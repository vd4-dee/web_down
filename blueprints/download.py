from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
import config
import link_report
from logic_download import regions_data
from functools import wraps

# Import state and core logic from app context
from globals import lock, is_running, status_messages, download_thread
from logic_download import run_download_process  # Import hàm xử lý download chính

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

download_bp = Blueprint('download', __name__, url_prefix='/download', template_folder='../templates')

@download_bp.route('/')
@login_required
def index():
    permissions = session.get('permissions', [])
    report_url_map = link_report.get_report_url()
    reports = [{"name": name, "url": url} for name, url in report_url_map.items()]
    return render_template('dl_reports.html', permissions=permissions, reports=reports)

@download_bp.route('/history')
@login_required
def download_history():
    permissions = session.get('permissions', [])
    return render_template('dl_history.html', permissions=permissions)

@download_bp.route('/settings')
@login_required
def advanced_settings():
    permissions = session.get('permissions', [])
    return render_template('dl_settings.html', permissions=permissions)

@download_bp.route('/api/get-reports-regions', methods=['GET'])
@login_required
def get_reports_regions_data():
    try:
        report_url_map = link_report.get_report_url()
        report_names = list(report_url_map.keys()) if report_url_map else []
        regions_info = {idx: data['name'] for idx, data in regions_data.items()}
        return jsonify({
            'reports': report_names,
            'regions': regions_info,
            'region_required_urls': config.REGION_REQUIRED_REPORT_URLS,
            'report_urls_map': report_url_map
        })
    except Exception as e:
        print(f"Error in /api/get-reports-regions: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": "error", "message": "Could not load report/region data."}), 500

@download_bp.route('/api/start-download', methods=['POST'])
@login_required
def handle_start_download_api():
    global is_running
    from app import download_thread # Import here to avoid circular import
    with lock:
        if is_running:
            return jsonify({'status': 'error', 'message': 'A download process is already running. Please wait.'}), 409
    try:
        # Hỗ trợ cả JSON và form-data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict(flat=False)  # Lấy tất cả giá trị nếu có nhiều dòng
        print('Received data:', data)  # Debug dữ liệu nhận được
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid request: No data received.'}), 400
        # (Validation logic có thể chuyển sang hàm riêng nếu cần)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Error processing request data: {e}'}), 400
    try:
        # Khởi động luồng download nền
        with lock:
            download_thread = None
        import threading
        thread_data = data.copy()
        download_thread = threading.Thread(target=run_download_process, args=(thread_data,))
        download_thread.daemon = True
        download_thread.start()
        return jsonify({'status': 'started', 'message': 'Report download process initiated.'})
    except Exception as e:
        import traceback; traceback.print_exc()
        with lock:
            is_running = False
        return jsonify({'status': 'error', 'message': f'Internal Server Error: Failed to start download process ({e}).'}), 500
