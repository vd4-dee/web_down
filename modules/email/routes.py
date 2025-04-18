from . import email_bp
from flask import render_template, request, redirect, url_for, flash
import os
import re
from .logic_email import send_bulk_email


@email_bp.route('/', methods=['GET', 'POST'])
def index():
    # Load scenario templates
    file_dir = os.path.join(os.getcwd(), 'file')
    templates = {}
    if os.path.isdir(file_dir):
        for fname in os.listdir(file_dir):
            path = os.path.join(file_dir, fname)
            try:
                content = open(path, 'r', encoding='utf-8').read()
            except:
                continue
            if not content.strip().lower().startswith('<!doctype'):
                continue
            m = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            subject = m.group(1) if m else os.path.splitext(fname)[0]
            key = os.path.splitext(fname)[0]
            templates[key] = {'subject': subject, 'body': content}
    if request.method == 'POST':
        file = request.files.get('email_list')
        scenario = request.form.get('scenario')
        if scenario and scenario in templates:
            subject = templates[scenario]['subject']
            body = templates[scenario]['body']
        else:
            subject = request.form.get('subject')
            body = request.form.get('body')
        if not file or not subject or not body:
            flash('Email list, subject, and body are required.', 'danger')
            return redirect(url_for('email.index'))
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, file.filename)
        file.save(filepath)
        result = send_bulk_email(filepath, subject, body)
        return render_template('email/result.html', result=result)
    return render_template('email/index.html', templates=templates)
