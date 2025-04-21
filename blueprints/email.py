from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

email_bp = Blueprint('email', __name__, url_prefix='/email', template_folder='../templates')

@email_bp.route('/')
@login_required
def index():
    permissions = session.get('permissions', [])
    return render_template('email_send.html', permissions=permissions)

@email_bp.route('/history')
@login_required
def email_history():
    permissions = session.get('permissions', [])
    return render_template('email_history.html', permissions=permissions)
