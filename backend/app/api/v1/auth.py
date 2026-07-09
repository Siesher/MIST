"""Authentication endpoints and dependencies."""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import backend_settings
from backend.app.models.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    verify_token,
)
from backend.app.models.database import get_db
from backend.app.models.tables import RefreshTokenTable, UserTable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)

# ── Login throttling (in-memory, per-IP) ────────────────────

_AUTH_RATE_LIMIT = 10  # попыток в окно
_AUTH_RATE_WINDOW = 60.0  # секунд
_auth_attempts: dict[str, deque] = defaultdict(deque)

# Анонимная квота LLM-путей (per-IP, in-memory): публичный инстанс нельзя
# бесплатно выжигать GPU-временем. Авторизованные пользователи — без квоты.
_anon_llm_calls: dict[str, deque] = defaultdict(deque)


def _check_auth_rate(request: Request) -> None:
    """Троттлинг /auth: не более N попыток в окно с одного IP.

    In-memory, сбрасывается при рестарте — для single-instance деплоя достаточно.
    """
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _auth_attempts[ip]
    while attempts and now - attempts[0] > _AUTH_RATE_WINDOW:
        attempts.popleft()
    if len(attempts) >= _AUTH_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Слишком много попыток — повторите через минуту")
    attempts.append(now)


def ensure_session_access(session_user_id: str | None, user: "UserTable | None") -> None:
    """Capability-based ownership: сессия пользователя доступна только ему.

    Анонимные сессии (user_id=NULL) доступны по знанию UUID — это сохраняет
    демо-режим без логина. 404 вместо 403, чтобы не подтверждать существование
    чужой сессии (анти-enumeration).
    """
    if session_user_id is not None and (user is None or user.id != session_user_id):
        raise HTTPException(status_code=404, detail="Session not found")


async def _purge_stale_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    """Удаляет протухшие/отозванные refresh-токены пользователя.

    Иначе refresh_tokens растёт неограниченно: каждый login/refresh добавляет
    строку, а revoke только ставит флаг.
    """
    await db.execute(
        delete(RefreshTokenTable).where(
            RefreshTokenTable.user_id == user_id,
            or_(
                RefreshTokenTable.expires_at < datetime.now(timezone.utc),
                RefreshTokenTable.revoked.is_(True),
            ),
        )
    )


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


def check_anon_llm_quota(ip: str) -> bool:
    """Скользящее окно анонимных LLM-вызовов на IP.

    True — вызов учтён и разрешён; False — квота исчерпана.
    Отдельная функция (а не Depends), чтобы WebSocket мог вызывать её вручную.
    """
    now = time.monotonic()
    calls = _anon_llm_calls[ip]
    while calls and now - calls[0] > backend_settings.ANON_LLM_WINDOW:
        calls.popleft()
    if len(calls) >= backend_settings.ANON_LLM_LIMIT:
        return False
    calls.append(now)
    return True


async def require_llm_budget(
    request: Request,
    user: UserTable | None = Depends(get_optional_user),
) -> UserTable | None:
    """Гейт дорогих LLM-эндпоинтов; возвращает пользователя (или None).

    Авторизованный проходит всегда. Аноним: при REQUIRE_AUTH — 401 (публичный
    инстанс), иначе per-IP квота ANON_LLM_LIMIT/ANON_LLM_WINDOW, при
    исчерпании — 429. Возвращает то же, что get_optional_user, поэтому
    подменяет его в сигнатурах без изменения session-scoping логики.
    """
    if user is not None:
        return user
    if backend_settings.REQUIRE_AUTH:
        raise HTTPException(
            status_code=401,
            detail="Требуется вход: анонимный доступ отключён на этом инстансе",
        )
    ip = request.client.host if request.client else "unknown"
    if not check_anon_llm_quota(ip):
        raise HTTPException(
            status_code=429,
            detail="Анонимная квота LLM-запросов исчерпана — войдите в аккаунт или повторите позже",
        )
    return None


# ── Endpoints ───────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    _check_auth_rate(http_request)
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
    db.add(
        RefreshTokenTable(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        )
    )

    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, http_request: Request, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    _check_auth_rate(http_request)
    result = await db.execute(select(UserTable).where(UserTable.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login_at = datetime.now(timezone.utc)
    await _purge_stale_refresh_tokens(db, user.id)

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    refresh_payload = verify_token(refresh)
    db.add(
        RefreshTokenTable(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        )
    )

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

    # flush до bulk-delete: иначе pending UPDATE целится в строку, которую purge уже удалил
    await db.flush()
    await _purge_stale_refresh_tokens(db, user.id)

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    refresh_payload = verify_token(refresh)
    db.add(
        RefreshTokenTable(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        )
    )

    await db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=204)
async def logout(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Logout — revoke refresh token."""
    token_h = hash_token(request.refresh_token)
    result = await db.execute(select(RefreshTokenTable).where(RefreshTokenTable.token_hash == token_h))
    stored = result.scalar_one_or_none()
    if stored:
        stored.revoked = True
        await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserTable = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_mode=user.preferred_mode,
        created_at=user.created_at,
    )
