from flask import Blueprint, render_template, session, redirect, url_for

main_bp = Blueprint('main', __name__, template_folder='../templates')

@main_bp.route('/')
def index():
    if 'user_email' not in session:
        return redirect(url_for('auth.login'))
    # --- Thống kê tổng quan cho dashboard ---
    stats = {
        'downloads': 0,
        'schedules': 0,
        'emails': 0,
        'system_status': 'Online'
    }
    # Đếm số lần tải báo cáo từ log
    try:
        import os
        log_path = os.path.join(os.getcwd(), 'logs', 'download_log.csv')
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                stats['downloads'] = sum(1 for _ in f) - 1  # Trừ header
    except Exception:
        pass
    # Đếm số job trong APScheduler
    try:
        from app import scheduler
        stats['schedules'] = len(scheduler.get_jobs())
    except Exception:
        pass
    # Đếm số email đã gửi từ log
    try:
        email_log_path = os.path.join(os.getcwd(), 'logs', 'email_log.csv')
        if os.path.exists(email_log_path):
            with open(email_log_path, 'r', encoding='utf-8') as f:
                stats['emails'] = sum(1 for _ in f) - 1
    except Exception:
        pass
    return render_template('dashboard.html', user_email=session.get('user_email'), stats=stats)

@main_bp.route('/user_manuals')
def user_manuals():
    if 'user_email' not in session:
        return redirect(url_for('auth.login'))
    permissions = session.get('permissions', [])
    return render_template('user_manuals.html', permissions=permissions)
