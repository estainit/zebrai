from google.oauth2 import id_token
from google.auth.transport import requests
import os
from dotenv import load_dotenv
from fastapi import Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from app.core.logging import logger
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.models.user import users

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

async def google_auth_callback(code: str, db: AsyncSession = Depends(get_db_session)):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                    "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_response.json()
            
            # Get user info using access token
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user_info = userinfo_response.json()

        # Check if user exists in database
        query = select(users).where(users.c.email == user_info["email"])
        result = await db.execute(query)
        user = result.fetchone()

        if not user:
            lang = "en"
            # Create new user
            user_data = {
                "username": user_info["email"].split("@")[0],
                "email": user_info["email"],
                "password_hash": "",  # No password for OAuth users
                "role": "user",
                "lang": lang,
                "conf": "{}"
            }
            query = users.insert().values(**user_data)
            await db.execute(query)
            await db.commit()
            
            # Get the newly created user
            query = select(users).where(users.c.email == user_info["email"])
            result = await db.execute(query)
            user = result.fetchone()

        # Create JWT token
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role}
        )

        # Return HTML that will close the popup and update the main window
        html_content = f"""
        <html>
            <body>
                <script>
                    // Send message to opener window
                    window.opener.postMessage({{
                        type: 'oauth-success',
                        token: '{access_token}',
                        username: '{user.username}'
                    }}, '*');
                    
                    // Close the popup
                    window.close();
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Google OAuth error: {str(e)}")
        html_content = f"""
        <html>
            <body>
                <script>
                    // Send error to opener window
                    window.opener.postMessage({{
                        type: 'oauth-error',
                        error: '{str(e)}'
                    }}, '*');
                    
                    // Close the popup
                    window.close();
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content) 