import httpx
from .config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

def get_google_auth_url(redirect_uri: str) -> str:
    """
    Generates the Google OAuth consent screen URL.
    """
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    return f"{GOOGLE_AUTH_URL}?{query_string}"


async def get_google_user_info(code: str, redirect_uri: str) -> dict:
    """
    Exchanges the authorization code for an access token and retrieves user info.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("Google Client ID/Secret not configured")

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        token_res = await client.post(GOOGLE_TOKEN_URL, data=token_data)
        token_res.raise_for_status()
        tokens = token_res.json()
        access_token = tokens["access_token"]

        # Get user info
        user_res = await client.get(
            GOOGLE_USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_res.raise_for_status()
        return user_res.json()
