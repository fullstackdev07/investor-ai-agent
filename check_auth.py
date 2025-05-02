import google.auth
import google.auth.exceptions
import os
from dotenv import load_dotenv

print("Attempting to find default Google credentials using google.auth.default()...")

try:
    credentials, project_id = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])

    print("\n--- SUCCESS! ---")
    print("google.auth.default() found credentials successfully.")

    if hasattr(credentials, 'service_account_email'):
        print(f"Credential Type: Service Account ({credentials.service_account_email})")
    elif hasattr(credentials, 'token'):
        print("Credential Type: User Account (ADC)")
    else:
        print("Credential Type: Unknown (but found)")

    print(f"Default Project ID detected by google.auth: {project_id}")

    load_dotenv()
    expected_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if expected_project:
        print(f"Project ID expected from .env file:    {expected_project}")
        if project_id and project_id == expected_project:
            print("-> Detected Project ID matches .env file.")
        elif project_id:
            print("-> WARNING: Detected Project ID does NOT match .env file!")
        else:
            print("-> WARNING: Could not detect a default project ID via google.auth, but .env has one.")
    else:
        print("Could not find GOOGLE_CLOUD_PROJECT in .env for comparison.")

except google.auth.exceptions.DefaultCredentialsError as e:
    print("\n--- FAILURE ---")
    print("google.auth.default() FAILED to find credentials.")
    print("This confirms the core authentication problem.")
    print("--> Please run 'gcloud auth application-default login' successfully in your terminal.")
    print(f"Error details: {e}")

except Exception as e:
    print("\n--- UNEXPECTED ERROR during authentication check ---")
    print(f"Error Type: {type(e)}")
    print(f"Details: {e}")