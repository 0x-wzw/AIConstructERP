"""Authentication & authorization: password → JWT, RBAC dependencies.

Tokens include: sub (user_id), role, tenant_id, type (access|refresh).
Access tokens expire in ACCESS_TOKEN_EXPIRE_MINUTES (default 60).
Refresh tokens expire in REFRESH_TOKEN_EXPIRE_DAYS (default 7).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

# bcrypt max password is 72 bytes.
MAX_PASSWORD_BYTES = 72


class Role(str, Enum):
    admin = "admin"
    project_manager = "project_manager"
    accounting = "accounting"
    viewer = "viewer"


# ── Passwords ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    if len(plain.encode()) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes",
        )
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


# ── JWT ───────────────────────────────────────────────────────────────
def create_access_token(*, subject: str | int, role: str, tenant_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "tenant_id": tenant_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(*, subject: str | int, role: str, tenant_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "tenant_id": tenant_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=7),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise _credentials_exc


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = _decode_token(token)
    if payload.get("type") not in (None, "access"):
        raise _credentials_exc
    user_id = int(payload.get("sub"))
    user = db.get(User, user_id)
    if user is None:
        raise _credentials_exc
    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def require_roles(*roles: str):
    """Dependency factory — allow only the given roles (admin always allowed)."""
    allowed = {r.value if isinstance(r, Role) else r for r in roles} | {Role.admin.value}

    def dependency(user: User = Depends(get_current_active_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {sorted(allowed)}",
            )
        return user

    return dependency