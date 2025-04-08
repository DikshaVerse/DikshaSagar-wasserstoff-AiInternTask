import os
from google.oauth2 import service_account
from update_env import update_env  # Your existing function

def rotate_google_key():
    # 1. Create new key via Google Cloud API
    credentials = service_account.Credentials.from_service_account_file('service-account.json')
    new_key = create_google_key(credentials)  # Implement API call
    
    # 2. Update .env
    update_env("GOOGLE_API_KEY", new_key)
    
    # 3. Delete old key after 24h
    schedule_key_deletion(old_key)