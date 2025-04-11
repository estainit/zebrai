from google.oauth2 import id_token
from google.auth.transport import requests
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

async def verify_google_token(token):
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID
        )

        # Check if the token was issued to our client
        if idinfo['aud'] != GOOGLE_CLIENT_ID:
            raise ValueError('Invalid audience')

        # Return user information
        return {
            'email': idinfo['email'],
            'name': idinfo.get('name', ''),
            'picture': idinfo.get('picture', ''),
            'sub': idinfo['sub']  # Google's unique user ID
        }
    except Exception as e:
        raise ValueError(f'Invalid token: {str(e)}') 