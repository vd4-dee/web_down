from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from auth_google_sheet import check_user_credentials, get_user_permissions, update_user_password

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if check_user_credentials(email, password):
            session['user_email'] = email
            try:
                permissions = get_user_permissions(email)
                session['permissions'] = permissions
            except Exception as e:
                flash('Could not load user permissions: {}'.format(e))
                session['permissions'] = []
            return redirect(url_for('main.index'))
        else:
            flash('Invalid email or password.')
    return render_template('login.html')

@auth_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        email = request.form['email']
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        if not (email and old_password and new_password):
            flash('Please fill in all fields.')
            return render_template('change_password.html')
        if not check_user_credentials(email, old_password):
            flash('Current password is incorrect.')
            return render_template('change_password.html')
        if old_password == new_password:
            flash('New password must be different from current password.')
            return render_template('change_password.html')
        try:
            updated = update_user_password(email, new_password)
            if updated:
                flash('Password changed successfully. Please log in with your new password.')
                return redirect(url_for('auth.login'))
            else:
                flash('Email not found.')
        except Exception as e:
            flash('An error occurred: {}'.format(e))
    return render_template('change_password.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('auth.login'))
