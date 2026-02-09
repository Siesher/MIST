"""Authentication endpoints and dependencies."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.database import get_db
from backend.app.models.tables import UserTable, RefreshTokenTable
from backend.app.models.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    verify_token, hash_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)


# ── Schemas ─────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    preferred_mode: str
    created_at: datetime


# ── Dependencies ────────────────────────────────────────────


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserTable:
    """FastAPI dependency: verify JWT and return current user."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    payload = verify_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.get(UserTable, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UserTable | None:
    """Returns user if token provided, None otherwise (backward compat)."""
    if not credentials:
        return None
    payload = verify_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    return await db.get(UserTable, payload["sub"])


# ── Endpoints ───────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    existing = await db.execute(select(UserTable).where(UserTable.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = UserTable(
        email=request.email,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
    )
    db.add(user)
    await db.flush()

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    refresh_payload = verify_token(refresh)
    db.add(RefreshTokenTable(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
    ))

    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    result = await db.execute(select(UserTable).where(UserTable.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login_at = datetime.now(timezone.utc)

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    refresh_payload = verify_token(refresh)
    db.add(RefreshTokenTable(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
    ))

    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    payload = verify_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_h = hash_token(request.refresh_token)
    result = await db.execute(
        select(RefreshTokenTable).where(
            RefreshTokenTable.token_hash == token_h,
            RefreshTokenTable.revoked == False,
        )
    )
    stored_token = result.scalar_one_or_none()
    if not stored_token:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    stored_token.revoked = True

    user = await db.get(UserTable, payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    refresh_payload = verify_token(refresh)
    db.add(RefreshTokenTable(
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
    ))

    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=204)
async def logout(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Logout — revoke refresh token."""
    token_h = hash_token(request.refresh_token)
    result = await db.execute(
        select(RefreshTokenTable).where(RefreshTokenTable.token_hash == token_h)
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True
        await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserTable = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=user.id, email=user.email,
        display_name=user.display_name,
        preferred_mode=user.preferred_mode,
        created_at=user.created_at,
    )
