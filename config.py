# config.py
import os

# !!! IMPORTANT: Never commit this file to Git if it contains sensitive information !!!
# Consider using environment variables for secrets.

# --- Required Configuration ---
OTP_SECRET = 'TAPHLYTABSKHTZWM' # Replace with your actual OTP secret key
DRIVER_PATH = os.path.abspath('chromedriver.exe') # Or absolute path, e.g., r"C:\path\to\chromedriver.exe"
DOWNLOAD_BASE_PATH = os.path.abspath(r"D:\OneDrive\KT\Checking") # Base folder for downloaded report subfolders

# --- Optional Configuration (leave empty to require input on UI) ---
DEFAULT_EMAIL = 'khangvd4'
DEFAULT_PASSWORD = 'toiGHEThack@123' # Leave empty if password should be entered on the UI

# --- Other Configuration ---
# List of report URLs that require region selection
REGION_REQUIRED_REPORT_URLS = [
    'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF030.aspx'
    # Add other report URLs if they require region selection
]