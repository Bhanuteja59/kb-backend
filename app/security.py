from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = settings.jwt_algorithm

class TokenData(BaseModel):
    sub: str
    role: str
    exp: int

def hash_password(password: str) -> str:
    # truncate to 72 bytes to satisfy bcrypt
    password = password[:72]
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(subject: str, role: str, expires_minutes: int = 60*24) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "role": role, "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
