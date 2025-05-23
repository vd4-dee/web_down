# filename: app.py
import flask # type: ignore
from flask import Flask, render_template, request, jsonify, Response # type: ignore
import threading
import time
import csv
import os
import pyotp # type: ignore
from datetime import datetime, timezone, timedelta
import pandas as pd # type: ignore
import json
import traceback
import atexit
from selenium.common.exceptions import WebDriverException

# Scheduling Imports
from apscheduler.schedulers.background import BackgroundScheduler # type: ignore
from apscheduler.jobstores.memory import MemoryJobStore # type: ignore
from apscheduler.triggers.date import DateTrigger # type: ignore
from apscheduler.executors.pool import ThreadPoolExecutor # type: ignore
from apscheduler.jobstores.base import JobLookupError # type: ignore

# Local Imports
import config
from logic_download import WebAutomation, regions_data, DownloadFailedException # Import custom exception
import link_report

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Đặt secret key cho session/flash

# --- Import Google Sheet Auth ---
from auth_google_sheet import is_user_allowed

# --- Register Blueprints ---
from blueprints.auth import auth_bp
from blueprints.main import main_bp
from blueprints.download import download_bp
from blueprints.email import email_bp
from blueprints.schedule import schedule_bp
from blueprints.config_mgmt import config_bp
from blueprints.sse import sse_bp

app.register_blueprint(auth_bp)  # /login, /logout, /change_password
app.register_blueprint(main_bp)  # /
app.register_blueprint(download_bp)  # /download/
app.register_blueprint(email_bp)  # /email/
app.register_blueprint(schedule_bp)  # /schedule/
app.register_blueprint(config_bp)  # /api/config
app.register_blueprint(sse_bp)    # /stream-status

# Constants
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'configs.json')
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'logs', 'download_log.csv')

# --- Ensure log file exists with header ---
def ensure_log_file():
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write('SessionID,Timestamp,File Name,Start Date,End Date,Status,Error Message\n')

ensure_log_file()

# Global state (import từ globals)
from globals import status_messages, is_running, download_thread, lock

# Scheduler Setup
jobstores = {'default': MemoryJobStore()}
executors = {'default': ThreadPoolExecutor(2)} # Reduced pool size for sequential stability
job_defaults = {'coalesce': True, 'max_instances': 1}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone=timezone.utc)

# Utility Functions
def load_configs():
    """Loads configurations safely."""
    if not os.path.exists(CONFIG_FILE_PATH): return {}
    try:
        with lock: # Lock for reading consistency (optional but safer)
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: return {}
                return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading config file {CONFIG_FILE_PATH}: {e}")
        return {}

def save_configs(configs):
    """Saves configurations safely."""
    try:
        with lock: # Lock is crucial for writing
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving config file {CONFIG_FILE_PATH}: {e}")

def stream_status_update(message):
    """Adds a message to the status list for SSE."""
    global status_messages
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"{timestamp}: {message}"
    print(full_message) # Log to console
    with lock:
        status_messages.append(full_message)
        MAX_LOG_MESSAGES = 500
        if len(status_messages) > MAX_LOG_MESSAGES:
            status_messages = status_messages[-MAX_LOG_MESSAGES:]


