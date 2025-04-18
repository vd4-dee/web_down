import csv
import os
import time
from datetime import datetime
import win32com.client as win32
from config import DEFAULT_SENDER, EMAIL_BATCH_SIZE, EMAIL_PAUSE_SECONDS, EMAIL_LOG_PATH


def send_bulk_email(csv_file_path, subject, body):
    """
    Send bulk emails via local Outlook COM.
    Reads recipients from the first column of the CSV (skips header if 'email').
    Logs each send to EMAIL_LOG_PATH and returns summary.
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Ensure log file with header exists
    if not os.path.exists(EMAIL_LOG_PATH):
        with open(EMAIL_LOG_PATH, 'w', newline='', encoding='utf-8') as logf:
            writer = csv.writer(logf)
            writer.writerow(['SessionID', 'Timestamp', 'Recipient', 'Status', 'ErrorMessage'])

    # Read recipients
    recipients = []
    try:
        with open(csv_file_path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                val = row[0].strip()
                if val.lower() == 'email':
                    continue
                recipients.append(val)
    except Exception as e:
        return {'error': f'Read CSV failed: {e}'}

    # Initialize Outlook
    try:
        outlook = win32.Dispatch('Outlook.Application')
    except Exception as e:
        return {'error': f'Outlook COM dispatch failed: {e}'}

    results = []
    success_count = 0
    failure_count = 0

    # Send in batches
    for i in range(0, len(recipients), EMAIL_BATCH_SIZE):
        batch = recipients[i:i + EMAIL_BATCH_SIZE]
        for recipient in batch:
            timestamp = datetime.now().isoformat()
            status = 'Success'
            error_message = ''
            try:
                mail = outlook.CreateItem(0)
                mail.To = recipient
                mail.Subject = subject
                mail.HTMLBody = body
                # Optional: set sender if required
                # mail.SentOnBehalfOfName = DEFAULT_SENDER
                mail.Send()
                success_count += 1
            except Exception as e:
                status = 'Failed'
                error_message = str(e)
                failure_count += 1
            # Record result
            results.append({'recipient': recipient, 'status': status, 'error': error_message})
            # Append to log file
            with open(EMAIL_LOG_PATH, 'a', newline='', encoding='utf-8') as logf:
                writer = csv.writer(logf)
                writer.writerow([session_id, timestamp, recipient, status, error_message])
        # Pause between batches
        time.sleep(EMAIL_PAUSE_SECONDS)

    return {
        'session_id': session_id,
        'total': len(recipients),
        'success': success_count,
        'failed': failure_count,
        'details': results
    }
