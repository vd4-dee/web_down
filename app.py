# app.py
from flask import Flask, render_template, request, jsonify, Response
import threading
import time
import csv
import os
import pyotp
from datetime import datetime
import pandas as pd # Using pandas for easier CSV reading
import math

# Import from other project files
import config
from logic_download import WebAutomation, regions_data # Ensure regions_data is importable
import link_report

app = Flask(__name__)

# Global variables for state management (simple; might need refinement for concurrent users)
status_messages = []
is_running = False
download_thread = None

# --- Utility Functions ---
def stream_status_update(message):
    """Sends status messages to the client via SSE."""
    global status_messages
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"{timestamp}: {message}"
    print(full_message) # Log to backend console for debugging
    status_messages.append(full_message)
    # The SSE mechanism will pick this up

def run_download_process(params):
    """Function executed in a separate thread to perform the download."""
    global is_running, status_messages
    is_running = True
    status_messages = [] # Clear previous logs on new run
    stream_status_update("Starting report download process...")

    email = params['email']
    password = params['password']
    report_type_key = params['report_type'] # This is the key like "FAF001 - Sales Report"
    from_date = params['from_date']
    to_date = params['to_date']
    chunk_size_str = params['chunk_size']
    selected_regions_indices = params.get('regions', []) # List of selected region indices

    # --- Determine chunk_size ---
    try:
        if chunk_size_str.lower() == 'month':
            chunk_size = 'month'
        elif chunk_size_str:
            chunk_size = int(chunk_size_str)
            if chunk_size <= 0:
                 stream_status_update("Error: Chunk size must be a positive integer or 'month'. Using default: 5.")
                 chunk_size = 5 # Safe default
        else:
             stream_status_update("Chunk size not provided. Using default: 5.")
             chunk_size = 5 # Safe default
    except ValueError:
         stream_status_update(f"Error: Invalid chunk size '{chunk_size_str}'. Must be integer or 'month'. Using default: 5.")
         chunk_size = 5

    # --- Get Report URL ---
    report_url = link_report.get_report_url(report_type_key)
    if not report_url:
        stream_status_update(f"Error: Could not find URL for report type '{report_type_key}'")
        is_running = False
        return

    automation = None # Initialize to None
    try:
        # --- Create Download Folder ---
        # Modify create_download_folder in logic_download.py to accept base_path
        stream_status_update(f"Preparing download folder in: {config.DOWNLOAD_BASE_PATH}")
        download_folder = WebAutomation.create_download_folder(config.DOWNLOAD_BASE_PATH)
        stream_status_update(f"Download folder created: {download_folder}")

        # --- Initialize WebAutomation ---
        stream_status_update("Initializing browser automation...")
        # Modify __init__ in logic_download.py if you want to pass the status callback during init
        automation = WebAutomation(config.DRIVER_PATH, download_folder)

        # --- Login ---
        stream_status_update(f"Logging in with user: {email}...")
        otp = pyotp.TOTP(config.OTP_SECRET).now()
        # Pass status_callback to login (requires modification in logic_download.py)
        automation.login(report_url, email, password, otp, status_callback=stream_status_update)
        stream_status_update("Login successful.")

        # --- Perform Download ---
        stream_status_update(f"Preparing to download report: {report_type_key}")
        stream_status_update(f"Date Range: {from_date} to {to_date}, Chunk Size: {chunk_size}")

        # *** Logic to determine which download function to call ***
        # This requires mapping the report_type_key or report_url to the specific
        # download method in the WebAutomation class.

        if report_url in config.REGION_REQUIRED_REPORT_URLS:
            if not selected_regions_indices:
                stream_status_update("Error: This report requires selecting one or more regions.")
                is_running = False
                if automation: automation.close()
                return
            region_names = [regions_data[i]['name'] for i in selected_regions_indices if i in regions_data]
            stream_status_update(f"Downloading for regions: {', '.join(region_names)}")
            # Call the function for region-based downloads
            # Modify download_reports_for_all_regions in logic_download.py to accept status_callback
            automation.download_reports_for_all_regions(
                report_url, from_date, to_date,
                region_indices=selected_regions_indices,
                status_callback=stream_status_update
            )

        # --- Add specific report download logic here based on report_type_key or report_url ---
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
        # Add more 'elif' conditions for other specific reports (FAF002, 003, 005, 006, 028 etc.)
        # if they have dedicated `download_reports_in_chunks_X` methods.

        else:
            # Default download function for reports without special handling
            stream_status_update("Using generic download logic.")
            automation.download_reports_in_chunks(
                report_url, from_date, to_date, chunk_size,
                status_callback=stream_status_update
            )
        # --- End of specific report download logic ---

        stream_status_update("Report download process completed.")

    except Exception as e:
        error_message = f"An error occurred: {e}"
        stream_status_update(f"FATAL ERROR: {error_message}")
        import traceback
        traceback.print_exc() # Print full traceback to backend console

    finally:
        if automation:
            stream_status_update("Closing browser...")
            automation.close()
            stream_status_update("Browser closed.")
        is_running = False
        stream_status_update("--- PROCESS FINISHED ---")