# --- Download Process Function ---
from logic_download import run_download_process
def run_download_process(params):
    """Main download function executed in a background thread."""
    global is_running, status_messages
    automation = None
    process_successful = True # Assume success initially

    # --- Setup within Lock ---
    with lock:
        if is_running: # Double check inside lock
             print("Download process already running, exiting new thread request.")
             # Cannot easily send status back from here, rely on API response
             return
        is_running = True
        status_messages = [] # Clear logs for this run

    stream_status_update("Starting report download process...")

    try:
        # --- Extract Parameters ---
        # These are guaranteed by validation in handle_start_download or loaded config structure
        email = params['email']
        password = params['password']
        # 'reports' is expected to be a LIST of DICTIONARIES
        reports_to_download = params.get('reports', [])
        # 'regions' is expected to be a list of strings (indices)
        selected_regions_indices_str = params.get('regions', [])

        if not reports_to_download:
            raise ValueError("No reports configured for download.")

        # --- Prepare Download Folder ---
        # timestamp_folder = datetime.now().strftime("%Y%m%d")
        timestamp_folder = "001" + datetime.now().strftime("%Y%m%d")
        specific_download_folder = os.path.join(config.DOWNLOAD_BASE_PATH, timestamp_folder)
        try:
            os.makedirs(specific_download_folder, exist_ok=True)
            stream_status_update(f"Download folder for this run: {specific_download_folder}")
        except OSError as e:
            raise RuntimeError(f"Failed to create download directory '{specific_download_folder}': {e}")

        # --- Initialize Automation ---
        stream_status_update("Initializing browser automation...")
        # Pass status callback to WebAutomation constructor
        automation = WebAutomation(config.DRIVER_PATH, specific_download_folder, status_callback=stream_status_update)

        # --- Login ---
        stream_status_update(f"Logging in with user: {email}...")
        # Use first report's URL for login initiation
        first_report_info = reports_to_download[0]
        first_report_url = link_report.get_report_url(first_report_info.get('report_type'))
        if not first_report_url:
            raise ValueError(f"Could not find URL for initial report type '{first_report_info.get('report_type')}' needed for login.")
        if not config.OTP_SECRET:
            raise ValueError("OTP_SECRET is not configured.")

        if not automation.login(first_report_url, email, password, config.OTP_SECRET, status_callback=stream_status_update):
            raise RuntimeError("Login failed after multiple attempts. Cannot proceed.")
        stream_status_update("Login successful.")

        # --- Download Reports Loop ---
        # Iterate through the list of report dictionaries
        for report_info in reports_to_download:
            report_type_key = report_info.get('report_type')
            from_date = report_info.get('from_date')
            to_date = report_info.get('to_date')
            chunk_size_str = report_info.get('chunk_size', '5') # Default to '5' if missing

            # Validate essential info for this report
            if not all([report_type_key, from_date, to_date]):
                 stream_status_update(f"Warning: Skipping report entry due to missing info: {report_info}")
                 process_successful = False # Mark partial failure
                 continue

            # Validate and parse chunk_size
            chunk_size = 5 # Default
            try:
                if isinstance(chunk_size_str, str) and chunk_size_str.lower() == 'month':
                    chunk_size = 'month'
                elif chunk_size_str:
                    chunk_size_days = int(chunk_size_str)
                    chunk_size = chunk_size_days if chunk_size_days > 0 else 5
                # If chunk_size_str is empty or None, default 5 is kept
            except (ValueError, TypeError):
                stream_status_update(f"Warning: Invalid chunk size '{chunk_size_str}' for '{report_type_key}'. Using default: 5 days.")
                chunk_size = 5

            # Get report URL
            report_url = link_report.get_report_url(report_type_key)
            if not report_url:
                stream_status_update(f"Error: Could not find URL for report type '{report_type_key}'. Skipping.")
                process_successful = False
                continue

            stream_status_update(f"--- Starting download for report: {report_type_key} ---")
            stream_status_update(f"Date Range: {from_date} to {to_date}, Chunk Size/Mode: {chunk_size}")

            report_failed = False
            try:
                # --- Determine Download Method ---
                if report_url in config.REGION_REQUIRED_REPORT_URLS:
                    if not selected_regions_indices_str:
                        stream_status_update(f"Error: Report '{report_type_key}' requires region selection, but none provided. Skipping.")
                        report_failed = True
                    else:
                        try:
                            selected_regions_indices_int = [int(idx) for idx in selected_regions_indices_str]
                            region_names = [regions_data[i]['name'] for i in selected_regions_indices_int if i in regions_data]
                            stream_status_update(f"Downloading '{report_type_key}' for regions: {', '.join(region_names)}")

                            if hasattr(automation, 'download_reports_for_all_regions'):
                                # Call the multi-region chunking method
                                automation.download_reports_for_all_regions(
                                    report_url, from_date, to_date, chunk_size,
                                    region_indices=selected_regions_indices_int,
                                    status_callback=stream_status_update
                                )
                            else:
                                stream_status_update("ERROR: 'download_reports_for_all_regions' method missing.")
                                report_failed = True
                        except (ValueError, TypeError, KeyError) as region_err:
                            stream_status_update(f"Error processing region indices for '{report_type_key}': {region_err}. Skipping.")
                            report_failed = True
                # Report-specific chunking methods
                elif report_type_key == "FAF001 - Sales Report" and hasattr(automation, 'download_reports_in_chunks_1'):
                    automation.download_reports_in_chunks_1(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF004N - Internal Rotation Report (Imports)" and hasattr(automation, 'download_reports_in_chunks_4n'):
                     automation.download_reports_in_chunks_4n(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF004X - Internal Rotation Report (Exports)" and hasattr(automation, 'download_reports_in_chunks_4x'):
                     automation.download_reports_in_chunks_4x(report_url, from_date, to_date, chunk_size, stream_status_update)
                # Add elif for other specific reports (2, 3, 5, 6, 28) mapped to generic or specific methods
                elif report_type_key == "FAF002 - Dosage Report" and hasattr(automation, 'download_reports_in_chunks_2'):
                     automation.download_reports_in_chunks_2(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF003 - Report Of Other Imports And Exports" and hasattr(automation, 'download_reports_in_chunks_3'):
                     automation.download_reports_in_chunks_3(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF005 - Detailed Report Of Imports" and hasattr(automation, 'download_reports_in_chunks_5'):
                     automation.download_reports_in_chunks_5(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF006 - Supplier Return Report" and hasattr(automation, 'download_reports_in_chunks_6'):
                     automation.download_reports_in_chunks_6(report_url, from_date, to_date, chunk_size, stream_status_update)
                elif report_type_key == "FAF028 - Detailed Import - Export Transaction Report" and hasattr(automation, 'download_reports_in_chunks_28'):
                     automation.download_reports_in_chunks_28(report_url, from_date, to_date, chunk_size, stream_status_update)
                # Generic fallback chunking method
                elif hasattr(automation, 'download_reports_in_chunks'):
                    stream_status_update(f"Using generic chunking download logic for '{report_type_key}'.")
                    automation.download_reports_in_chunks(report_url, from_date, to_date, chunk_size, stream_status_update)
                else:
                    stream_status_update(f"ERROR: No suitable download method found for report type '{report_type_key}'. Skipping.")
                    report_failed = True

            # --- Catch Errors During Report Download ---
            except DownloadFailedException as report_err: # Specific download failure
                 stream_status_update(f"ERROR downloading report {report_type_key}: {report_err}")
                 report_failed = True
                 # traceback.print_exc() # Optional: log traceback for specific failures too
            except WebDriverException as wd_err:
                 stream_status_update(f"ERROR (WebDriver) during download of {report_type_key}: {wd_err}")
                 report_failed = True
                 traceback.print_exc()
                 # If session becomes invalid, stop processing further reports in this run
                 if "invalid session id" in str(wd_err).lower():
                     stream_status_update("FATAL: Session invalid. Stopping further report downloads for this run.")
                     process_successful = False
                     break # Exit the reports loop
            except Exception as generic_err:
                 stream_status_update(f"FATAL UNEXPECTED ERROR during processing of {report_type_key}: {generic_err}")
                 report_failed = True
                 traceback.print_exc()
                 # Consider stopping for unexpected errors too
                 # break

            # --- Report Completion Status ---
            if report_failed:
                process_successful = False # Mark overall process as failed
                stream_status_update(f"--- Download FAILED for report: {report_type_key} ---")
            else:
                stream_status_update(f"--- Download COMPLETED for report: {report_type_key} ---")
        # --- End of Reports Loop ---

    except (RuntimeError, ValueError, WebDriverException) as setup_err:
        error_message = f"A critical error occurred during setup or login: {setup_err}"
        stream_status_update(f"FATAL ERROR: {error_message}")
        traceback.print_exc()
        process_successful = False
    except Exception as e:
        error_message = f"An unexpected critical error occurred: {e}"
        stream_status_update(f"FATAL ERROR: {error_message}")
        traceback.print_exc()
        process_successful = False

    finally:
        # --- Cleanup ---
        if automation:
            try:
                stream_status_update("Attempting to close browser...")
                automation.close()
                # stream_status_update("Browser closed.") # Already logged in close()
            except Exception as close_e:
                stream_status_update(f"CRITICAL ERROR: Failed to close browser session properly: {close_e}")
                traceback.print_exc()

        # --- Final Status ---
        final_message = "PROCESS FINISHED: "
        final_message += "All requested reports attempted."
        if not process_successful:
             final_message += " One or more errors occurred. Please review logs and CSV file."
        else:
             final_message += " Check logs and CSV file for individual report status."
        stream_status_update(f"--- {final_message} ---")

        # Reset running state
        with lock:
            is_running = False
            # download_thread = None # Optional: clear thread variable

# --- Function Called by Scheduler ---
def trigger_scheduled_download(config_name):
    """Loads a saved configuration and starts the download process."""
    print(f"Scheduler attempting job for config: {config_name}")
    global is_running

    with lock:
        if is_running:
            print(f"Scheduler: Download process already running. Skipping job for '{config_name}'.")
            return
        # No need to set is_running=True here; run_download_process does it

    configs = load_configs()
    params = configs.get(config_name)

    if not params:
        print(f"Scheduler: Configuration '{config_name}' not found.")
        return

    # Validate essential keys in the loaded config structure
    required_keys = ['email', 'password', 'reports'] # Regions is optional
    if not all(key in params for key in required_keys) or not isinstance(params['reports'], list):
         print(f"Scheduler: Config '{config_name}' missing required keys or 'reports' is not a list.")
         return
    if not params['reports']: # Check if reports list is empty
        print(f"Scheduler: Config '{config_name}' has no reports defined.")
        return

    print(f"Scheduler: Starting download thread for config '{config_name}'...")
    thread_params = params.copy() # Pass a copy
    scheduled_thread = threading.Thread(target=run_download_process, args=(thread_params,))
    scheduled_thread.daemon = True
    scheduled_thread.start()

# --- Flask Routes REMOVED: All routes moved to blueprints. ---
# from auth_google_sheet import is_user_allowed
# from flask import session, flash, redirect, url_for

# --- All authentication routes moved to blueprints/auth.py ---

# --- Download, schedule, history, and settings routes moved to blueprints/download.py and blueprints/schedule.py ---

# --- Email and history routes moved to blueprints/email.py ---

# --- User manuals route moved to blueprints/main.py or blueprints/download.py as needed ---

# --- Logout route moved to blueprints/auth.py ---

# --- Main dashboard route moved to blueprints/main.py ---

# --- API endpoint for reports/regions moved to blueprints/download.py ---

# --- Download start API moved to blueprints/download.py ---


# --- SSE stream-status route moved to blueprints/sse.py ---


@app.route('/get-logs', methods=['GET'])
def get_download_logs():
    """Reads and returns the download log file content."""
    logs_data = []
    status_code = 200
    response_status = 'success'
    message = ''

    if not os.path.exists(LOG_FILE_PATH):
        message = 'Log file does not exist yet.'
        response_status = 'warning'
    else:
        try:
            # Use low_memory=False for potentially mixed types if needed
            df = pd.read_csv(LOG_FILE_PATH, dtype=str, keep_default_na=False, na_values=[''], on_bad_lines='warn')
            df = df.fillna('') # Replace any remaining NaN with empty string
            logs_data = df.to_dict('records')

            if 'Timestamp' in df.columns and not df.empty:
                try:
                    df['TimestampParsed'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                    df_sorted = df.sort_values(by='TimestampParsed', ascending=False, na_position='last')
                    logs_data = df_sorted.drop(columns=['TimestampParsed']).to_dict('records')
                except Exception as sort_err:
                   print(f"Could not sort logs by timestamp: {sort_err}")

            if not logs_data:
                message = 'Log file is empty.'
        except pd.errors.EmptyDataError:
            message = 'Log file is empty.'
            response_status = 'warning' # Empty is not an error
        except Exception as e:
            print(f"Error reading or processing log file: {e}")
            traceback.print_exc()
            response_status = 'error'
            message = f'Error reading log file: {e}'
            status_code = 500

    return jsonify({'status': response_status, 'message': message, 'logs': logs_data}), status_code

# --- Configuration Endpoints ---
# --- Config management API routes moved to blueprints/config_mgmt.py ---

# --- Scheduling API Endpoints ---
# --- Schedule management API routes moved to blueprints/schedule.py ---

# --- Main Execution ---
if __name__ == '__main__':
    # Initial Setup
    try:
        os.makedirs(config.DOWNLOAD_BASE_PATH, exist_ok=True)
    except OSError as e:
        print(f"CRITICAL ERROR: Could not create base download directory '{config.DOWNLOAD_BASE_PATH}': {e}")
        exit(1)
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"Configuration file not found at {CONFIG_FILE_PATH}. Creating empty file.")
        save_configs({})

    # Start Scheduler
    if not scheduler.running:
        try:
            scheduler.start(paused=False) # Start immediately
            print("APScheduler started successfully.")
            atexit.register(lambda: scheduler.shutdown())
            print("Registered APScheduler shutdown hook.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to start APScheduler: {e}")
            traceback.print_exc()
            # exit(1) # Exit if scheduler is critical

    # Run Flask App
    print("Starting Flask application...")
    HOST = '127.0.0.1'
    PORT = 5000
    # Use Waitress if available for better performance/stability than dev server
    try:
        from waitress import serve
        print(f"Running with Waitress WSGI server on http://{HOST}:{PORT}")
        # Adjust threads, connection_limit, channel_timeout as needed
        serve(app, host=HOST, port=PORT, threads=10, channel_timeout=1800) # 30 min channel timeout
    except ImportError:
        print("\n--- WARNING ---")
        print("Waitress not found (pip install waitress). Using Flask's development server.")
        print("Flask's development server is NOT suitable for production.")
        print("---------------\n")
        # Run dev server with reloader disabled for APScheduler stability
        app.run(debug=False, host=HOST, port=PORT, threaded=True, use_reloader=False)