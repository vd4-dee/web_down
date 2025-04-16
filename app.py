# app.py
import flask
from flask import Flask, render_template, request, jsonify, Response
import threading
import time
import csv
import os
import pyotp
from datetime import datetime, timezone # Import timezone for scheduler
import pandas as pd
import math
import json
import traceback
import atexit # For graceful scheduler shutdown

# --- Scheduling Imports ---
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.date import DateTrigger
# from apscheduler.triggers.cron import CronTrigger # Uncomment if using cron
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import JobLookupError # For specific error handling

# --- Local Imports ---
# Assume config.py, logic_download.py, link_report.py are in the same directory
import config
# Ensure logic_download has necessary classes/functions (WebAutomation, regions_data)
from logic_download import WebAutomation, regions_data
import link_report

app = Flask(__name__)

# --- Constants ---
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'configs.json')
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'download_log.csv')

# --- Global variables for state management ---
status_messages = []
is_running = False
download_thread = None
# Lock for synchronizing access to shared resources
# (is_running, status_messages, config file write, scheduler interaction)
lock = threading.Lock()

# --- Scheduler Setup ---
jobstores = {
    'default': MemoryJobStore() # Schedules lost on restart
}
executors = {
    'default': ThreadPoolExecutor(5) # Allow up to 5 jobs concurrently
}
job_defaults = {
    'coalesce': True, # Run missed jobs only once if scheduler was down
    'max_instances': 1 # Prevent multiple instances of the same job running
}
# Using UTC is generally recommended for scheduling to avoid DST issues
# Ensure datetime objects passed to triggers are timezone-aware or naive but interpreted as UTC
scheduler = BackgroundScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone=timezone.utc # Use UTC timezone
)

# --- Utility Functions ---

def load_configs():
    """Loads configurations from the JSON file safely."""
    if not os.path.exists(CONFIG_FILE_PATH):
        return {}
    try:
        # Reading might not strictly need a lock if writes are infrequent and atomic
        # but using it for consistency doesn't hurt.
        with lock:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content:
                    return {}
                return json.loads(content)
    except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
        print(f"Error loading config file {CONFIG_FILE_PATH}: {e}")
        return {}

def save_configs(configs):
    """Saves configurations to the JSON file safely."""
    try:
        with lock: # Lock is crucial for writing
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Error saving config file {CONFIG_FILE_PATH}: {e}")

def stream_status_update(message):
    """Sends status updates to the client via SSE and logs to console."""
    global status_messages
    # Use UTC time for logs for consistency? Or local time? Using local for now.
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"{timestamp}: {message}"
    print(full_message) # Log to console
    with lock:
        status_messages.append(full_message)

# --- Download Process Function ---