# --- Routes (API Endpoints) ---
@app.route('/')
def index():
    """Render the main user interface page."""
    return render_template('index.html',
                           default_email=config.DEFAULT_EMAIL,
                           default_password=config.DEFAULT_PASSWORD)

@app.route('/get-reports-regions', methods=['GET'])
def get_reports_regions_data():
    """Provide the list of reports and region information."""
    report_names = list(link_report.get_report_url().keys())
    # Format region data for easier use in JS
    regions_info = {idx: data['name'] for idx, data in regions_data.items()}
    return jsonify({
        'reports': report_names,
        'regions': regions_info,
        'region_required_urls': config.REGION_REQUIRED_REPORT_URLS, # Send URLs requiring regions
        'report_urls_map': link_report.get_report_url() # Send map: report_key -> url
    })

@app.route('/start-download', methods=['POST'])
def handle_start_download():
    """Receive download request and start the process in a new thread."""
    global is_running, download_thread
    if is_running:
        return jsonify({'status': 'error', 'message': 'A download process is already running. Please wait.'}), 400

    data = request.json
    required_fields = ['email', 'password', 'report_type', 'from_date', 'to_date', 'chunk_size']
    if not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Missing required information.'}), 400

    # Check if region selection is required and provided
    report_url = link_report.get_report_url(data['report_type'])
    if report_url in config.REGION_REQUIRED_REPORT_URLS:
        if 'regions' not in data or not data['regions']: # Check if 'regions' key exists and is not empty
             return jsonify({'status': 'error', 'message': 'This report requires region selection.'}), 400
        # Convert region values from string to int (if they aren't already)
        try:
            data['regions'] = [int(r) for r in data['regions']]
        except (ValueError, TypeError):
             return jsonify({'status': 'error', 'message': 'Invalid region data received.'}), 400
    else:
        # Ensure regions list is empty if not needed
        data['regions'] = []


    # Start the background thread
    stream_status_update("Received download request. Starting background process...")
    download_thread = threading.Thread(target=run_download_process, args=(data,))
    download_thread.daemon = True # Allow app to exit even if thread is running
    download_thread.start()

    return jsonify({'status': 'started', 'message': 'Report download process initiated.'})


@app.route('/stream-status')
def stream_status_events():
    """Server-Sent Events (SSE) endpoint for status updates."""
    def event_stream():
        last_yielded_index = 0
        try:
            while True:
                # Yield new messages since last check
                current_messages_count = len(status_messages)
                if current_messages_count > last_yielded_index:
                    for i in range(last_yielded_index, current_messages_count):
                        yield f"data: {status_messages[i]}\n\n"
                    last_yielded_index = current_messages_count

                # If process finished and all messages sent, signal end and break
                if not is_running and last_yielded_index == len(status_messages):
                    yield f"data: FINISHED\n\n" # Signal to client
                    break

                time.sleep(1) # Wait before checking for new messages again
        except GeneratorExit:
            print("SSE client disconnected.")
        finally:
            print("SSE stream closing.")

    # Important: Set the mimetype to text/event-stream for SSE

@app.route('/get-logs', methods=['GET'])
def get_download_logs():
    """Read and return the content of the download_log.csv file."""
    import math
    log_file_path = os.path.join(os.path.dirname(__file__), 'download_log.csv')
    if not os.path.exists(log_file_path):
        return jsonify({'status': 'warning', 'message': 'Log file does not exist yet.', 'logs': []}), 200 # Return empty list

    try:
        # Use pandas to read CSV, handles headers well
        df = pd.read_csv(log_file_path)
        # Convert DataFrame to list of dictionaries (JSON records format)
        logs_data = df.to_dict('records')
        # Nếu logs_data không phải list thì trả về logs rỗng
        if not isinstance(logs_data, list):
            logs_data = []
        # Clean logs_data: loại bỏ giá trị NaN, None, ...
        for row in logs_data:
            for key, value in row.items():
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    row[key] = ''
        # Optional: sort by Timestamp if exists
        if 'Timestamp' in df.columns:
            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                logs_data = df.sort_values(by='Timestamp', ascending=False).to_dict('records')
            except Exception:
                pass # Keep original order if sorting fails

        return jsonify({'status': 'success', 'logs': logs_data})
    except pd.errors.EmptyDataError:
         return jsonify({'status': 'success', 'message': 'Log file is empty.', 'logs': []}), 200
    except Exception as e:
        # Đảm bảo không trả về NaN trong message
        msg = f'Failed to read log file: {str(e)}'
        if msg == 'NaN' or msg is None:
            msg = ''
        return jsonify({'status': 'error', 'message': msg, 'logs': []}), 500

if __name__ == '__main__':
    # Create the base download directory if it doesn't exist
    os.makedirs(config.DOWNLOAD_BASE_PATH, exist_ok=True)
    # Run the Flask development server
    # debug=True is helpful for development but should be False in production
    # threaded=True is necessary for handling SSE and background tasks concurrently
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)