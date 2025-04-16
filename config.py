# config.py
import os
# Recommended: Use a library like python-dotenv to load secrets from a .env file
# Example:
# from dotenv import load_dotenv
# load_dotenv() # Load variables from .env file into environment

# !!! IMPORTANT: Avoid committing sensitive data like secrets directly into code !!!
# Consider using Environment Variables or a dedicated secrets management system.

# --- Required Configuration ---
# Load from environment variables if available, otherwise use hardcoded (less secure)
OTP_SECRET = os.getenv('OTP_SECRET', 'TAPHLYTABSKHTZWM') # Replace with your actual OTP secret key or set ENV VAR
DRIVER_PATH = os.getenv('CHROMEDRIVER_PATH', os.path.abspath('chromedriver.exe')) # Or absolute path
DOWNLOAD_BASE_PATH = os.getenv('DOWNLOAD_PATH', os.path.abspath(r"D:\Base\Checking")) # Base folder

# --- Optional Configuration (leave empty to require input on UI) ---
DEFAULT_EMAIL = os.getenv('DEFAULT_EMAIL', 'khangvd4')
# Avoid storing default password here if possible. Prefer UI input.
DEFAULT_PASSWORD = os.getenv('DEFAULT_PASSWORD', 'toiGHEThack@123') # Leave empty or load from ENV VAR if absolutely needed

# DRIVER_PORT = 9515 # This port seems unused in the current logic? Verify if needed.

# --- Other Configuration ---
# List of report URLs that require region selection
REGION_REQUIRED_REPORT_URLS = [
    'https://bi.nhathuoclongchau.com.vn/MIS/PHAR/PHARFAF030.aspx'
    # Add other report URLs if they require region selection
]

# --- Validation (Optional but recommended) ---
if not OTP_SECRET or OTP_SECRET == 'YOUR_DEFAULT_OTP_SECRET_HERE':
    print("WARNING: OTP_SECRET is not configured securely. Please set the environment variable or update config.py.")
if not os.path.exists(DRIVER_PATH):
     print(f"WARNING: ChromeDriver path does not exist: {DRIVER_PATH}. Please check the path or set CHROMEDRIVER_PATH environment variable.")
if not os.path.exists(DOWNLOAD_BASE_PATH):
     print(f"WARNING: Download base path does not exist: {DOWNLOAD_BASE_PATH}. It might be created automatically, but check configuration.")