def run_download_process(params):
    global is_running, status_messages
    is_running = True
    status_messages = [] # Clear previous logs on new run
    stream_status_update("Starting report download process...")

    email = params['email']
    password = params['password']
    report_types = params['report_type'] if isinstance(params['report_type'], list) else [params['report_type']]
    from_dates = params['from_date'] if isinstance(params['from_date'], list) else [params['from_date']]
    to_dates = params['to_date'] if isinstance(params['to_date'], list) else [params['to_date']]
    chunk_sizes = params['chunk_size'] if isinstance(params['chunk_size'], list) else [params['chunk_size']]
    selected_regions_indices = params.get('regions', [])

    automation = None
    try:
        stream_status_update(f"Preparing download folder in: {config.DOWNLOAD_BASE_PATH}")
        download_folder = WebAutomation.create_download_folder(config.DOWNLOAD_BASE_PATH)
        stream_status_update(f"Download folder created: {download_folder}")
        stream_status_update("Initializing browser automation...")
        automation = WebAutomation(config.DRIVER_PATH, download_folder)
        stream_status_update(f"Logging in with user: {email}...")
        otp = pyotp.TOTP(config.OTP_SECRET).now()
        # Đăng nhập 1 lần đầu tiên
        first_report_url = link_report.get_report_url(report_types[0])
        automation.login(first_report_url, email, password, otp, status_callback=stream_status_update)
        stream_status_update("Login successful.")

        for i in range(len(report_types)):
            report_type_key = report_types[i]
            from_date = from_dates[i] if i < len(from_dates) else from_dates[-1]
            to_date = to_dates[i] if i < len(to_dates) else to_dates[-1]
            chunk_size_str = chunk_sizes[i] if i < len(chunk_sizes) else chunk_sizes[-1]

            try:
                if isinstance(chunk_size_str, str) and chunk_size_str.lower() == 'month':
                    chunk_size = 'month'
                elif chunk_size_str:
                    chunk_size = int(chunk_size_str)
                    if chunk_size <= 0:
                        stream_status_update("Error: Chunk size must be a positive integer or 'month'. Using default: 5.")
                        chunk_size = 5
                else:
                    stream_status_update("Chunk size not provided. Using default: 5.")
                    chunk_size = 5
            except ValueError:
                stream_status_update(f"Error: Invalid chunk size '{chunk_size_str}'. Must be integer or 'month'. Using default: 5.")
                chunk_size = 5

            report_url = link_report.get_report_url(report_type_key)
            if not report_url:
                stream_status_update(f"Error: Could not find URL for report type '{report_type_key}'")
                continue

            stream_status_update(f"Preparing to download report: {report_type_key}")
            stream_status_update(f"Date Range: {from_date} to {to_date}, Chunk Size: {chunk_size}")

            if report_url in config.REGION_REQUIRED_REPORT_URLS:
                if not selected_regions_indices:
                    stream_status_update("Error: This report requires selecting one or more regions.")
                    continue
                
                try:
                    selected_regions_indices_int = [int(idx) for idx in selected_regions_indices]
                    region_names = [regions_data[i]['name'] for i in selected_regions_indices_int if i in regions_data]
                    stream_status_update(f"Downloading for regions: {', '.join(region_names)}")
                    automation.download_reports_for_all_regions(
                        report_url, from_date, to_date,
                        region_indices=selected_regions_indices_int,
                        status_callback=stream_status_update
                    )
                except (ValueError, TypeError):
                    stream_status_update("Error: Invalid region indices provided.")
                    continue

            elif report_type_key == "FAF001 - Sales Report":
                stream_status_update("Detected FAF001 - Using specific download logic.")
                automation.download_reports_in_chunks_1(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            elif report_type_key == "FAF004N - Internal Rotation Report (Imports)":
                stream_status_update("Detected FAF004N - Using specific download logic.")
                automation.download_reports_in_chunks_4n(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            elif report_type_key == "FAF004X - Internal Rotation Report (Exports)":
                stream_status_update("Detected FAF004X - Using specific download logic.")
                automation.download_reports_in_chunks_4x(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            elif report_type_key == "FAF002 - Dosage Report":
                stream_status_update("Detected FAF002 - Using specific download logic.")
                automation.download_reports_in_chunks_2(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            elif report_type_key == "FAF003 - Transport Report":
                stream_status_update("Detected FAF003 - Using specific download logic.")
                automation.download_reports_in_chunks_3(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            else:
                stream_status_update("Using generic download logic.")
                automation.download_reports_in_chunks(
                    report_url, from_date, to_date, chunk_size,
                    status_callback=stream_status_update
                )
            stream_status_update(f"Completed download for report: {report_type_key}")

        stream_status_update("All report downloads completed.")
    except Exception as e:
        error_message = f"An error occurred: {e}"
        stream_status_update(f"FATAL ERROR: {error_message}")
        import traceback
        traceback.print_exc()
    finally:
        if automation:
            stream_status_update("Closing browser...")
            automation.close()
            stream_status_update("Browser closed.")
        is_running = False
        stream_status_update("--- PROCESS FINISHED ---")


# --- Function Called by Scheduler ---
def trigger_scheduled_download(config_name):
    """
    Loads a saved configuration and starts the download process in a new thread.
    Executed by APScheduler jobs.
    """
    print(f"Scheduler attempting to trigger job for config: {config_name}")
    # stream_status_update(f"(Scheduler) Triggered download for config: {config_name}") # Optional: Log to UI

    with lock:
        if is_running:
            print(f"Scheduler: Download process already running. Skipping job for '{config_name}'.")
            stream_status_update(f"(Scheduler) Skipped job for '{config_name}': Process already running.")
            return
        # No need to set is_running here, run_download_process will do it

    # Load the configuration
    configs = load_configs()
    params = configs.get(config_name)

    if not params:
        print(f"Scheduler: Configuration '{config_name}' not found. Cannot start download.")
        stream_status_update(f"(Scheduler) Error: Configuration '{config_name}' not found.")
        return

    # Start the download process in a new thread
    print(f"Scheduler: Starting download thread for config '{config_name}'...")
    # Pass the loaded params and indicate the source
    scheduled_thread = threading.Thread(
        target=run_download_process,
        args=(params,) # Pass loaded params directly
    )
    scheduled_thread.daemon = True
    scheduled_thread.start()


# --- Flask Routes ---
@app.route('/')
def index():
    """Render the main UI page."""
    return render_template('index.html',
                           default_email=config.DEFAULT_EMAIL,
                           default_password=config.DEFAULT_PASSWORD)

# --- API Endpoints ---

@app.route('/get-reports-regions', methods=['GET'])
def get_reports_regions_data():
    """Provide the list of reports and region information."""
    try:
        report_names = list(link_report.get_report_url().keys())
        regions_info = {idx: data['name'] for idx, data in regions_data.items()}
        report_urls_map = link_report.get_report_url()
        return jsonify({
            'reports': report_names,
            'regions': regions_info,
            'region_required_urls': config.REGION_REQUIRED_REPORT_URLS,
            'report_urls_map': report_urls_map
        })
    except Exception as e:
        print(f"Error in /get-reports-regions: {e}")
        return jsonify({"status": "error", "message": "Could not load report/region data."}), 500


@app.route('/start-download', methods=['POST'])
def handle_start_download():
    """Handles manual download request from the form."""
    global is_running, download_thread
    print("\n--- Received request for /start-download ---")

    with lock:
        if is_running:
            print("/start-download: Process already running. Returning error.")
            return jsonify({'status': 'error', 'message': 'A download process is already running. Please wait.'}), 400
        # No need to set is_running here, run_download_process does it

    # Get data safely
    try:
        data = request.get_json()
        if not data:
            print("/start-download: No JSON data received. Returning error.")
            return jsonify({'status': 'error', 'message': 'Invalid request data.'}), 400
        print(f"/start-download: Received data: {json.dumps(data)}") # Log received data
    except Exception as e:
        print(f"/start-download: Error getting JSON data: {e}")
        return jsonify({'status': 'error', 'message': f'Error parsing request data: {e}'}), 400

    # --- Input validation ---
    print("/start-download: Starting validation...")
    required_fields = ['email', 'password', 'report_type', 'from_date', 'to_date', 'chunk_size']
    missing_fields = [field for field in required_fields if field not in data or not data[field]] # Check for empty values too
    if missing_fields:
        msg = f'Missing required information: {", ".join(missing_fields)}.'
        print(f"/start-download: Validation failed - {msg}")
        return jsonify({'status': 'error', 'message': msg}), 400

    report_types = data.get('report_type', [])
    report_types = report_types if isinstance(report_types, list) else [report_types]
    # Ensure at least one non-empty report type
    if not any(rt for rt in report_types):
        msg = 'Please select at least one report type.'
        print(f"/start-download: Validation failed - {msg}")
        return jsonify({'status': 'error', 'message': msg}), 400

    # Check list lengths
    num_reports = len(report_types)
    if not all(len(data.get(key, [])) == num_reports for key in ['from_date', 'to_date', 'chunk_size']):
         msg = 'Data mismatch: Number of dates/chunk sizes does not match number of reports.'
         print(f"/start-download: Validation failed - {msg}")
         return jsonify({'status': 'error', 'message': msg}), 400

    # Region validation
    region_required_for_any = False
    report_urls_map = link_report.get_report_url()
    regions_required_list = config.REGION_REQUIRED_REPORT_URLS
    for report_type in report_types:
        report_url = report_urls_map.get(report_type)
        if report_url in regions_required_list:
            region_required_for_any = True
            break

    if region_required_for_any:
        print("/start-download: Validating regions data...")
        if 'regions' not in data or not isinstance(data['regions'], list):
            msg = 'Invalid region data (must be a list).'
            print(f"/start-download: Validation failed - {msg}")
            return jsonify({'status': 'error', 'message': msg}), 400
        try:
            # Ensure regions are integers (frontend should send strings, convert here)
            data['regions'] = [int(r) for r in data['regions']]
            if not data['regions']: # Check if list is empty after conversion
                msg = 'Please select at least one region for the required report.'
                print(f"/start-download: Validation failed - {msg}")
                return jsonify({'status': 'error', 'message': msg}), 400
        except (ValueError, TypeError) as e:
            msg = f'Invalid region data (must be numbers): {e}'
            print(f"/start-download: Validation failed - {msg}")
            return jsonify({'status': 'error', 'message': msg}), 400
    else:
        data['regions'] = [] # Ensure empty list if not required
    print("/start-download: Validation successful.")
    # --- End validation ---

    # --- Start background thread ---
    try:
        print("/start-download: Preparing to start download thread...")
        stream_status_update("Received manual download request. Starting background process...")
        download_thread = threading.Thread(target=run_download_process, args=(data.copy(),))
        download_thread.daemon = True
        download_thread.start()
        print("/start-download: Download thread started.")
    except Exception as e:
        print(f"/start-download: Failed to start download thread: {e}")
        traceback.print_exc()
        # If thread fails to start, we are not 'running'
        return jsonify({'status': 'error', 'message': f'Failed to start download process: {e}'}), 500

    print("/start-download: Returning 'started' status.")
    return jsonify({'status': 'started', 'message': 'Report download process initiated.'})


@app.route('/stream-status')
def stream_status_events():
    """SSE endpoint for status updates."""
    def event_stream():
        last_yielded_index = 0
        try:
            while True:
                # Check state and get messages under lock
                with lock:
                    current_messages_count = len(status_messages)
                    is_process_running = is_running
                    messages_to_yield = status_messages[last_yielded_index:current_messages_count]

                # Yield new messages outside lock
                if messages_to_yield:
                    for message_to_send in messages_to_yield:
                         yield f"data: {message_to_send}\n\n"
                    last_yielded_index = current_messages_count # Update index *after* sending

                # Check finish condition *after* sending potentially final messages
                if not is_process_running and last_yielded_index == current_messages_count:
                    # Add a small delay to ensure FINISHED is the very last message
                    time.sleep(0.1)
                    yield f"data: FINISHED\n\n"
                    break

                time.sleep(0.5) # Check for updates every 0.5 seconds
        except GeneratorExit:
            print("SSE client disconnected.")
        # except Exception as e:
            # print(f"Error in SSE stream: {e}") # Uncomment for debugging SSE issues
        finally:
            print("SSE stream closing.")
    return Response(event_stream(), mimetype='text/event-stream')


@app.route('/get-logs', methods=['GET'])
def get_download_logs():
    """Reads and returns the content of the download_log.csv file."""
    if not os.path.exists(LOG_FILE_PATH):
        return jsonify({'status': 'warning', 'message': 'Log file does not exist yet.', 'logs': []}), 200
    try:
        # Read with pandas, ensuring correct handling of potential errors
        df = pd.read_csv(LOG_FILE_PATH, dtype=str, keep_default_na=False, na_values=[''], on_bad_lines='skip')
        logs_data = df.to_dict('records')
        # Clean data (handle potential NaN/None remnants from pandas)
        cleaned_logs = [
            {key: '' if pd.isna(value) or value is None else str(value) for key, value in row.items()}
            for row in logs_data
        ]
        # Optional: Sort by Timestamp descending
        if 'Timestamp' in df.columns:
            try:
                # Use pd.to_datetime with error coercion
                df['TimestampParsed'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                # Sort valid timestamps, keep original order for invalid ones? Or drop? Dropping for now.
                df_sorted = df.dropna(subset=['TimestampParsed']).sort_values(by='TimestampParsed', ascending=False)
                # Convert sorted data back and clean again
                sorted_records = df_sorted.drop(columns=['TimestampParsed']).to_dict('records')
                cleaned_logs = [
                    {key: '' if pd.isna(value) or value is None else str(value) for key, value in row.items()}
                    for row in sorted_records
                ]
            except Exception as sort_err:
                print(f"Could not sort logs by timestamp: {sort_err}")
                # Use unsorted cleaned_logs if sorting fails
        return jsonify({'status': 'success', 'logs': cleaned_logs})
    except pd.errors.EmptyDataError:
         return jsonify({'status': 'success', 'message': 'Log file is empty.', 'logs': []}), 200
    except Exception as e:
        print(f"Error reading log file: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Error reading log file: {e}', 'logs': []}), 500

# --- Configuration Endpoints ---
@app.route('/get-configs', methods=['GET'])
def get_configs():
    """Gets the list of saved configuration names."""
    configs = load_configs()
    return jsonify({'status': 'success', 'configs': list(configs.keys())})

@app.route('/save-config', methods=['POST'])
def save_config():
    """Saves or updates a configuration."""
    data = request.json
    config_name = data.get('config_name')
    config_data = data.get('config_data')
    if not config_name or not config_data:
        return jsonify({'status': 'error', 'message': 'Missing configuration name or data.'}), 400
    # Basic validation of config_data structure?
    if not isinstance(config_data.get('reports'), list):
         return jsonify({'status': 'error', 'message': 'Invalid configuration data structure.'}), 400
    configs = load_configs()
    configs[config_name] = config_data
    save_configs(configs)
    return jsonify({'status': 'success', 'message': f'Configuration "{config_name}" saved.'})

@app.route('/load-config/<config_name>', methods=['GET'])
def load_config(config_name):
    """Loads the details of a specific configuration."""
    configs = load_configs()
    config_data = configs.get(config_name)
    if config_data:
        return jsonify({'status': 'success', 'config_data': config_data})
    else:
        return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found.'}), 404

@app.route('/delete-config/<config_name>', methods=['DELETE'])
def delete_config(config_name):
    """Deletes a saved configuration."""
    configs = load_configs()
    if config_name in configs:
        del configs
        save_configs(configs)
        return jsonify({'status': 'success', 'message': f'Configuration "{config_name}" deleted.'})
    else:
        return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found for deletion.'}), 404

# --- Scheduling API Endpoints ---

@app.route('/schedule-job', methods=['POST'])
def schedule_job():
    """Schedules a new download job."""
    data = request.json
    config_name = data.get('config_name')
    trigger_type = data.get('trigger_type', 'date') # Default to 'date'
    run_datetime_str = data.get('run_datetime') # Expected format: YYYY-MM-DDTHH:MM

    print(f"Received schedule request: config='{config_name}', trigger='{trigger_type}', datetime='{run_datetime_str}'")

    if not config_name:
        return jsonify({'status': 'error', 'message': 'Configuration name is required.'}), 400

    # Validate config exists
    configs = load_configs()
    if config_name not in configs:
         return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found.'}), 404

    trigger = None
    # Generate a more robust unique job ID
    job_id = f"sched_{config_name.replace(' ','_')}_{int(time.time())}"

    try:
        if trigger_type == 'date':
            if not run_datetime_str:
                return jsonify({'status': 'error', 'message': 'Run date/time is required for "date" trigger.'}), 400
            # Parse the naive datetime string from input
            run_datetime_naive = datetime.fromisoformat(run_datetime_str)

            # Compare with current *naive* time to check if it's in the past
            # This assumes server and user input share the same (or close enough) timezone context for validation
            if run_datetime_naive <= datetime.now():
                 return jsonify({'status': 'error', 'message': 'Scheduled time must be in the future.'}), 400

            # Use the naive datetime directly with the UTC scheduler
            # APScheduler will interpret this naive datetime according to its configured timezone (UTC)
            trigger = DateTrigger(run_date=run_datetime_naive)
            print(f"Scheduling job {job_id} with DateTrigger for naive datetime {run_datetime_naive} (interpreted as UTC)")

        # Add 'cron' or 'interval' trigger logic here if needed
        # elif trigger_type == 'cron':
        # ...

        else:
             return jsonify({'status': 'error', 'message': f'Unsupported trigger type: {trigger_type}'}), 400

        # Add the job to the scheduler
        # Use lock to prevent potential race conditions if scheduler is modified elsewhere
        with lock:
            scheduler.add_job(
                func=trigger_scheduled_download,
                trigger=trigger,
                args=[config_name], # Pass config name as argument
                id=job_id,
                name=f"Download: {config_name}", # Job name for easier identification
                replace_existing=False,
                misfire_grace_time=600 # 10 minutes grace period
            )
        print(f"Successfully added job {job_id} to scheduler.")
        return jsonify({'status': 'success', 'message': f'Job scheduled successfully for config "{config_name}".', 'job_id': job_id})

    except Exception as e:
        print(f"Error scheduling job: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to schedule job: {e}'}), 500


@app.route('/get-schedules', methods=['GET'])
def get_schedules():
    """Gets the list of currently scheduled jobs."""
    jobs_info = []
    try:
        # Use lock when accessing scheduler state
        with lock:
            jobs = scheduler.get_jobs()
            for job in jobs:
                # Format next run time safely
                next_run_iso = None
                if job.next_run_time:
                    try:
                        # Ensure it's UTC before formatting
                        next_run_utc = job.next_run_time.astimezone(timezone.utc)
                        next_run_iso = next_run_utc.isoformat()
                    except Exception as fmt_e:
                        print(f"Error formatting next_run_time for job {job.id}: {fmt_e}")
                        next_run_iso = str(job.next_run_time) # Fallback

                jobs_info.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': next_run_iso,
                    'trigger': str(job.trigger),
                    'args': job.args # Should contain the config_name
                })
        return jsonify({'status': 'success', 'schedules': jobs_info})
    except Exception as e:
        print(f"Error getting schedules: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to get schedules: {e}'}), 500


@app.route('/cancel-schedule/<job_id>', methods=['DELETE'])
def cancel_schedule(job_id):
    """Cancels (removes) a scheduled job."""
    print(f"Received request to cancel job: {job_id}")
    try:
        # Use lock for scheduler modification
        with lock:
            scheduler.remove_job(job_id)
        print(f"Removed job {job_id} from scheduler.")
        # Return success even if job was already gone (idempotent)
        return jsonify({'status': 'success', 'message': f'Job "{job_id}" cancelled successfully.'})
    except JobLookupError:
         print(f"Job {job_id} not found for cancellation (already finished or removed).")
         # Return success as the desired state (job gone) is achieved
         return jsonify({'status': 'success', 'message': f'Job "{job_id}" not found or already completed.'})
    except Exception as e:
        print(f"Error cancelling job {job_id}: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to cancel job "{job_id}": {e}'}), 500


# --- Main Execution ---
if __name__ == '__main__':
    # Initial setup
    os.makedirs(config.DOWNLOAD_BASE_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"Configuration file not found at {CONFIG_FILE_PATH}. Creating empty file.")
        save_configs({}) # Create empty config file if it doesn't exist

    # Start the scheduler only if running the main script directly
    # and not already running (e.g., in Flask debug mode with reloader)
    if not scheduler.running:
        try:
            scheduler.start()
            print("APScheduler started successfully.")
            # Register shutdown hook
            atexit.register(lambda: scheduler.shutdown())
            print("Registered APScheduler shutdown hook.")
        except Exception as e:
            print(f"Error starting APScheduler: {e}")
            traceback.print_exc()
            # Decide if the app should exit or continue without scheduler

    # Run Flask app
    print("Starting Flask application...")
    # Use use_reloader=False to prevent scheduler from starting twice in debug mode
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True, use_reloader=False)

