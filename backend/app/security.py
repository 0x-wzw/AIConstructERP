"""Authentication & authorization: password hashing, JWT, RBAC dependencies."""
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


class Role(str, Enum):
    admin = "admin"
    project_manager = "project_manager"
    accounting = "accounting"
    viewer = "viewer"


# ── Passwords ─────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    # bcrypt has a 72-byte cap; truncate defensively so long inputs don't error.
    return bcrypt.hashpw(plain.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except ValueError:
        return False


# ── JWT ───────────────────────────────────────────────────────────────
def create_access_token(*, subject: str | int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise _credentials_exc
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
