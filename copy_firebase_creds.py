import json
import os
from pathlib import Path

def format_firebase_creds(creds_path):
    """Read Firebase credentials from JSON and format for Streamlit secrets"""
    try:
        # Read the Firebase service account JSON file
        with open(creds_path, 'r') as f:
            creds = json.load(f)
            
        # Format credentials for Streamlit secrets
        formatted_creds = {
            "firebase": {
                "my_project_settings": {
                    "type": creds.get("type"),
                    "project_id": creds.get("project_id"),
                    "private_key_id": creds.get("private_key_id"),
                    "private_key": creds.get("private_key"),
                    "client_email": creds.get("client_email"),
                    "client_id": creds.get("client_id"),
                    "auth_uri": creds.get("auth_uri"),
                    "token_uri": creds.get("token_uri"),
                    "auth_provider_x509_cert_url": creds.get("auth_provider_x509_cert_url"),
                    "client_x509_cert_url": creds.get("client_x509_cert_url")
                }
            }
        }
        
        return formatted_creds
        
    except Exception as e:
        print(f"Error reading credentials: {str(e)}")
        return None

def save_formatted_creds(formatted_creds, output_path):
    """Save formatted credentials to a JSON file"""
    try:
        with open(output_path, 'w') as f:
            json.dump(formatted_creds, f, indent=2)
        print(f"✅ Credentials saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving credentials: {str(e)}")
        return False

def main():
    # Get input and output paths
    creds_path = input("Enter path to Firebase credentials JSON file: ")
    output_path = input("Enter path for formatted credentials output (default: .streamlit/secrets.toml): ")
    
    if not output_path:
        output_path = ".streamlit/secrets.toml"
    
    # Ensure input file exists
    if not os.path.exists(creds_path):
        print(f"❌ Input file not found: {creds_path}")
        return
    
    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Format credentials
    formatted_creds = format_firebase_creds(creds_path)
    if not formatted_creds:
        return
    
    # Save formatted credentials
    if save_formatted_creds(formatted_creds, output_path):
        print("\nNext steps:")
        print("1. If using Streamlit Cloud, copy the contents of the output file")
        print("2. Go to your Streamlit Cloud dashboard")
        print("3. Navigate to your app's settings")
        print("4. Paste the contents into the 'Secrets' section")

if __name__ == "__main__":
    main()