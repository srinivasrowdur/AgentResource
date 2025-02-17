import os
from dotenv import load_dotenv
from firebase_utils import initialize_firebase, reset_database

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Firebase
    try:
        db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
        print("Firebase initialized successfully")
        
        # Reset database with 100 sample employees
        if reset_database(db):
            print("✅ Database reset successful!")
        else:
            print("❌ Database reset failed")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 