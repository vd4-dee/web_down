import gspread
from google.oauth2.service_account import Credentials

# Thay bằng tên Google Sheet thật sự của bạn
GOOGLE_SHEET_ID = '19XJsntpyJXJRYGuXMIgr6yBsw4_jT1zZ9lI8ERTCOFg'
# GOOGLE_SHEET_NAME = 'allowed_users'  # Không dùng nữa
# Đường dẫn tới file credentials JSON đã tải về
GOOGLE_CREDENTIALS_FILE = 'google-credentials.json'

# Lấy danh sách user từ Google Sheet (theo cột email)
def get_allowed_users():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        print("Using credentials file:", GOOGLE_CREDENTIALS_FILE)
        print("Service account email:", creds.service_account_email)
        print("Scopes:", creds.scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.worksheet('allowed_users')
        rows = worksheet.get_all_records()
        allowed_emails = set()
        for row in rows:
            email = row.get('email')
            if email:
                allowed_emails.add(email.strip().lower())
        return allowed_emails
    except Exception as e:
        print("ERROR in get_allowed_users:", e)
        raise

# Password authentication helpers

def get_user_password(email):
    """
    Returns the password for a given email from Google Sheet (plain text).
    Returns None if not found.
    """
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.worksheet('allowed_users')
        rows = worksheet.get_all_records()
        for row in rows:
            row_email = row.get('email')
            if row_email and row_email.strip().lower() == email.strip().lower():
                return row.get('password')
        return None
    except Exception as e:
        print("ERROR in get_user_password:", e)
        raise

def check_user_credentials(email, password):
    """
    Returns True if email exists and password matches (plain text).
    """
    user_password = get_user_password(email)
    if user_password is None:
        return False
    return str(password) == str(user_password)

def update_user_password(email, new_password):
    """
    Update the password for the given email in Google Sheet.
    Returns True if updated, False if not found.
    """
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.worksheet('allowed_users')
        rows = worksheet.get_all_records()
        for idx, row in enumerate(rows, start=2):  # Row 1 is header
            row_email = row.get('email')
            if row_email and row_email.strip().lower() == email.strip().lower():
                # Find the column index for 'password'
                header = worksheet.row_values(1)
                if 'password' in header:
                    col_idx = header.index('password') + 1
                    worksheet.update_cell(idx, col_idx, new_password)
                    return True
        return False
    except Exception as e:
        print("ERROR in update_user_password:", e)
        raise

# Hàm kiểm tra quyền

def is_user_allowed(email):
    allowed = get_allowed_users()
    return email.strip().lower() in allowed
