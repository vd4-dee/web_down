from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from functools import wraps
from globals import lock
# Import các hàm này ngay bên trong function sử dụng để tránh circular import
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime, timedelta
import time

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule', template_folder='../templates')

@schedule_bp.route('/')
@login_required
def index():
    permissions = session.get('permissions', [])
    return render_template('dl_schedule.html', permissions=permissions)

@schedule_bp.route('/api/schedule-job', methods=['POST'])
@login_required
def schedule_job():
    from app import scheduler, load_configs, trigger_scheduled_download
    try:
        data = request.get_json()
        if not data: return jsonify({'status': 'error', 'message': 'Invalid request: No data.'}), 400
        config_name = data.get('config_name')
        run_datetime_str = data.get('run_datetime')
        if not config_name: return jsonify({'status': 'error', 'message': 'Configuration name required.'}), 400
        if not run_datetime_str: return jsonify({'status': 'error', 'message': 'Run date/time required.'}), 400
        configs = load_configs()
        if config_name not in configs:
            return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found.'}), 404
        job_id = f"sched_{config_name.replace(' ','_').lower()}_{int(time.time())}"
        try:
            run_datetime_naive = datetime.fromisoformat(run_datetime_str)
            if run_datetime_naive <= datetime.now() + timedelta(seconds=60):
                return jsonify({'status': 'error', 'message': 'Scheduled time must be > 1 min in the future.'}), 400
            trigger = DateTrigger(run_date=run_datetime_naive)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date/time format (YYYY-MM-DDTHH:MM).'}), 400
        with lock:
            scheduler.add_job(
                func=trigger_scheduled_download, trigger=trigger, args=[config_name],
                id=job_id, name=f"Download: {config_name}", replace_existing=False,
                misfire_grace_time=600
            )
        return jsonify({'status': 'success', 'message': f'Job scheduled for config "{config_name}".', 'job_id': job_id})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to schedule job: {e}'}), 500

@schedule_bp.route('/api/get-schedules', methods=['GET'])
@login_required
def get_schedules():
    from app import scheduler
    jobs_info = []
    try:
        with lock:
            jobs = scheduler.get_jobs()
            for job in jobs:
                next_run_iso = None
                if job.next_run_time:
                    try:
                        next_run_iso = job.next_run_time.isoformat()
                    except Exception as fmt_e:
                        next_run_iso = str(job.next_run_time)
                jobs_info.append({
                    'id': job.id, 'name': job.name,
                    'next_run_time': next_run_iso,
                    'trigger': str(job.trigger),
                    'args': job.args
                })
        return jsonify({'status': 'success', 'schedules': jobs_info})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to get schedules: {e}'}), 500

@schedule_bp.route('/api/cancel-schedule/<job_id>', methods=['DELETE'])
@login_required
def cancel_schedule(job_id):
    from app import scheduler
    try:
        with lock:
            scheduler.remove_job(job_id)
        return jsonify({'status': 'success', 'message': f'Job "{job_id}" cancelled.'})
    except JobLookupError:
        return jsonify({'status': 'success', 'message': f'Job "{job_id}" not found (already run or cancelled).'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to cancel job "{job_id}": {e}'}), 500
