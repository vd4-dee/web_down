# logic_download.py
import os
import time
import csv
import traceback
import functools
import zipfile # Needed for extract_zip_files
from datetime import datetime, timedelta

import pyotp # type: ignore
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import ReadTimeoutError, MaxRetryError # Import specific exceptions
import urllib3

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.remote_connection import RemoteConnection # For setting command timeout
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, ElementNotInteractableException,
    UnexpectedAlertPresentException, NoAlertPresentException
)
# Use webdriver_manager only if driver_path in config is not set or invalid
# from webdriver_manager.chrome import ChromeDriverManager # type: ignore

# --- Constants ---
# Increased timeouts (in seconds)
SELENIUM_COMMAND_TIMEOUT = 900 # Increased from default (usually 60s) for Selenium commands
WEBDRIVER_WAIT_TIMEOUT = 900   # Increased timeout for explicit waits (WebDriverWait)
PAGE_LOAD_TIMEOUT = 900        # Increased timeout for page loads
DOWNLOAD_WAIT_TIMEOUT = 1800   # Max time to wait for a single file download (30 min)
RETRY_DELAY = 10               # Default delay between retries for operations
CLICK_RETRY_DELAY = 15         # Longer delay specifically for click retries
MAX_RETRIES = 3                # Default number of retries for operations prone to failure
SHORT_WAIT = 2                 # Short pause time in seconds

# --- HTTP Configuration (For direct requests, not Selenium commands) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
urllib3.Timeout.DEFAULT_TIMEOUT = 600 # Timeout for direct requests

# Custom retry strategy for direct requests (if needed elsewhere)
# retry_strategy = Retry(
#     total=MAX_RETRIES,
#     backoff_factor=1,
#     status_forcelist=[408, 429, 500, 502, 503, 504],
#     allowed_methods=frozenset(['GET', 'POST']) # Specify methods if needed
# )
# session = requests.Session()
# adapter = HTTPAdapter(max_retries=retry_strategy)
# session.mount("http://", adapter)
# session.mount("https://", adapter)
# session.timeout = 600

