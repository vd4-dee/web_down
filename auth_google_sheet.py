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

# Hàm kiểm tra quyền

def is_user_allowed(email):
    allowed = get_allowed_users()
    return email.strip().lower() in allowed
