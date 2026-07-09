"""JWT token and password hashing utilities."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.app.config import backend_settings

_ph = PasswordHasher()


# ── Password hashing ────────────────────────────────────────


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# ── JWT tokens ──────────────────────────────────────────────


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=backend_settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, backend_settings.JWT_SECRET_KEY, algorithm=backend_settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "exp": datetime.now(timezone.utc) + timedelta(days=backend_settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, backend_settings.JWT_SECRET_KEY, algorithm=backend_settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns payload dict or None if invalid."""
    try:
        payload = jwt.decode(token, backend_settings.JWT_SECRET_KEY, algorithms=[backend_settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def hash_token(token: str) -> str:
    """Hash a refresh token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