# --- Region Data (Keep as defined in original) ---
regions_data = {
    0: {"name": "HCM", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[1]/div/span[3]"},
    1: {"name": "HNi", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[2]/div/span[3]"},
    2: {"name": "Mdong", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[3]/div/span[3]"},
    3: {"name": "Mtay", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[4]/div/span[3]"},
    4: {"name": "MB2", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[5]/div/span[3]"},
    5: {"name": "Mtrung", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[6]/div/span[3]"},
    6: {"name": "MB1", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[7]/div/span[3]"}
}

# --- Global Path Definitions ---
current_folder = os.path.dirname(os.path.abspath(__file__))
# Use LOG_FILE_PATH from app.py? For consistency, define it here relative to this file.
csv_filename = os.path.join(current_folder, 'download_log.csv')

# --- Helper Functions ---
def format_date_ddmmyyyy(date_str):
    """ Formats date string from 'YYYY-MM-DD' to 'DD/MM/YYYY'. """
    try:
        # Handle both datetime objects and string inputs
        if isinstance(date_str, datetime):
             return date_str.strftime('%d/%m/%Y')
        else:
             dt_obj = datetime.strptime(str(date_str), '%Y-%m-%d')
             return dt_obj.strftime('%d/%m/%Y')
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not format date '{date_str}' to DD/MM/YYYY: {e}. Returning original.")
        return str(date_str) # Return original string representation on error

def retry_on_exception(exceptions=(WebDriverException,), retries=MAX_RETRIES, delay=RETRY_DELAY, backoff=1.5):
    """
    Decorator to retry a function on specific Selenium/HTTP exceptions with exponential backoff.
    Catches WebDriverException by default, which includes ReadTimeoutError from localhost connection.
    """
    # Ensure exceptions is a tuple
    if not isinstance(exceptions, tuple):
        exceptions = (exceptions,)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract status_callback safely from kwargs if present
            status_callback = kwargs.get('status_callback')
            # Get self/instance from args if it's a method
            instance = args[0] if args and isinstance(args[0], WebAutomation) else None

            attempt = 0
            current_delay = delay
            last_exception = None

            while attempt < retries:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    # Check if the exception is specifically a connection error we might recover from
                    is_recoverable_timeout = isinstance(e, WebDriverException) and \
                                             ('timed out' in str(e).lower() or 'connection refused' in str(e).lower())

                    if status_callback:
                        status_callback(f"WARNING: Attempt {attempt}/{retries} failed for {func.__name__} with {type(e).__name__}. Error: {str(e)[:100]}...") # Log truncated error

                    if attempt >= retries:
                        if status_callback:
                            status_callback(f"ERROR: Max retries ({retries}) reached for {func.__name__}. Last error: {type(e).__name__}")
                        # No more retries, raise the last captured exception
                        raise last_exception from e
                    else:
                        # Wait before retrying
                        if status_callback:
                             status_callback(f"Retrying in {current_delay:.2f}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff # Apply backoff

                        # --- Optional: Connection Check/Reconnect ---
                        # If it's a timeout/connection error, try reconnecting (use with caution)
                        # if is_recoverable_timeout and instance:
                        #     if status_callback: status_callback("Attempting WebDriver reconnect due to timeout/connection error...")
                        #     if not instance.reconnect_if_needed(status_callback=status_callback):
                        #         # If reconnect fails decisively, stop retrying this function call
                        #         if status_callback: status_callback("ERROR: Reconnect failed. Stopping retries for this operation.")
                        #         raise last_exception # Raise the original error
                        #     else:
                        #         # Reconnect successful, continue to next attempt
                        #         if status_callback: status_callback("Reconnect successful, proceeding with retry.")
                        # --- End Optional Reconnect ---

                except Exception as e: # Catch any other unexpected error not in the specified exceptions
                    if status_callback:
                        status_callback(f"FATAL UNEXPECTED ERROR in {func.__name__} (attempt {attempt}): {type(e).__name__} - {e}. Stopping retries.")
                    traceback.print_exc() # Print traceback for unexpected errors
                    raise # Re-raise immediately
            # This line should ideally not be reached if retries > 0
            # If it is (e.g., retries=0), raise the last exception if one occurred
            if last_exception:
                raise last_exception
            # Or return None/raise custom error if function never succeeded and no exception was caught
            raise RuntimeError(f"{func.__name__} failed after {retries} attempts without specific exception.")


        return wrapper
    return decorator


class WebAutomation:
    """Handles browser automation using Selenium for downloading reports."""

    def __init__(self, driver_path, download_folder):
        """
        Initializes the WebDriver and sets up necessary configurations.

        Args:
            driver_path (str): Path to the ChromeDriver executable.
            download_folder (str): The specific folder where downloads for this run should be saved.
        """
        self.driver_path = driver_path
        self.download_folder = download_folder
        self.driver = None
        self.wait = None
        self.before_download = set() # Use set for efficient file checking

        print(f"Initializing WebAutomation. Download Folder: {self.download_folder}")

        # *** Set higher timeout for Selenium's internal HTTP client commands ***
        try:
            RemoteConnection.set_timeout(SELENIUM_COMMAND_TIMEOUT)
            print(f"Set Selenium RemoteConnection command timeout to {SELENIUM_COMMAND_TIMEOUT}s.")
        except Exception as e:
             print(f"Warning: Could not set RemoteConnection timeout: {e}")

        chrome_options = webdriver.ChromeOptions()
        prefs = {
            'download.default_directory': self.download_folder,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safeBrowse.enabled': True,
            'plugins.always_open_pdf_externally': True, # Useful for PDF reports
            # Performance improvement: disable image loading if not needed for interaction
            # "profile.managed_default_content_settings.images": 2,
        }
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging']) # Suppress DevTools messages

        # --- Stability and Performance Arguments ---
        chrome_options.add_argument('--no-sandbox') # Required in some environments (like Docker)
        chrome_options.add_argument('--disable-dev-shm-usage') # Overcomes limited resource problems
        chrome_options.add_argument('--disable-gpu') # Often needed for stability in headless/server environments
        chrome_options.add_argument('--window-size=1920x1080') # Set a reasonable window size
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--enable-automation')
        chrome_options.add_argument('--dns-prefetch-disable')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--remote-debugging-port=9222')
        # chrome_options.add_argument('--headless=new') # Use new headless mode if UI isn't needed during run

        # --- Initialize WebDriver Service and Driver ---
        try:
            # Check if driver_path exists
            if not os.path.exists(self.driver_path):
                print(f"Warning: ChromeDriver path '{self.driver_path}' not found.")
                # Option 1: Fallback to webdriver-manager (requires installation: pip install webdriver-manager)
                # print("Attempting to use webdriver-manager...")
                # try:
                #     self.service = Service(ChromeDriverManager().install())
                # except Exception as wdm_e:
                #      print(f"Error using webdriver-manager: {wdm_e}")
                #      raise RuntimeError(f"ChromeDriver not found at '{self.driver_path}' and webdriver-manager failed.") from wdm_e
                # Option 2: Raise error immediately
                raise FileNotFoundError(f"ChromeDriver executable not found at the specified path: {self.driver_path}")
            else:
                self.service = Service(self.driver_path)

            # capabilities = webdriver.DesiredCapabilities.CHROME.copy() # Deprecated
            # capabilities['pageLoadStrategy'] = 'normal'
            # capabilities['unhandledPromptBehavior'] = 'accept'

            print("Starting ChromeDriver service...")
            self.driver = webdriver.Chrome(
                service=self.service,
                options=chrome_options,
                # desired_capabilities=capabilities # Deprecated
            )
            print("WebDriver initialized.")

            # --- Set Driver Timeouts ---
            self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            # Reduce implicit wait, rely more on explicit waits
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, WEBDRIVER_WAIT_TIMEOUT) # Explicit wait setup

            # Initialize files present before any downloads
            self.update_files_before_download()

        except WebDriverException as e:
            print(f"FATAL: WebDriver initialization failed: {e}")
            traceback.print_exc()
            # Cleanup if service started but driver failed
            if hasattr(self, 'service') and self.service and self.service.process:
                self.service.stop()
            raise # Re-raise to stop the application

    # --- Utility Methods ---

    def update_files_before_download(self):
        """Updates the set of files currently present in the download folder."""
        if os.path.exists(self.download_folder):
            try:
                self.before_download = set(os.listdir(self.download_folder))
                # print(f"[Debug] Files before download: {self.before_download}") # Debug log
            except OSError as e:
                 print(f"Error listing download directory {self.download_folder}: {e}")
                 self.before_download = set() # Reset if error
        else:
            print(f"Warning: Download directory {self.download_folder} does not exist yet.")
            self.before_download = set()

    def wait_for_download_to_finish(self, timeout=DOWNLOAD_WAIT_TIMEOUT, status_callback=None):
        """
        Waits for a new file download to complete in the download folder.
        Returns the name of the newly downloaded file or None if timeout/error.
        """
        if status_callback:
            status_callback(f"Waiting for download to complete (timeout: {timeout}s)...")

        start_time = time.time()
        new_file_path = None
        last_partial_file_info = {} # Store info like {filename: size}

        while time.time() - start_time < timeout:
            current_files = set()
            try:
                if os.path.exists(self.download_folder):
                    current_files = set(os.listdir(self.download_folder))
                else:
                    if status_callback: status_callback("Warning: Download folder disappeared during wait.")
                    time.sleep(SHORT_WAIT)
                    continue # Skip this iteration if folder doesn't exist

            except OSError as e:
                if status_callback: status_callback(f"Error accessing download folder during wait: {e}")
                time.sleep(SHORT_WAIT) # Wait before retrying listdir
                continue

            # Calculate new files since the operation started
            new_files = current_files - self.before_download

            # 1. Check for completely downloaded files (not partial)
            # Exclude common temporary file extensions
            completed_files = [f for f in new_files if not f.lower().endswith(('.tmp', '.crdownload', '.part'))]
            if completed_files:
                try:
                    # Find the most recently modified completed file
                    newest_file_path = max(
                        [os.path.join(self.download_folder, f) for f in completed_files if os.path.isfile(os.path.join(self.download_folder, f))],
                        key=os.path.getmtime
                    )
                    new_file_name = os.path.basename(newest_file_path)
                    if status_callback: status_callback(f"Detected completed file: {new_file_name}")
                    # Add this completed file to the baseline for the *next* download in this run
                    # self.before_download.add(new_file_name) # Do this after rename/extract maybe?
                    return new_file_name # Success
                except (ValueError, OSError) as e:
                     if status_callback: status_callback(f"Error identifying latest completed file: {e}")
                     # Continue checking in case of transient error

            # 2. Check for partial files to monitor progress
            partial_files = {f for f in new_files if f.lower().endswith(('.tmp', '.crdownload', '.part'))}
            active_partials_found = False
            if partial_files:
                for partial_file in partial_files:
                    partial_file_path = os.path.join(self.download_folder, partial_file)
                    try:
                        current_size = os.path.getsize(partial_file_path)
                        last_size = last_partial_file_info.get(partial_file, -1)

                        if current_size > last_size:
                            if status_callback:
                                # Report progress less frequently to avoid flooding logs
                                if time.time() % 10 < 1: # Report roughly every 10 seconds
                                    status_callback(f"Download in progress ({partial_file}): {current_size} bytes...")
                            last_partial_file_info[partial_file] = current_size
                            active_partials_found = True
                            # Optional: Slightly extend timeout if progress is being made
                            # start_time = time.time() # Resetting fully can be risky
                        elif current_size == last_size:
                             # Size hasn't changed, might be stalled or done but not renamed
                             active_partials_found = True # Still considered active for now
                        # else: size decreased? Ignore or log warning

                    except OSError:
                        # File might have been renamed/deleted between listdir and getsize
                        if partial_file in last_partial_file_info:
                            del last_partial_file_info[partial_file] # Remove stale entry
                        continue # Check next partial file

            # If no completed file found yet, and no partials are active, wait
            if not completed_files and not active_partials_found and partial_files:
                # All partials seem stalled, but keep waiting for rename or timeout
                 pass

            # Cleanup info for partials that disappeared (likely renamed/completed)
            stale_partials = set(last_partial_file_info.keys()) - partial_files
            for stale in stale_partials:
                del last_partial_file_info[stale]

            time.sleep(SHORT_WAIT) # Check every few seconds

        # --- Loop Timed Out ---
        if status_callback:
            status_callback(f"WARNING: Download wait timed out after {timeout} seconds.")
            # Check final state
            final_files = set(os.listdir(self.download_folder)) if os.path.exists(self.download_folder) else set()
            final_new_files = final_files - self.before_download
            final_completed = [f for f in final_new_files if not f.lower().endswith(('.tmp', '.crdownload', '.part'))]
            final_partial = [f for f in final_new_files if f.lower().endswith(('.tmp', '.crdownload', '.part'))]
            if final_completed:
                 status_callback(f"Timeout occurred, but found completed file(s) post-timeout: {final_completed}")
                 # Decide if this counts as success - let's return the newest one found post-timeout
                 try:
                     newest_file_path = max([os.path.join(self.download_folder, f) for f in final_completed if os.path.isfile(os.path.join(self.download_folder, f))], key=os.path.getmtime)
                     return os.path.basename(newest_file_path)
                 except Exception as e:
                     status_callback(f"Error getting newest file post-timeout: {e}")
                     return None # Indicate failure
            elif final_partial:
                 status_callback(f"Timeout occurred with file(s) still potentially downloading: {final_partial}")
                 return None # Indicate failure
            else:
                 status_callback("Timeout occurred and no new completed or partial files were detected.")
                 return None # Indicate failure

    def safe_click(self, locator, description="element", retries=MAX_RETRIES, delay=CLICK_RETRY_DELAY, status_callback=None):
        """
        Attempts to click an element safely using explicit waits and retries.

        Args:
            locator (tuple): By locator tuple (e.g., (By.ID, 'element_id')).
            description (str): A human-readable name for the element for logging.
            retries (int): Number of click attempts.
            delay (int): Delay between retries in seconds.
            status_callback (function, optional): Callback function for status updates.

        Returns:
            bool: True if click was successful, False otherwise.
        """
        if not self.driver or not self.wait:
            if status_callback: status_callback("ERROR: safe_click called but WebDriver not initialized.")
            return False # Cannot proceed

        last_exception = None
        for attempt in range(retries):
            try:
                # 1. Wait for element presence *first*
                # self.wait.until(EC.presence_of_element_located(locator))
                # 2. Wait for element to be clickable (implies presence, visibility, enabled)
                element = self.wait.until(EC.element_to_be_clickable(locator))

                # 3. Optional: Scroll into view just before clicking
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.5) # Brief pause after scroll
                except Exception as scroll_err:
                     if status_callback: status_callback(f"Warning: Could not scroll '{description}' into view: {scroll_err}")

                # 4. Perform the click
                element.click()
                if status_callback: status_callback(f"Clicked '{description}' successfully (Attempt {attempt+1}).")
                return True # Click succeeded

            # --- Handle Specific Click-Related Exceptions ---
            except (ElementClickInterceptedException, ElementNotInteractableException) as e:
                last_exception = e
                error_type = type(e).__name__
                if status_callback: status_callback(f"WARNING: Click attempt {attempt+1} for '{description}' failed ({error_type}). Element might be obscured or not ready.")
                # Option: Try JS click on the last attempt as a fallback?
                if attempt == retries - 1:
                     try:
                         if status_callback: status_callback(f"Trying JavaScript click fallback for '{description}'...")
                         element_js = self.driver.find_element(*locator) # Re-find element for JS click
                         self.driver.execute_script("arguments[0].click();", element_js)
                         if status_callback: status_callback(f"JavaScript click successful for '{description}'.")
                         return True
                     except Exception as js_e:
                         if status_callback: status_callback(f"JavaScript click fallback failed: {js_e}")
                         last_exception = js_e # Update last exception
                         # Fall through to wait and retry logic end

            # --- Handle Element Not Found / Timeout Waiting ---
            except (TimeoutException, NoSuchElementException) as e:
                last_exception = e
                error_type = type(e).__name__
                if status_callback: status_callback(f"ERROR: Failed to find or wait for '{description}' (locator: {locator}) on attempt {attempt+1} ({error_type}).")
                # No point retrying immediately if the element cannot be found after the wait
                break # Exit the retry loop for this error

            # --- Handle General WebDriver Errors (including potential timeouts) ---
            except WebDriverException as e:
                last_exception = e
                error_type = type(e).__name__
                # Check if it's the specific timeout error we're trying to fix
                is_timeout = 'timed out' in str(e).lower()
                timeout_msg = " (Timeout Error)" if is_timeout else ""
                if status_callback: status_callback(f"WARNING: WebDriverException{timeout_msg} during click attempt {attempt+1} for '{description}': {str(e)[:100]}...")

            # --- Catch any other unexpected error ---
            except Exception as e:
                last_exception = e
                error_type = type(e).__name__
                if status_callback: status_callback(f"ERROR: Unexpected error {error_type} clicking '{description}' on attempt {attempt+1}: {e}")
                traceback.print_exc() # Log full trace for unexpected errors
                break # Exit retry loop for unexpected errors

            # --- Wait before retrying if loop continues ---
            if attempt < retries - 1:
                if status_callback: status_callback(f"Waiting {delay}s before retrying click on '{description}'...")
                time.sleep(delay)
            else: # Last attempt failed
                 if status_callback: status_callback(f"ERROR: Failed to click '{description}' after {retries} attempts. Last error: {type(last_exception).__name__}")

        return False # Failed after all retries or breaking early

    @staticmethod
    def write_log_to_csv(log_data, filename=csv_filename):
        """Writes a log entry to the specified CSV file."""
        # Check if file exists, create with header if not
        file_exists = os.path.isfile(filename)
        try:
            # Use 'a' mode to append, newline='' to prevent extra blank rows
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Write header only if file is new or empty
                if not file_exists or os.path.getsize(filename) == 0:
                    writer.writerow(['Timestamp', 'Start Date', 'End Date', 'Status', 'File Name', 'Error Message'])
                writer.writerow(log_data)
        except IOError as e:
            print(f"CRITICAL ERROR: Could not write to log file {filename}: {e}")
            # Fallback: print log data to console if CSV fails
            print(f"LOG_DATA (CSV failed): {log_data}")
        except Exception as e:
             print(f"CRITICAL ERROR: Unexpected error writing to log file {filename}: {e}")
             print(f"LOG_DATA (CSV failed): {log_data}")


    def capture_screenshot(self, filename_prefix="error_screenshot"):
        """Saves a screenshot of the current browser window."""
        if not self.driver:
            print("Cannot capture screenshot, driver not available.")
            return None
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Save screenshot in the download folder for this run
            filename = os.path.join(self.download_folder, f"{filename_prefix}_{timestamp}.png")
            if self.driver.save_screenshot(filename):
                 print(f"Screenshot saved: {filename}")
                 return filename
            else:
                 print("Failed to save screenshot (driver returned false).")
                 return None
        except WebDriverException as e:
            print(f"Failed to capture screenshot due to WebDriverException: {e}")
            return None
        except Exception as e:
            print(f"Failed to capture screenshot due to unexpected error: {e}")
            return None

    def handle_alert(self, accept=True, status_callback=None):
        """Checks for and handles browser alerts."""
        try:
            alert = self.wait.until(EC.alert_is_present())
            # alert = self.driver.switch_to.alert # Alternative way to get alert
            alert_text = alert.text
            if status_callback: status_callback(f"Alert detected: '{alert_text}'")
            if accept:
                alert.accept()
                if status_callback: status_callback("Accepted alert.")
            else:
                alert.dismiss()
                if status_callback: status_callback("Dismissed alert.")
            return True # Alert was handled
        except TimeoutException:
            # No alert was present within the wait time
            return False # No alert handled
        except NoAlertPresentException:
             # Alert disappeared before we could handle it
             return False
        except Exception as e:
            if status_callback: status_callback(f"Error handling alert: {e}")
            # Decide how to proceed - maybe try to continue?
            return False # Indicate alert was not successfully handled

    # --- Login Method ---
    @retry_on_exception(exceptions=(WebDriverException,), retries=2, delay=10) # Retry login on WebDriver errors
    def login(self, login_url, email, password, otp_secret, status_callback=None):
        """Logs into the website using credentials and OTP."""
        if not self.driver or not self.wait:
            raise WebDriverException("WebDriver not initialized for login.")
        if status_callback: status_callback(f"Attempting login for user {email}...")

        try:
            self.driver.get(login_url) # Go to a page that potentially redirects to login

            # --- Wait for and fill login form ---
            # Locators need to be verified against the actual login page HTML
            # These are examples based on the original snippet IDs (mat-input-3, 4, 5)
            email_locator = (By.ID, 'mat-input-3') # Replace with actual ID/locator
            password_locator = (By.ID, 'mat-input-4') # Replace with actual ID/locator
            otp_locator = (By.ID, 'mat-input-5') # Replace with actual ID/locator
            # Login button locator might be more complex
            login_button_locator = (By.ID, 'kt_login_signin_submit') # Replace with actual ID/locator

            email_field = self.wait.until(EC.element_to_be_clickable(email_locator))
            email_field.clear()
            email_field.send_keys(email)

            password_field = self.wait.until(EC.element_to_be_clickable(password_locator))
            password_field.clear()
            password_field.send_keys(password)

            # --- Generate and Enter OTP ---
            try:
                totp = pyotp.TOTP(otp_secret)
                otp_code = totp.now()
                # DO NOT log OTP in production, only for temporary local debugging if necessary
                # if status_callback: status_callback(f"[DEBUG ONLY] Generated OTP: {otp_code}")
                if status_callback: status_callback("Entering OTP...")
                otp_field = self.wait.until(EC.element_to_be_clickable(otp_locator))
                otp_field.clear()
                otp_field.send_keys(otp_code)
            except Exception as otp_e:
                if status_callback: status_callback(f"ERROR: Failed to generate or enter OTP: {otp_e}")
                self.capture_screenshot("otp_error")
                raise WebDriverException(f"OTP generation/entry failed: {otp_e}") from otp_e

            # --- Click Login Button Safely ---
            if not self.safe_click(login_button_locator, "Login Button", retries=2, status_callback=status_callback):
                self.capture_screenshot("login_click_failed")
                raise WebDriverException("Failed to click login button after retries.")

            # --- Wait for Login Success Indicator ---
            # This is crucial and needs a reliable element/condition
            # Example: Wait for a specific element on the dashboard/report page
            # Or wait for the URL to change away from the login page
            try:
                 # Option A: Wait for URL to change (if login redirects)
                 # self.wait.until_not(EC.url_contains("login")) # Adjust 'login' substring if needed
                 # Option B: Wait for a known element on the target page
                 # Example ID: 'ctl00_MainContent_btnExportCSVDemo_input' from report page
                 success_indicator_locator = (By.ID, 'ctl00_MainContent_btnExportCSVDemo_input')
                 self.wait.until(EC.presence_of_element_located(success_indicator_locator))
                 if status_callback: status_callback("Login successful (detected element on target page).")
                 return True
            except TimeoutException:
                  # Login might have failed silently (e.g., bad credentials)
                  if status_callback: status_callback("ERROR: Login failed or took too long. Success indicator not found.")
                  self.capture_screenshot("login_failed_or_timeout")
                  # Check for specific error messages on the page if possible
                  # error_msg_locator = (By.CSS_SELECTOR, ".login-error-message") # Example
                  # try:
                  #      error_element = self.driver.find_element(*error_msg_locator)
                  #      if status_callback: status_callback(f"Login page error message: {error_element.text}")
                  # except NoSuchElementException:
                  #      pass # No specific error message found
                  return False # Indicate login failure


        except (TimeoutException, NoSuchElementException) as e:
            log_error = f"Login failed: Could not find login elements ({type(e).__name__}). Check locators."
            if status_callback: status_callback(f"ERROR: {log_error}")
            self.capture_screenshot("login_element_error")
            # Raise a more specific error or return False
            # raise WebDriverException(log_error) from e
            return False
        except WebDriverException as e: # Catch errors during the process, handled by decorator
            log_error = f"Login failed: WebDriver error occurred - {e}"
            if status_callback: status_callback(f"ERROR: {log_error}")
            self.capture_screenshot("login_webdriver_error")
            raise # Re-raise WebDriverException for decorator retry
        except Exception as e: # Catch other unexpected errors
            log_error = f"Login failed: Unexpected error - {type(e).__name__}: {e}"
            if status_callback: status_callback(f"FATAL ERROR: {log_error}")
            self.capture_screenshot("login_unexpected_error")
            traceback.print_exc()
            raise WebDriverException(log_error) from e # Wrap in WebDriverException

    # --- File Handling Methods (from original, adapted) ---

    def extract_zip_files(self, status_callback=None):
        """
        Extracts newly downloaded zip files found in the download folder.
        Assumes new zip files are those not present in self.before_download.
        """
        if status_callback: status_callback("Checking for new zip files to extract...")
        extracted_something = False
        files_after_download = set()
        try:
            if os.path.exists(self.download_folder):
                 files_after_download = set(os.listdir(self.download_folder))
            else:
                 if status_callback: status_callback("Warning: Download folder not found for extraction.")
                 return # Cannot extract if folder doesn't exist

            # Identify new zip files
            new_zip_files = {f for f in files_after_download if f not in self.before_download and f.lower().endswith('.zip')}

            if not new_zip_files:
                if status_callback: status_callback("No new zip files found to extract.")
                return

            for zip_file in new_zip_files:
                zip_file_path = os.path.join(self.download_folder, zip_file)
                if not os.path.isfile(zip_file_path): continue # Skip if not a file

                try:
                    if status_callback: status_callback(f"Extracting '{zip_file}'...")
                    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                        zip_ref.extractall(self.download_folder)
                    if status_callback: status_callback(f"Successfully extracted: {zip_file}")
                    extracted_something = True
                    # Optional: Delete zip file after successful extraction
                    # try:
                    #     os.remove(zip_file_path)
                    #     if status_callback: status_callback(f"Deleted zip file: {zip_file}")
                    # except OSError as del_e:
                    #      if status_callback: status_callback(f"Warning: Could not delete zip file {zip_file}: {del_e}")

                except zipfile.BadZipFile:
                     if status_callback: status_callback(f"ERROR: Bad zip file '{zip_file}'. Skipping.")
                     print(f"ERROR: Bad zip file '{zip_file}'. Skipping.")
                except Exception as e:
                     if status_callback: status_callback(f"ERROR extracting '{zip_file}': {e}")
                     print(f"ERROR extracting '{zip_file}': {e}")

            # Update the baseline AFTER processing all zips in this batch
            # self.before_download = set(os.listdir(self.download_folder)) # Update to reflect extracted files and potentially deleted zips

        except Exception as e:
             if status_callback: status_callback(f"Error during zip extraction process: {e}")
             print(f"Error during zip extraction process: {e}")

    def rename_downloaded_file(self, original_filename, from_date, to_date, suffix="", status_callback=None):
        """
        Renames a specific downloaded file based on date range and suffix.

        Args:
            original_filename (str): The name of the file to rename (must exist in download_folder).
            from_date (str): Start date string ('YYYY-MM-DD').
            to_date (str): End date string ('YYYY-MM-DD').
            suffix (str): Optional suffix to add before the extension.
            status_callback (function, optional): Callback for status updates.

        Returns:
            str or None: The new filename if successful, None otherwise.
        """
        if not original_filename:
             if status_callback: status_callback("Rename failed: No original filename provided.")
             return None

        original_full_path = os.path.join(self.download_folder, original_filename)

        if not os.path.isfile(original_full_path):
             if status_callback: status_callback(f"Rename failed: File '{original_filename}' not found.")
             return None

        try:
            # --- Date Formatting ---
            from_date_formatted = datetime.strptime(from_date, '%Y-%m-%d').strftime('%d%m%Y')
            to_date_formatted = datetime.strptime(to_date, '%Y-%m-%d').strftime('%d%m%Y')
            # --- End Date Formatting ---

            file_name_part, file_extension = os.path.splitext(original_filename)

            # --- Skip Rename Conditions (Example) ---
            # if file_name_part.startswith("BaoCaoFAF001"):
            #     if status_callback: status_callback(f"Skipping rename for special report: {original_filename}")
            #     return original_filename # Return original name if skipped

            # --- Construct New Name ---
            # Clean file_name_part if necessary (e.g., remove temporary prefixes)
            cleaned_name = file_name_part # Add cleaning logic if needed
            new_name = f"{cleaned_name}_{from_date_formatted}_{to_date_formatted}{suffix}{file_extension}".replace(' ','_')
            new_full_path = os.path.join(self.download_folder, new_name)

            # Handle potential naming conflicts
            counter = 1
            base_new_name = new_name
            while os.path.exists(new_full_path):
                 if status_callback: status_callback(f"Warning: File '{new_name}' already exists. Appending counter.")
                 name_part, ext_part = os.path.splitext(base_new_name)
                 new_name = f"{name_part}_{counter}{ext_part}"
                 new_full_path = os.path.join(self.download_folder, new_name)
                 counter += 1

            # --- Perform Rename ---
            if status_callback: status_callback(f"Attempting to rename '{original_filename}' to '{new_name}'")
            os.rename(original_full_path, new_full_path)
            if status_callback: status_callback(f"Successfully renamed file to: {new_name}")
            return new_name # Return the actual new name

        except Exception as e:
            error_msg = f"Error renaming file '{original_filename}': {e}"
            if status_callback: status_callback(f"ERROR: {error_msg}")
            print(f"ERROR: {error_msg}")
            return None # Indicate failure

    # --- Core Download Logic (Generic - Needs specific implementations below) ---

    def _perform_download_steps(self, report_url, from_date, to_date, report_specific_setup=None, file_suffix="", status_callback=None):
        """Internal helper to perform common download steps."""
        if not self.driver or not self.wait:
            raise WebDriverException("WebDriver not initialized.")

        log_file_name = ""
        log_status = "Failed"
        log_error = ""
        downloaded_original_name = None

        try:
            if status_callback: status_callback(f"Navigating to report URL: {report_url}")
            self.driver.get(report_url)
            # Wait for page readiness (e.g., presence of date inputs)
            sdate_locator = (By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')
            self.wait.until(EC.presence_of_element_located(sdate_locator))

            # --- Perform report-specific setup actions (like clicking radio buttons) ---
            if report_specific_setup:
                report_specific_setup()

            # --- Enter Dates ---
            if status_callback: status_callback(f"Setting 'To Date': {to_date}")
            edate_locator = (By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')
            edate_input = self.wait.until(EC.element_to_be_clickable(edate_locator))
            edate_input.clear()
            edate_input.send_keys(format_date_ddmmyyyy(to_date))

            if status_callback: status_callback(f"Setting 'From Date': {from_date}")
            sdate_input = self.wait.until(EC.element_to_be_clickable(sdate_locator))
            sdate_input.clear()
            sdate_input.send_keys(format_date_ddmmyyyy(from_date))

            # --- Click Download Button ---
            download_button_locator = (By.ID, 'ctl00_MainContent_btnExportCSVDemo_input') # Common download button ID? Verify.
            if status_callback: status_callback("Locating and clicking download button...")

            # Handle alerts just before clicking (sometimes appear on date change)
            self.handle_alert(accept=True, status_callback=status_callback)

            # Update file list *just before* clicking
            self.update_files_before_download()

            if self.safe_click(download_button_locator, "Download Button", status_callback=status_callback):
                # Handle alerts immediately after clicking
                self.handle_alert(accept=True, status_callback=status_callback)

                # --- Wait for Download ---
                downloaded_original_name = self.wait_for_download_to_finish(status_callback=status_callback)

                if downloaded_original_name:
                    # --- Process Downloaded File ---
                    if status_callback: status_callback(f"Processing downloaded file: {downloaded_original_name}")

                    # 1. Rename the originally downloaded file
                    renamed_file = self.rename_downloaded_file(downloaded_original_name, from_date, to_date, file_suffix, status_callback)
                    log_file_name = renamed_file if renamed_file else downloaded_original_name # Log the final name

                    # 2. Extract if it was a zip file (check by original name)
                    if downloaded_original_name.lower().endswith('.zip'):
                        self.extract_zip_files(status_callback=status_callback)
                        # Optional: Rename extracted files if needed - Requires more complex logic
                        # self.rename_extracted_files(...)

                    # Consider successful if download finished and rename didn't fail critically
                    log_status = "Success" if renamed_file is not None else "Success (Rename Failed)"
                    if status_callback: status_callback(f"Download and processing complete. Final file state: {log_file_name}")

                else: # wait_for_download_to_finish timed out / failed
                    log_error = f"Download wait timed out or failed."
                    log_status = "Failed (Download Wait)"
                    if status_callback: status_callback(f"ERROR: {log_error}")
                    # Capture screenshot on wait timeout
                    self.capture_screenshot("download_wait_timeout")
            else:
                # safe_click failed after retries
                log_error = "Failed to click download button after multiple retries."
                log_status = "Failed (Click Error)"
                if status_callback: status_callback(f"ERROR: {log_error}")
                self.capture_screenshot("download_click_error")

        except UnexpectedAlertPresentException as alert_e:
            log_status = "Failed (Alert)"
            alert_text = "Unknown Alert"
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.accept() # Try to accept it
            except Exception as inner_alert_e:
                 alert_text += f" (Error handling alert: {inner_alert_e})"
            log_error = f"Unhandled Alert: '{alert_text}' - {alert_e}"
            if status_callback: status_callback(f"ERROR: {log_error}")
            self.capture_screenshot("unexpected_alert")
        except WebDriverException as e: # Catch specific Selenium errors
            log_status = "Failed (WebDriver Error)"
            log_error = f"WebDriver error during download steps: {type(e).__name__} - {str(e)[:150]}..." # Truncate long messages
            if status_callback: status_callback(f"ERROR: {log_error}")
            self.capture_screenshot("download_webdriver_error")
            traceback.print_exc() # Log full trace for WebDriver errors
            raise # Re-raise WebDriverException to be potentially caught by retry decorator
        except Exception as e: # Catch any other unexpected error
            log_status = "Failed (Unexpected Error)"
            log_error = f"Unexpected error during download steps: {type(e).__name__} - {e}"
            if status_callback: status_callback(f"FATAL ERROR: {log_error}")
            self.capture_screenshot("download_unexpected_error")
            traceback.print_exc()
            raise WebDriverException(log_error) from e # Wrap unexpected errors

        finally:
            # --- Log Result ---
            log_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                from_date, to_date, log_status, log_file_name, log_error
            ]
            self.write_log_to_csv(log_data)
            if status_callback: status_callback(f"Logged download status '{log_status}' for {from_date}-{to_date}.")

        # Return True if successful, False otherwise (or raise exception)
        if log_status.startswith("Success"):
            return True
        else:
            # Raise a specific exception for the calling chunking method to catch
            raise DownloadFailedException(f"Download failed for {from_date}-{to_date}. Status: {log_status}, Error: {log_error}")


    # --- Report-Specific Download Methods ---

    @retry_on_exception() # Apply retry decorator
    def download_report_001(self, report_url, from_date, to_date, status_callback=None):
        """Downloads report FAF001 for a single date range."""
        if status_callback: status_callback("Executing specific logic for FAF001...")
        def setup_001():
             # Click the specific radio button for FAF001 type
             radio_locator = (By.ID, 'ctl00_MainContent_rblType_1') # Verify ID
             if not self.safe_click(radio_locator, "FAF001 Report Type Radio", status_callback=status_callback):
                 raise DownloadFailedException("Failed to click FAF001 report type radio button.")
        # Use the internal helper
        return self._perform_download_steps(report_url, from_date, to_date, report_specific_setup=setup_001, file_suffix="", status_callback=status_callback)

    @retry_on_exception()
    def download_report_004N(self, report_url, from_date, to_date, status_callback=None):
        """Downloads report FAF004N (Imports) for a single date range."""
        if status_callback: status_callback("Executing specific logic for FAF004N (Imports)...")
        def setup_004N():
             # Click the specific radio button for FAF004N type (Imports)
             radio_locator = (By.ID, 'ctl00_MainContent_rblType_1') # Verify ID (Imports)
             if not self.safe_click(radio_locator, "FAF004N Report Type Radio (Imports)", status_callback=status_callback):
                 raise DownloadFailedException("Failed to click FAF004N report type radio button.")
        # Use the internal helper, add suffix "N"
        return self._perform_download_steps(report_url, from_date, to_date, report_specific_setup=setup_004N, file_suffix="N", status_callback=status_callback)

    @retry_on_exception()
    def download_report_004X(self, report_url, from_date, to_date, status_callback=None):
        """Downloads report FAF004X (Exports) for a single date range."""
        if status_callback: status_callback("Executing specific logic for FAF004X (Exports)...")
        def setup_004X():
             # Click the specific radio button for FAF004X type (Exports)
             radio_locator = (By.ID, 'ctl00_MainContent_rblType_0') # Verify ID (Exports)
             if not self.safe_click(radio_locator, "FAF004X Report Type Radio (Exports)", status_callback=status_callback):
                 raise DownloadFailedException("Failed to click FAF004X report type radio button.")
        # Use the internal helper, add suffix "X"
        return self._perform_download_steps(report_url, from_date, to_date, report_specific_setup=setup_004X, file_suffix="X", status_callback=status_callback)

    # --- Add download_report_002, 003, 005, 006, 028 etc. following the same pattern ---
    # If they don't need specific setup, they can use _perform_download_steps directly
    @retry_on_exception()
    def download_generic_report(self, report_url, from_date, to_date, status_callback=None):
         """Downloads a generic report with no special setup."""
         if status_callback: status_callback("Executing generic download logic...")
         return self._perform_download_steps(report_url, from_date, to_date, status_callback=status_callback)

    # --- Region Selection Logic (Example for FAF030) ---
    def select_region(self, region_index, status_callback=None):
        """Selects a single region based on its index."""
        try:
            if region_index in regions_data:
                region = regions_data[region_index]
                xpath = region["xpath"]
                region_name = region["name"]
                locator = (By.XPATH, xpath)

                if status_callback: status_callback(f"Selecting region '{region_name}' (Index: {region_index})")
                # Use safe_click for selecting the region
                if not self.safe_click(locator, f"Region '{region_name}'", status_callback=status_callback):
                    if status_callback: status_callback(f"ERROR: Failed to click region '{region_name}'.")
                    return False # Indicate failure
                time.sleep(SHORT_WAIT) # Add a small pause after selecting region
                return True
            else:
                if status_callback: status_callback(f"ERROR: Invalid region index: {region_index}.")
                return False
        except Exception as e:
            if status_callback: status_callback(f"ERROR selecting region index {region_index}: {e}")
            # Optionally capture screenshot here
            # self.capture_screenshot(f"region_select_error_idx_{region_index}")
            return False


    @retry_on_exception() # Apply retry decorator
    def download_report_for_region(self, report_url, from_date, to_date, region_index, status_callback=None):
        """Downloads a report requiring region selection (e.g., FAF030)."""
        if region_index not in regions_data:
             if status_callback: status_callback(f"Invalid region index {region_index} passed to download_report_for_region.")
             return False # Or raise error

        region_name = regions_data[region_index]["name"]
        if status_callback: status_callback(f"Executing download for region: {region_name}")

        log_file_name = ""
        log_status = "Failed"
        log_error = ""
        downloaded_original_name = None

        try:
            if status_callback: status_callback(f"Navigating to report URL: {report_url}")
            self.driver.get(report_url)
            sdate_locator = (By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput') # Example element to wait for
            self.wait.until(EC.presence_of_element_located(sdate_locator))

            # --- Enter Dates ---
            if status_callback: status_callback(f"Setting 'To Date': {to_date}")
            edate_locator = (By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')
            edate_input = self.wait.until(EC.element_to_be_clickable(edate_locator))
            edate_input.clear()
            edate_input.send_keys(format_date_ddmmyyyy(to_date))

            if status_callback: status_callback(f"Setting 'From Date': {from_date}")
            sdate_input = self.wait.until(EC.element_to_be_clickable(sdate_locator))
            sdate_input.clear()
            sdate_input.send_keys(format_date_ddmmyyyy(from_date))

            # --- Open Region Selection Tree and Select Region ---
            # These locators are from the original code and need verification
            tree_arrow_locator = (By.ID, 'ctl00_MainContent_TreeShopThuoc1_cboDepartmentsThuoc_Arrow')
            tree_plus_locator = (By.CLASS_NAME, 'rtPlus') # This might be too generic
            # Click to open the dropdown/tree
            if not self.safe_click(tree_arrow_locator, "Region Tree Arrow", status_callback=status_callback):
                raise DownloadFailedException("Failed to open region selection tree.")
            # Click to expand the tree (if needed)
            if not self.safe_click(tree_plus_locator, "Region Tree Expand (+)", status_callback=status_callback):
                # This might not be critical if regions are already visible
                 if status_callback: status_callback("Warning: Could not click tree expand (+), proceeding anyway.")
            # Select the specific region
            if not self.select_region(region_index, status_callback=status_callback):
                raise DownloadFailedException(f"Failed to select region '{region_name}'.")

            # Click outside the tree to close it (if necessary) - Example XPath
            # Adjust this locator based on actual page structure
            # body_locator = (By.XPATH, "//body")
            # self.safe_click(body_locator, "Page Body (to close dropdown)", status_callback=status_callback)
            # Or find a specific element that closes the dropdown
            close_element_locator = (By.XPATH, "//div[contains(text(), 'Báo Cáo Nhập Xuất Tồn FAF')]") # From original
            if not self.safe_click(close_element_locator, "Report Title (to close dropdown)", status_callback=status_callback):
                  if status_callback: status_callback("Warning: Could not explicitly close region dropdown.")


            # --- Click Download Button (Different ID for region reports?) ---
            # Original code used 'ctl00_MainContent_btnExportExcel_input' for region report
            download_button_locator_region = (By.ID, 'ctl00_MainContent_btnExportExcel_input') # Verify this ID
            if status_callback: status_callback("Locating and clicking region download button...")

            self.handle_alert(accept=True, status_callback=status_callback) # Check for alerts before click
            self.update_files_before_download() # Update file list

            if self.safe_click(download_button_locator_region, "Region Download Button", status_callback=status_callback):
                self.handle_alert(accept=True, status_callback=status_callback) # Check for alerts after click

                # --- Wait for Download ---
                downloaded_original_name = self.wait_for_download_to_finish(status_callback=status_callback)

                if downloaded_original_name:
                    # --- Process Downloaded File ---
                    if status_callback: status_callback(f"Processing downloaded file: {downloaded_original_name}")
                    # Rename using region name as suffix
                    renamed_file = self.rename_downloaded_file(downloaded_original_name, from_date, to_date, region_name, status_callback)
                    log_file_name = renamed_file if renamed_file else downloaded_original_name

                    if downloaded_original_name.lower().endswith('.zip'):
                        self.extract_zip_files(status_callback=status_callback)
                        # Add renaming logic for extracted files specific to region if needed

                    log_status = "Success" if renamed_file is not None else "Success (Rename Failed)"
                    if status_callback: status_callback(f"Region {region_name} download and processing complete. File: {log_file_name}")

                else: # wait_for_download_to_finish failed
                    log_error = f"Download wait timed out or failed for region {region_name}."
                    log_status = "Failed (Download Wait)"
                    if status_callback: status_callback(f"ERROR: {log_error}")
                    self.capture_screenshot(f"region_{region_name}_wait_timeout")
            else:
                # safe_click failed
                log_error = f"Failed to click download button for region {region_name} after multiple retries."
                log_status = "Failed (Click Error)"
                if status_callback: status_callback(f"ERROR: {log_error}")
                self.capture_screenshot(f"region_{region_name}_click_error")

        # --- Error Handling ---
        except DownloadFailedException as df_err: # Catch specific failure points
             log_status = "Failed (Setup/Select Error)"
             log_error = str(df_err)
             if status_callback: status_callback(f"ERROR: {log_error}")
             self.capture_screenshot(f"region_{region_name}_setup_error")
             # Do not re-raise, let finally block handle logging
        except UnexpectedAlertPresentException as alert_e:
             # Handle same as in _perform_download_steps
             log_status = "Failed (Alert)"
             # ... alert handling ...
             log_error = f"Unhandled Alert for region {region_name}: ..."
             if status_callback: status_callback(f"ERROR: {log_error}")
             self.capture_screenshot(f"region_{region_name}_alert")
        except WebDriverException as e:
             log_status = "Failed (WebDriver Error)"
             log_error = f"WebDriver error for region {region_name}: {type(e).__name__} - {str(e)[:150]}..."
             if status_callback: status_callback(f"ERROR: {log_error}")
             self.capture_screenshot(f"region_{region_name}_webdriver_error")
             traceback.print_exc()
             # Do not re-raise, let finally block handle logging
        except Exception as e:
             log_status = "Failed (Unexpected Error)"
             log_error = f"Unexpected error for region {region_name}: {type(e).__name__} - {e}"
             if status_callback: status_callback(f"FATAL ERROR: {log_error}")
             self.capture_screenshot(f"region_{region_name}_unexpected_error")
             traceback.print_exc()
             # Do not re-raise

        finally:
            # --- Log Result ---
            log_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                from_date, to_date, f"{log_status} (Region: {region_name})", log_file_name, log_error
            ]
            self.write_log_to_csv(log_data)
            if status_callback: status_callback(f"Logged region download status '{log_status}' for {from_date}-{to_date}, Region: {region_name}.")

        # Return True/False based on success
        return log_status.startswith("Success")


    # --- Chunking Methods ---

    def split_date_range(self, start_date_str, end_date_str, chunk_size):
        """
        Splits a date range into smaller chunks.
        Handles chunk_size as number of days or the string 'month'.
        """
        try:
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
             print(f"Error parsing date range: {start_date_str} to {end_date_str}")
             return [] # Return empty list on parse error

        if start > end:
            print(f"Warning: Start date {start_date_str} is after end date {end_date_str}. No chunks generated.")
            return []

        date_ranges = []
        current_start = start

        while current_start <= end:
            if chunk_size == 'month':
                # Find the end of the current month
                month_end = (current_start.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                # Ensure chunk end doesn't exceed the overall end date
                chunk_end_date = min(month_end, end)
            elif isinstance(chunk_size, int) and chunk_size > 0:
                # Calculate end based on number of days
                chunk_end_date = min(current_start + timedelta(days=chunk_size - 1), end)
            else:
                 # Invalid chunk size, default to downloading the whole range as one chunk
                 print(f"Invalid chunk size '{chunk_size}', processing range as single chunk.")
                 chunk_end_date = end

            date_ranges.append((current_start.strftime('%Y-%m-%d'), chunk_end_date.strftime('%Y-%m-%d')))
            # Move to the next day after the current chunk ends
            current_start = chunk_end_date + timedelta(days=1)

            # Safety break for month logic if something goes wrong
            if chunk_size == 'month' and len(date_ranges) > 240: # Limit to 20 years of months
                print("Error: Exceeded maximum number of monthly chunks. Stopping.")
                break

        return date_ranges

    def _download_chunks_base(self, download_method, report_url, start_date, end_date, chunk_size, status_callback=None, **kwargs):
        """Base function to handle downloading in chunks."""
        if status_callback: status_callback(f"Splitting date range {start_date} to {end_date} with chunk size {chunk_size}.")
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        total_chunks = len(date_ranges)
        success_count = 0
        fail_count = 0

        if not date_ranges:
             message = f"Could not split date range {start_date} to {end_date} or range is invalid."
             if status_callback: status_callback(f"WARNING: {message}")
             else: print(message)
             return # Cannot proceed

        if status_callback: status_callback(f"Total chunks to process: {total_chunks}")

        for i, (from_date_chunk, to_date_chunk) in enumerate(date_ranges):
            chunk_num = i + 1
            if status_callback:
                status_callback(f"--- Starting Chunk {chunk_num}/{total_chunks}: {from_date_chunk} to {to_date_chunk} ---")

            try:
                # Call the specific download method passed as argument
                # Ensure the method accepts status_callback and **kwargs
                # Example: self.download_report_001(..., status_callback=status_callback)
                if download_method(report_url=report_url, from_date=from_date_chunk, to_date=to_date_chunk, status_callback=status_callback, **kwargs):
                     success_count += 1
                     if status_callback: status_callback(f"--- Completed Chunk {chunk_num}/{total_chunks} Successfully ---")
                else:
                     # Method returned False, indicating failure logged internally
                     fail_count += 1
                     if status_callback: status_callback(f"--- Completed Chunk {chunk_num}/{total_chunks} with FAILURE (Check Logs) ---")

            except DownloadFailedException as df_err: # Catch specific failure exception
                 fail_count += 1
                 error_msg = f"ERROR in Chunk {chunk_num}/{total_chunks} ({from_date_chunk} to {to_date_chunk}): DownloadFailed - {df_err}"
                 if status_callback: status_callback(error_msg)
                 # Logged internally by download_method, but log chunk failure here too
                 log_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), from_date_chunk, to_date_chunk, "Failed in Chunk", "", error_msg]
                 self.write_log_to_csv(log_data)
                 print(f"Continuing after caught DownloadFailedException: {error_msg}")
            except Exception as e:
                fail_count += 1
                error_msg = f"UNEXPECTED ERROR in Chunk {chunk_num}/{total_chunks} ({from_date_chunk} to {to_date_chunk}): {type(e).__name__} - {e}"
                if status_callback: status_callback(error_msg)
                traceback.print_exc() # Log full traceback for unexpected errors
                # Log unexpected chunk failure
                log_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), from_date_chunk, to_date_chunk, "Failed in Chunk (Unexpected)", "", error_msg]
                self.write_log_to_csv(log_data)
                print(f"Continuing after unexpected error: {error_msg}")
                # Consider stopping if errors are too frequent or critical

            finally:
                # --- Refresh or Pause between chunks ---
                # Avoid refreshing if it causes issues, maybe just pause
                if chunk_num < total_chunks: # Don't refresh after the last chunk
                    try:
                        if status_callback: status_callback("Pausing briefly before next chunk...")
                        time.sleep(SHORT_WAIT * 2) # Slightly longer pause
                        # Refresh can be unstable, only use if necessary
                        # if status_callback: status_callback("Refreshing page...")
                        # self.driver.refresh()
                        # self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput'))) # Wait for element after refresh
                        # if status_callback: status_callback("Page refreshed.")
                    except Exception as refresh_e:
                         if status_callback: status_callback(f"Warning: Error during pause/refresh between chunks: {refresh_e}")
                         # Continue anyway

        if status_callback:
             status_callback(f"Finished processing all {total_chunks} chunks. Success: {success_count}, Failed: {fail_count}.")

    # --- Public Chunking Methods (Called by app.py) ---

    def download_reports_in_chunks(self, report_url, start_date, end_date, chunk_size, status_callback=None):
        """Downloads generic reports in chunks."""
        self._download_chunks_base(self.download_generic_report, report_url, start_date, end_date, chunk_size, status_callback)

    def download_reports_in_chunks_1(self, report_url, start_date, end_date, chunk_size, status_callback=None):
        """Downloads FAF001 reports in chunks."""
        self._download_chunks_base(self.download_report_001, report_url, start_date, end_date, chunk_size, status_callback)

    def download_reports_in_chunks_4n(self, report_url, start_date, end_date, chunk_size, status_callback=None):
        """Downloads FAF004N reports in chunks."""
        self._download_chunks_base(self.download_report_004N, report_url, start_date, end_date, chunk_size, status_callback)

    def download_reports_in_chunks_4x(self, report_url, start_date, end_date, chunk_size, status_callback=None):
        """Downloads FAF004X reports in chunks."""
        self._download_chunks_base(self.download_report_004X, report_url, start_date, end_date, chunk_size, status_callback)

    # Add wrappers for _2, _3, _5, _6, _28 etc. using download_generic_report or specific methods if created
    def download_reports_in_chunks_2(self, report_url, start_date, end_date, chunk_size, status_callback=None):
         self._download_chunks_base(self.download_generic_report, report_url, start_date, end_date, chunk_size, status_callback)

    def download_reports_in_chunks_3(self, report_url, start_date, end_date, chunk_size, status_callback=None):
         self._download_chunks_base(self.download_generic_report, report_url, start_date, end_date, chunk_size, status_callback)

    # ... add similar wrappers for 5, 6, 28 ...

    def download_reports_for_all_regions(self, report_url, start_date, end_date, chunk_size, region_indices, status_callback=None):
        """Downloads region-specific reports in chunks for specified regions."""
        # Chunking happens *outside* the region loop for simplicity
        # Each chunk will iterate through the required regions.
        if status_callback: status_callback(f"Splitting date range {start_date} to {end_date} for region download.")
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        total_chunks = len(date_ranges)
        regions_to_process = [idx for idx in region_indices if idx in regions_data] # Validate indices

        if not date_ranges:
             message = f"Could not split date range {start_date} to {end_date} or range is invalid."
             if status_callback: status_callback(f"WARNING: {message}")
             return

        if not regions_to_process:
            if status_callback: status_callback("Warning: No valid region indices provided to process.")
            return

        if status_callback: status_callback(f"Total chunks: {total_chunks}, Regions per chunk: {len(regions_to_process)}")

        for i, (from_date_chunk, to_date_chunk) in enumerate(date_ranges):
            chunk_num = i + 1
            if status_callback:
                status_callback(f"--- Starting Chunk {chunk_num}/{total_chunks}: {from_date_chunk} to {to_date_chunk} ---")

            chunk_success_count = 0
            chunk_fail_count = 0
            for region_idx in regions_to_process:
                 region_name = regions_data[region_idx]['name']
                 if status_callback: status_callback(f"--- Processing Region: {region_name} (Index: {region_idx}) for Chunk {chunk_num} ---")
                 try:
                     # Call the region download method for this chunk and region
                     if self.download_report_for_region(report_url, from_date_chunk, to_date_chunk, region_idx, status_callback=status_callback):
                          chunk_success_count += 1
                     else:
                          chunk_fail_count += 1
                 except Exception as e:
                     chunk_fail_count += 1
                     error_msg = f"UNEXPECTED ERROR in Chunk {chunk_num}, Region {region_name}: {type(e).__name__} - {e}"
                     if status_callback: status_callback(error_msg)
                     traceback.print_exc()
                     # Log unexpected region failure within chunk
                     log_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), from_date_chunk, to_date_chunk, f"Failed in Chunk (Region: {region_name}, Unexpected)", "", error_msg]
                     self.write_log_to_csv(log_data)

                 finally:
                      # Pause briefly between regions within a chunk
                      if len(regions_to_process) > 1:
                           time.sleep(SHORT_WAIT)

            if status_callback:
                status_callback(f"--- Completed Chunk {chunk_num}/{total_chunks}. Success: {chunk_success_count}, Failed: {chunk_fail_count} regions ---")

        if status_callback:
            status_callback(f"Finished processing all chunks for selected regions.")


    # --- Cleanup Method ---
    def close(self):
        """Quits the WebDriver session."""
        if self.driver:
            try:
                print("Closing WebDriver session...")
                self.driver.quit() # Use quit() to close all windows and end the session gracefully
                print("WebDriver session closed.")
            except WebDriverException as e:
                print(f"Error closing WebDriver session: {e}")
            except Exception as e:
                 print(f"Unexpected error closing WebDriver session: {e}")
            finally:
                self.driver = None
                self.wait = None
        else:
             print("WebDriver session already closed or not initialized.")

# --- Custom Exception Class ---
class DownloadFailedException(Exception):
    """Custom exception for download failures after retries."""
    pass


# --- Standalone Functionality (Original - Seems separate from WebAutomation flow) ---
# This class seems designed for post-processing files already downloaded.
# It doesn't use the WebDriver instance. Keep it separate if needed,
# or integrate parts like renaming into WebAutomation if applicable.
# class Functionality:
#    def __init__(self, folder_path):
#        self.folder_path = folder_path
#    def extract_and_rename(self, startswith=None, endswith='.zip'):
#        # ... (Original implementation from snippet [168-176]) ...
#        pass