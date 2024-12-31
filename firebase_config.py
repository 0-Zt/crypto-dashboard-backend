import firebase_admin
from firebase_admin import credentials, auth

def initialize_firebase():
    try:
        # Initialize Firebase Admin SDK
        # You'll need to replace 'path/to/serviceAccountKey.json' with your actual service account key path
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except ValueError:
        # App already exists
        pass

def verify_firebase_token(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        return None
