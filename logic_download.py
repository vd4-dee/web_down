#Import libary and function
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException
import os
import time
import pyotp # type: ignore
import random
import subprocess
import schedule # type: ignore
from datetime import datetime, timedelta
import zipfile
import shutil
import link_report
import calendar
import csv

# Định nghĩa lại từ điển vùng với tên khác, chẳng hạn regions_data
regions_data = {
    0: {"name": "HCM", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[1]/div/span[3]"},
    1: {"name": "HNi", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[2]/div/span[3]"},
    2: {"name": "Mdong", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[3]/div/span[3]"},
    3: {"name": "Mtay", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[4]/div/span[3]"},
    4: {"name": "MB2", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[5]/div/span[3]"},
    5: {"name": "Mtrung", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[6]/div/span[3]"},
    6: {"name": "MB1", "xpath": "/html/body/form/div[1]/div/div/ul/li/span[3]/div/ul/li/ul/li[7]/div/span[3]"}
}
# Lấy đường dẫn thư mục hiện tại nơi lưu trữ code
current_folder = os.path.dirname(os.path.abspath(__file__))

# Đường dẫn đầy đủ tới tệp tin CSV
csv_filename = os.path.join(current_folder, 'download_log.csv')

class WebAutomation:
    def __init__(self, driver_path, download_folder):
        self.driver_path = driver_path
        self.download_folder = download_folder
        
        chrome_options = webdriver.ChromeOptions()
        prefs = {'download.default_directory': self.download_folder}
        chrome_options.add_experimental_option('prefs', prefs)

        # Thêm các tùy chọn khởi động để tăng thời gian chờ của ChromeDriver
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-features=NetworkService')
        chrome_options.add_argument('--window-size=1920x1080')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--enable-automation')
        chrome_options.add_argument('--disable-infobars')
        #chrome_options.add_argument('--headless=new')
        #chrome_options.add_argument('--headless')  # Run headless to improve performance
        #chrome_options.page_load_strategy = 'eager'  # Load page with minimal resources

        self.service = Service(self.driver_path)
        self.driver = webdriver.Chrome(service=self.service, options=chrome_options)
         # Thiết lập thời gian chờ tải trang
        self.driver.set_page_load_timeout(100000)
        self.wait = WebDriverWait(self.driver, 60)
        self.before_download = self.get_files_in_folder()

    def get_files_in_folder(self):
        return os.listdir(self.download_folder)

    def wait_for_download_to_finish(self, timeout=100000, status_callback=None):
        """
        Waits for the download to complete by checking for '.crdownload' files
        and new files appearing in the download folder.
        Reports status via the callback function.
        """
        if status_callback:
            status_callback("Waiting for download file to appear and finalize...")

        end_time = time.time() + timeout
        initial_files = set(self.get_files_in_folder())
        last_check_output = "" # To avoid spamming the status log

        while True:
            time.sleep(5) # Check every 5 seconds

            crdownload_files = [f for f in self.get_files_in_folder() if f.endswith('.crdownload')]
            current_check_output = f"Checking download status... Found {len(crdownload_files)} '.crdownload' file(s)."

            # Only report status if it changes or periodically
            if current_check_output != last_check_output:
                if status_callback:
                    status_callback(current_check_output)
                last_check_output = current_check_output

            # Check if '.crdownload' files are gone
            if not crdownload_files:
                # Check if a new file has actually appeared compared to the initial state
                current_files = set(self.get_files_in_folder())
                if len(current_files - initial_files) > 0:
                    if status_callback:
                        status_callback("Download completed ('.crdownload' gone and new file detected).")
                    return True # Indicate success

            # Check for timeout
            if time.time() > end_time:
                timeout_message = "Download timed out waiting for file completion."
                if status_callback:
                    status_callback(f"ERROR: {timeout_message}")
                # Raise an exception to signal the failure clearly to the calling method
                raise TimeoutException(timeout_message)
                # break # Break is now unreachable due to raise, which is better

            # This part should ideally not be reached if timeout raises an exception
            return False # Indicate failure if loop somehow exits without success or timeout exception

    def rename_latest_file(self, from_date, to_date, suffix="", status_callback=None):
        """
        Renames the most recently downloaded file based on date range and suffix.
        Returns the new filename on success, None on failure or if no new file found.
        Reports status via callback.
        """
        if status_callback:
            status_callback("Checking for newly downloaded file to rename...")

        try:
            after_download = self.get_files_in_folder()
            # Find files present now that weren't present before the download started
            new_files = [f for f in after_download if f not in self.before_download and not f.endswith('.crdownload')]

            if not new_files:
                if status_callback:
                    status_callback("No new, completed file found to rename.")
                return None # Indicate no file was renamed

            # Find the most recently modified new file
            latest_file = max(new_files, key=lambda f: os.path.getmtime(os.path.join(self.download_folder, f)))
            file_name, file_extension = os.path.splitext(latest_file)
            original_full_path = os.path.join(self.download_folder, latest_file)

            if status_callback:
                status_callback(f"Found latest downloaded file: {latest_file}")

            # --- Date Formatting ---
            from_date_formatted = datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y%m%d')  # Standardized format
            to_date_formatted = datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y%m%d')      # Standardized format
            # --- End Date Formatting ---

            # Check if renaming should be skipped
            if file_name.startswith("BaoCaoFAF001"):
                if status_callback:
                    status_callback(f"Skipping rename for special report: {latest_file}")
                # Update before_download state even if not renamed, as the file is processed
                self.before_download = after_download
                return latest_file # Return original name as it's considered 'processed'

            # Construct the new name
            new_name = f"{file_name}_{from_date_formatted}_{to_date_formatted}{suffix}{file_extension}".replace(' ','_') # Replace spaces just in case
            new_full_path = os.path.join(self.download_folder, new_name)

            # Perform the rename
            if status_callback:
                status_callback(f"Attempting to rename '{latest_file}' to '{new_name}'")
            os.rename(original_full_path, new_full_path)

            if status_callback:
                status_callback(f"Successfully renamed file to: {new_name}")

            # Update the list of 'before' files for the next potential download
            self.before_download = after_download
            return new_name # <<< FIX: Return the new name on success

        except Exception as e:
            error_msg = f"Error during file renaming: {e}"
            if status_callback:
                status_callback(f"ERROR: {error_msg}")
            # Optionally log this error more formally if needed
            print(f"ERROR: {error_msg}") # Keep console log for critical errors
            return None # <<< FIX: Indicate failure by returning None

    def login(self, url, email, password, otp_code, status_callback=None):
        """Logs into the website using provided credentials and OTP code."""
        if status_callback:
            status_callback(f"Navigating to login page/report URL: {url}")
        try:
            self.driver.get(url)

            if status_callback:
                status_callback("Entering email...")
            email_input = self.wait.until(EC.element_to_be_clickable((By.ID, 'mat-input-3')))
            email_input.clear()
            email_input.send_keys(email)

            if status_callback:
                status_callback("Entering password...")
            password_input = self.wait.until(EC.element_to_be_clickable((By.ID, 'mat-input-4')))
            password_input.clear()
            password_input.send_keys(password)

            if status_callback:
                status_callback("Entering OTP code...")
            # <<< FIX: Use the 'otp_code' argument directly >>>
            otp_input = self.wait.until(EC.element_to_be_clickable((By.ID, 'mat-input-5')))
            otp_input.clear()
            otp_input.send_keys(otp_code)

            if status_callback:
                status_callback("Clicking login button...")
            login_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'kt_login_signin_submit')))
            login_button.click()

            # Add a small wait/check to ensure login is likely successful if possible
            time.sleep(3) # Simple wait, might need improvement
            if status_callback:
                status_callback("Login submitted. Assuming successful if no immediate error.")

        except Exception as e:
            if status_callback:
                status_callback(f"ERROR during login: {e}")
            # Re-raise the exception so it's caught in app.py
            raise e

    @staticmethod # Add this decorator as it doesn't use 'self'
    def create_download_folder(base_path): # <<< FIX: Added 'base_path' argument
        """Creates a dated download subfolder within the provided base path."""
        now = datetime.now()
        folder_name = now.strftime("001%Y%m%d")
        # Construct the full path using the provided base_path
        download_folder = os.path.join(base_path, folder_name) # <<< FIX: Use base_path argument

        # Create the directory if it doesn't exist
        os.makedirs(download_folder, exist_ok=True)

        return download_folder
        
    #     return date_ranges
    def split_date_range(self, start_date, end_date, chunk_size):
        """
        Splits a date range into smaller chunks based on the specified chunk size.
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')  # Standardized format
        end = datetime.strptime(end_date, '%Y-%m-%d')      # Standardized format

        # Điều chỉnh chunk_size nếu start_date = end_date
        if start == end:
            return [(start_date, end_date)]

        date_ranges = []

        while start <= end:
            if chunk_size == 'month':
                # Tính ngày đầu tiên của tháng tiếp theo
                next_month = start.replace(day=28) + timedelta(days=4)
                chunk_end = next_month - timedelta(days=next_month.day)

                # Nếu ngày cuối cùng của chunk vượt quá end_date, điều chỉnh lại
                if chunk_end > end:
                    chunk_end = end

                date_ranges.append((start.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))  # Standardized format
                start = chunk_end + timedelta(days=1)
            else:
                # Nếu chunk_size là số ngày cụ thể
                chunk_end = min(start + timedelta(days=chunk_size - 1), end)
                date_ranges.append((start.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))  # Standardized format
                start = chunk_end + timedelta(days=1)

        return date_ranges

    def extract_zip_files(self, status_callback=None):
        """
        Extracts newly downloaded zip files and reports status via callback.
        """
        if status_callback:
            status_callback("Checking for new zip files to extract...")

        after_download = self.get_files_in_folder()
        new_files = [f for f in after_download if f not in self.before_download and f.endswith('.zip')]

        for item in new_files:
            file_path = os.path.join(self.download_folder, item)
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(self.download_folder)
                if status_callback:
                    status_callback(f"Extracted: {item}")
            except Exception as e:
                if status_callback:
                    status_callback(f"ERROR extracting {item}: {e}")
                print(f"ERROR extracting {item}: {e}")

        # Update the list of files after extraction
        self.before_download = after_download

    def free_up_onedrive_space(self, folder):
        # Placeholder function: implement OneDrive API or command line utility for freeing up space
        print(f"Freeing up OneDrive space for folder: {folder}")
        # Example: os.system('path_to_onedrive_command_line_utility /freeup /path:folder')

    def rename_extracted_files(self, from_date, to_date, suffix="", status_callback=None):
        """
        Attempts to rename newly extracted files (non-zip) based on date range and suffix.
        Returns the name of the (last) renamed file, or None.
        Reports status via callback.
        NOTE: Logic for identifying extracted files might need refinement.
        """
        if status_callback:
            status_callback("Checking for newly extracted files to rename...")

        last_renamed_file = None # Keep track of the last file renamed in this call
        try:
            current_files = self.get_files_in_folder()
            # Attempt to identify potential extracted files:
            # Files present now, not present before extraction, and are NOT zip files.
            # This assumes self.before_download was updated *after* the zip was downloaded
            # but *before* extraction started, OR relies on extract_zip_files updating it correctly.
            extracted_candidates = [f for f in current_files if
                                    f not in self.before_download and
                                    not f.endswith('.zip') and
                                    not f.endswith('.crdownload')]

            if not extracted_candidates:
                if status_callback:
                    status_callback("No new, non-zip files found to rename (assumed extracted).")
                return None # Indicate no file was renamed

            if status_callback:
                status_callback(f"Found {len(extracted_candidates)} potential extracted file(s) to rename: {', '.join(extracted_candidates)}")

            # --- Date Formatting (same as rename_latest_file) ---
            from_date_formatted = datetime.strptime(from_date, '%Y-%m-%d').strftime('%Y%m%d')  # Standardized format
            to_date_formatted = datetime.strptime(to_date, '%Y-%m-%d').strftime('%Y%m%d')      # Standardized format
            # --- End Date Formatting ---

            processed_files_this_run = set() # Track files processed to update before_download accurately

            for extracted_file in extracted_candidates:
                original_full_path = os.path.join(self.download_folder, extracted_file)
                # Check if it's actually a file (skip directories if extraction created them)
                if not os.path.isfile(original_full_path):
                    continue

                file_name, file_extension = os.path.splitext(extracted_file)

                # Check if renaming should be skipped (e.g., specific filenames)
                if file_name.startswith("BaoCaoFAF001"): # Example skip condition
                    if status_callback:
                        status_callback(f"Skipping rename for special extracted file: {extracted_file}")
                    processed_files_this_run.add(extracted_file)
                    continue # Move to the next candidate

                # Construct the new name
                new_name = f"{file_name}_{from_date_formatted}_{to_date_formatted}{suffix}{file_extension}".replace(' ','_')
                new_full_path = os.path.join(self.download_folder, new_name)

                # Perform the rename
                if status_callback:
                    status_callback(f"Attempting to rename extracted file '{extracted_file}' to '{new_name}'")
                try:
                    os.rename(original_full_path, new_full_path)
                    if status_callback:
                        status_callback(f"Successfully renamed extracted file to: {new_name}")
                    last_renamed_file = new_name # Store the latest successful rename
                    processed_files_this_run.add(new_name) # Add the new name as processed
                except OSError as e:
                    if status_callback:
                        status_callback(f"ERROR renaming extracted file {extracted_file}: {e}")
                    processed_files_this_run.add(extracted_file) # Add original name if rename failed

            # Update before_download state more accurately
            # Add all files processed in this run (renamed or not) to the known state
            self.before_download = set(self.before_download) | processed_files_this_run


            if status_callback:
                status_callback("Finished processing extracted files.")

            return last_renamed_file # Return the name of the last successfully renamed file


        except Exception as e:
            error_msg = f"Error during extracted file renaming process: {e}"
            if status_callback:
                status_callback(f"ERROR: {error_msg}")
            print(f"ERROR: {error_msg}") # Keep console log
            return None # Indicate failure

    def write_log_to_csv(log_data, csv_filename= csv_filename):
        # Tạo tiêu đề cho file log nếu nó chưa tồn tại
        try:
            with open(csv_filename, 'a', newline='') as file:
                writer = csv.writer(file)
                
                # Nếu file trống, ghi tiêu đề
                if file.tell() == 0:
                    writer.writerow(["Timestamp", "Start Date", "End Date", "Status", "File Name", "Error Message"])
                
                # Ghi dữ liệu log vào file
                writer.writerow(log_data)
        except Exception as e:
            print(f"Error writing log to CSV: {e}")

    # <<< FIX: Added status_callback=None >>>
    def download_report(self, report_url, from_date, to_date, status_callback=None):
        """Downloads a single report for a given date range, handling file operations."""
        if status_callback:
            status_callback(f"Navigating to report URL: {report_url}")
        self.driver.get(report_url)

        log_file_name = "" # Initialize log file name
        log_status = "Failed" # Default status
        log_error = "" # Initialize error message

        try:
            if status_callback: status_callback("Waiting for page to load...")
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')

            # Enter the end date
            if status_callback: status_callback(f"Setting 'To Date': {to_date}")
            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            # Enter the start date
            if status_callback: status_callback(f"Setting 'From Date': {from_date}")
            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            # Click the download button
            if status_callback: status_callback("Clicking download button...")
            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportCSVDemo_input')))
            download_button.click()

            # Wait for the download to finish
            if status_callback: status_callback("Waiting for download to complete...")
            # Pass callback if wait_for_download_to_finish is modified, otherwise remove it from this call
            self.wait_for_download_to_finish(status_callback=status_callback)

            # Rename and extract files
            # <<< FIX: Pass status_callback down to these methods >>>
            # (Requires modifying their definitions too!)
            if status_callback: status_callback("Renaming downloaded file...")
            log_file_name = self.rename_latest_file(from_date, to_date, status_callback=status_callback) or "Rename Failed"

            if status_callback: status_callback("Extracting zip files (if any)...")
            self.extract_zip_files(status_callback=status_callback) # Keep track of extracted names if needed

            if status_callback: status_callback("Renaming extracted files (if any)...")
            # This might need more logic if extract_zip_files extracts multiple files
            extracted_file_name = self.rename_extracted_files(from_date, to_date, status_callback=status_callback)
            if extracted_file_name and log_file_name != "Rename Failed": # Log extracted name if successful
                log_file_name = extracted_file_name


            # Allow time for file system operations
            time.sleep(3)

            # Check if a new file (potentially renamed) exists
            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]

            if new_files or log_file_name != "Rename Failed": # Consider download successful if rename worked
                log_status = "Success"
                if status_callback:
                    status_callback(f"Successfully processed download for {from_date} to {to_date}. File: {log_file_name}")
                # Update before_download list only on success?
                self.before_download = after_download
            else:
                log_error = "No new file detected after download attempt."
                if status_callback: status_callback(f"WARNING: {log_error}")


        except UnexpectedAlertPresentException as e:
            alert = self.driver.switch_to.alert
            log_error = f"Alert Present: {alert.text}"
            if status_callback: status_callback(f"ERROR: {log_error}")
            try:
                alert.accept()
                if status_callback: status_callback("Accepted alert.")
            except Exception as accept_err:
                if status_callback: status_callback(f"Error accepting alert: {accept_err}")

        except TimeoutException as te:
            log_error = f"Timeout Error: {te}"
            if status_callback: status_callback(f"ERROR: {log_error}")

        except Exception as e:
            log_error = f"General Error: {str(e)}"
            if status_callback: status_callback(f"ERROR: {log_error}")
            # Optionally print traceback to console for debugging
            # import traceback
            # traceback.print_exc()

        finally:
            # Log the result to CSV
            try:
                log_data = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), from_date, to_date, log_status, log_file_name, log_error]
                # Assuming write_log_to_csv is a static method or correctly defined elsewhere
                WebAutomation.write_log_to_csv(log_data)
                if status_callback: status_callback(f"Logged status '{log_status}' for {from_date}-{to_date}.")
            except Exception as log_e:
                error_msg = f"CRITICAL: Failed to write log to CSV: {log_e}"
                if status_callback: status_callback(error_msg)
                print(error_msg) # Print critical log error to console

    def select_region(self, region_index):
        try:
            # Kiểm tra nếu index có trong từ điển
            if region_index < len(regions_data):
                region = regions_data[region_index]
                xpath = region["xpath"]
                region_name = region["name"]

                # Chờ phần tử có sẵn và click vào
                region_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                region_element.click()
                
                print(f"Selected region '{region_name}' (Index: {region_index}) with XPath: {xpath}")
                time.sleep(1)  # Thêm thời gian chờ ngắn giữa các lần click
                
            else:
                print(f"Invalid region index: {region_index}. Valid indices are from 0 to {len(regions_data) - 1}.")

        except TimeoutException:
            print(f"Timeout waiting for element at XPath: {regions_data.get(region_index, {}).get('xpath', 'Unknown XPath')}")
        except Exception as e:
            print(f"Error selecting region at index {region_index}: {e}")


    def download_report_for_region(self, report_url, from_date, to_date, region_index, region_name):
        try:
            self.driver.get(report_url)
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')

            # Nhập ngày tháng
            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            # Mở TreeShopThuoc và chọn vùng
            TreeShopThuoc = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_TreeShopThuoc1_cboDepartmentsThuoc_Arrow')))
            TreeShopThuoc.click()

            TreeShopThuoc_rtPlus = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'rtPlus')))
            TreeShopThuoc_rtPlus.click()

            # Chọn vùng hiện tại
            self.select_region(region_index)

            # Tìm phần tử có chứa văn bản cụ thể và click vào nó
            element = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Báo Cáo Nhập Xuất Tồn FAF')]")))
            element.click()
            
            # Nhấn nút tải xuống
            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportExcel_input')))
            download_button.click()

            # Chờ tải xuống hoàn tất và xử lý tệp tin
            self.wait_for_download_to_finish()
            self.rename_latest_file(from_date, to_date, region_name)
            self.extract_zip_files()
            self.rename_extracted_files(from_date, to_date, region_name)

            time.sleep(5)

            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]
            if new_files:
                print(f"The new file has been downloaded: {new_files[0]}")
                self.before_download = after_download  # Cập nhật danh sách before_download

        except Exception as e:
            print(f"An error occurred while downloading report for region: {str(e)}")

    # def download_reports_for_all_regions(self, report_url, from_date, to_date):
    #     for region_index in range(len(regions_data)):  # Duyệt qua tất cả các vùng trong regions_data
    #         region_name = regions_data[region_index]["name"]  # Lấy tên vùng tương ứng
    #         print(f"Starting download for region {region_index + 1} ({region_name})...")

    #         # Gọi hàm tải báo cáo cho từng vùng, truyền thêm region_index và region_name
    #         self.download_report_for_region(report_url, from_date, to_date, region_index, region_name)

    def download_reports_for_all_regions(self, report_url, from_date, to_date, region_indices=None):
        if region_indices is not None:
            # Nếu region_indices được truyền vào, chỉ tải báo cáo cho các vùng đó
            for region_index in region_indices:
                if region_index < len(regions_data):
                    region_name = regions_data[region_index]["name"]
                    print(f"Starting download for region {region_index + 1} ({region_name})...")
                    self.download_report_for_region(report_url, from_date, to_date, region_index, region_name)
                else:
                    print(f"Invalid region index: {region_index}. Valid indices are from 0 to {len(regions_data) - 1}.")
        else:
            # Nếu không có region_indices, duyệt qua tất cả các vùng
            for region_index in range(len(regions_data)):
                region_name = regions_data[region_index]["name"]
                print(f"Starting download for region {region_index + 1} ({region_name})...")
                self.download_report_for_region(report_url, from_date, to_date, region_index, region_name)
                
    # Use with report id = 030
    def download_report_030(self, report_url, from_date, to_date, region_index):
        self.driver.get(report_url)
        
        try:
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            TreeShopThuoc = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_TreeShopThuoc1_cboDepartmentsThuoc_Arrow')))
            TreeShopThuoc.click()

            TreeShopThuoc_rtPlus = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'rtPlus')))
            TreeShopThuoc_rtPlus.click()

            # Chọn các vùng
            self.select_region()

            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportExcel_input')))
            download_button.click()

            self.wait_for_download_to_finish()
            self.rename_latest_file(from_date, to_date)
            self.extract_zip_files()
            self.rename_extracted_files(from_date, to_date)

            time.sleep(5)

            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]
            if new_files:
                print("The new file has been downloaded:", new_files[0])
                # Cập nhật danh sách before_download
                self.before_download = after_download  

        except UnexpectedAlertPresentException as e:
            alert = self.driver.switch_to.alert
            print(f"Alert Text: {alert.text}")
            alert.accept()
            print("Close the alert and try again.")

        except TimeoutException as te:
            print("TimeoutException:", te)


    # Use with report id = 001
    def download_report_001(self, report_url , from_date, to_date):
        self.driver.get(report_url)
    
        try:
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            radio_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_rblType_1')))
            radio_button.click()            

            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportCSVDemo_input')))
            download_button.click()

            self.wait_for_download_to_finish()
            self.extract_zip_files()

            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]
            if new_files:
                print("The new file has been downloaded:", new_files[0])
                self.before_download = after_download  # Cập nhật danh sách before_download

        except UnexpectedAlertPresentException as e:
            alert = self.driver.switch_to.alert
            print(f"Alert Text: {alert.text}")
            alert.accept()
            print("Close the alert and try again.")

        except TimeoutException as te:
            print("TimeoutException:", te)

    # Use with report id = 004N
    def download_report_004N(self, report_url, from_date, to_date):
        self.driver.get(report_url)
    
        try:
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            radio_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_rblType_1')))
            radio_button.click()            

            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportCSVDemo_input')))
            download_button.click()

            self.wait_for_download_to_finish()
            self.rename_latest_file(from_date, to_date, "N")
            self.extract_zip_files()
            self.rename_extracted_files(from_date, to_date, "N")

            time.sleep(5)
        
            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]
            if new_files:
                print("The new file has been downloaded:", new_files[0])
                self.before_download = after_download  # Cập nhật danh sách before_download

        except UnexpectedAlertPresentException as e:
            alert = self.driver.switch_to.alert
            print(f"Alert Text: {alert.text}")
            alert.accept()
            print("Close the alert and try again.")
        except TimeoutException as te:
            print("TimeoutException:", te)

    # Use with report id = 004X
    def download_report_004X(self, report_url, from_date, to_date):
        self.driver.get(report_url)
    
        try:
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            radio_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_rblType_0')))
            radio_button.click()            

            edate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_toDate_dateInput')))
            edate.clear()
            edate.send_keys(to_date)

            sdate = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_cbo_fromDate_dateInput')))
            sdate.clear()
            sdate.send_keys(from_date)

            download_button = self.wait.until(EC.element_to_be_clickable((By.ID, 'ctl00_MainContent_btnExportCSVDemo_input')))
            download_button.click()

            self.wait_for_download_to_finish()
            self.rename_latest_file(from_date, to_date, "X")
            self.extract_zip_files()
            self.rename_extracted_files(from_date, to_date, "X")
            
            time.sleep(5)
        
            after_download = self.get_files_in_folder()
            new_files = [f for f in after_download if f not in self.before_download]
            if new_files:
                print("The new file has been downloaded:", new_files[0])
                self.before_download = after_download  # Cập nhật danh sách before_download

        except UnexpectedAlertPresentException as e:
            alert = self.driver.switch_to.alert
            print(f"Alert Text: {alert.text}")
            alert.accept()
            print("Close the alert and try again.")

        except TimeoutException as te:
            print("TimeoutException:", te)

    # <<< FIX: Added status_callback=None >>>
    def download_reports_in_chunks(self, report_url, start_date, end_date, chunk_size, status_callback=None):
        """Downloads reports in chunks using the generic download_report method."""
        if status_callback:
            status_callback(f"Splitting date range {start_date} to {end_date} with chunk size {chunk_size}.")
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)

        if date_ranges:
            total_chunks = len(date_ranges)
            for i, (from_date, to_date) in enumerate(date_ranges):
                chunk_num = i + 1
                if status_callback:
                    status_callback(f"--- Starting Chunk {chunk_num}/{total_chunks}: {from_date} to {to_date} ---")

                try:
                    # <<< FIX: Pass status_callback to the actual download method >>>
                    # (Assumes download_report is also modified to accept status_callback)
                    self.download_report(report_url, from_date, to_date, status_callback=status_callback)

                    if status_callback:
                        status_callback(f"--- Completed Chunk {chunk_num}/{total_chunks} ---")

                except Exception as e:
                    error_msg = f"ERROR in Chunk {chunk_num}/{total_chunks} ({from_date} to {to_date}): {e}"
                    if status_callback:
                        status_callback(error_msg)
                    # Decide if you want to stop on error or continue with next chunk
                    # For now, it continues. Add 'raise e' here if you want to stop.
                    print(f"Continuing after error: {error_msg}") # Log to console too

            if status_callback:
                status_callback(f"Finished processing all {total_chunks} chunks.")

        else:
            message = f"Could not split date range {start_date} to {end_date}."
            if status_callback:
                status_callback(f"WARNING: {message}")
            else: # Fallback print if no callback
                print(message)

        # Refresh logic
        try:
            if status_callback: status_callback("Refreshing browser page...")
            self.driver.refresh()
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            if status_callback: status_callback("Page refreshed.")
        except Exception as e:
            if status_callback: status_callback(f"Error during page refresh: {e}")

    def download_reports_in_chunks_1(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report_001(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_2(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_3(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_4n(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report_004N(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_4x(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report_004X(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_5(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_6(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_28(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")

    def download_reports_in_chunks_30(self, report_url, start_date, end_date, chunk_size):
        date_ranges = self.split_date_range(start_date, end_date, chunk_size)
        if date_ranges:
            for from_date, to_date in date_ranges:
                print(f"Download the report from {from_date} to {to_date}")
                self.download_report_030(report_url, from_date, to_date)
                # Chờ trang tải lại hoàn toàn trước khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
                self.driver.refresh()
                # Chờ trang tải lại hoàn toàn sau khi refresh
                self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        else:
            print("Could not find a valid date range to download the report.")
    

    def close(self):
        self.driver.quit()

class Functionality:
    def __init__(self, folder_path):
        """
        Khởi tạo đối tượng với đường dẫn thư mục làm việc.
        
        :param folder_path: Đường dẫn đến thư mục chứa file .zip
        """
        self.folder_path = folder_path

    def extract_and_rename(self, startswith=None, endswith='.zip'):
        """
        Giải nén tất cả các file .zip trong thư mục được chỉ định,
        sau đó đổi tên các file mới được giải nén dựa trên tên file .zip.
        # Chỉ định thư mục chứa file .zip
        custom_folder = "/path/to/your/folder"

        # Khởi tạo đối tượng ZipFileHandler
        handler = ZipFileHandler(custom_folder)

        # Gọi phương thức để giải nén và đổi tên file
        handler.extract_and_rename()
        """
        # Lấy danh sách tất cả các file trong thư mục
        files = [f for f in os.listdir(self.folder_path) if os.path.isfile(os.path.join(self.folder_path, f))]

        # Lọc ra các file .zip
        zip_files = [f for f in files if f.startswith(startswith) and f.endswith(endswith)]

        for zip_file in zip_files:
            # Đường dẫn đầy đủ của file .zip
            zip_file_path = os.path.join(self.folder_path, zip_file)

            # Tên file .zip (không bao gồm phần đuôi .zip)
            base_name = os.path.splitext(zip_file)[0]

            # Giải nén file .zip
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                extracted_files = zip_ref.namelist()  # Lấy danh sách các file được giải nén
                zip_ref.extractall(self.folder_path)
            print(f"Extracted: {zip_file}")

            # Đổi tên các file mới được giải nén
            for extracted_file in extracted_files:
                old_path = os.path.join(self.folder_path, extracted_file)
                if os.path.isfile(old_path):  # Chỉ xử lý file, không xử lý thư mục
                    _, ext = os.path.splitext(extracted_file)
                    new_name = f"{base_name}{ext}"  # Tạo tên file mới dựa trên tên file .zip
                    new_path = os.path.join(self.folder_path, new_name)

                    # Đảm bảo tên file mới không bị trùng lặp
                    counter = 1
                    while os.path.exists(new_path):
                        new_name = f"{base_name}_{counter}{ext}"
                        new_path = os.path.join(self.folder_path, new_name)
                        counter += 1

                    # Đổi tên file
                    os.rename(old_path, new_path)
                    print(f"Renamed file to: {new_name}")