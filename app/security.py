from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from pydantic import BaseModel
from .config import settings

ALGORITHM = settings.jwt_algorithm

class TokenData(BaseModel):
    sub: str
    exp: int

def create_access_token(subject: str, expires_minutes: int = 60 * 24) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
