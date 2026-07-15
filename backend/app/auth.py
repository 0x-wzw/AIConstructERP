"""Authentication & user-management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .database import get_db
from .security import (
    Role,
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    hash_password,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_user(db: Session, *, email: str, password: str, full_name: str, role: str,
                 tenant_id: Optional[int] = None) -> models.User:
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = models.User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        tenant_id=tenant_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", response_model=schemas.UserRead, status_code=201,
             summary="Public self-signup (role: viewer)")
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    return _create_user(
        db, email=payload.email, password=payload.password,
        full_name=payload.full_name, role=Role.viewer.value,
    )


@router.post("/token", response_model=schemas.Token, summary="Login (OAuth2 password flow)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    token = create_access_token(
        subject=user.id, role=user.role, tenant_id=user.tenant_id
    )
    refresh = create_refresh_token(
        subject=user.id, role=user.role, tenant_id=user.tenant_id
    )
    return schemas.Token(
        access_token=token, refresh_token=refresh, role=user.role,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=schemas.Token, summary="Refresh access token")
def refresh_token(payload: dict, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access + refresh token pair.

    Body: {"refresh_token": "..."}
    """
    import jwt as pyjwt
    token = payload.get("refresh_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token is required")
    try:
        decoded = pyjwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token has expired")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id_raw = decoded.get("sub")
    if user_id_raw is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user_id = int(user_id_raw)
    user = db.get(models.User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_access = create_access_token(
        subject=user.id, role=user.role, tenant_id=user.tenant_id
    )
    new_refresh = create_refresh_token(
        subject=user.id, role=user.role, tenant_id=user.tenant_id
    )
    return schemas.Token(
        access_token=new_access, refresh_token=new_refresh, role=user.role,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=schemas.UserRead, summary="Current user")
def me(user: models.User = Depends(get_current_active_user)):
    return user


# ── Admin-only user management ────────────────────────────────────────
@router.get("/users", response_model=List[schemas.UserRead],
            dependencies=[Depends(require_roles(Role.admin))], summary="List users (admin)")
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id).all()


@router.post("/users", response_model=schemas.UserRead, status_code=201,
             dependencies=[Depends(require_roles(Role.admin))], summary="Create user (admin)")
def create_user(payload: schemas.UserAdminCreate, db: Session = Depends(get_db)):
    return _create_user(
        db, email=payload.email, password=payload.password,
        full_name=payload.full_name, role=payload.role, tenant_id=payload.tenant_id,
    )


@router.patch("/users/{user_id}", response_model=schemas.UserRead,
              dependencies=[Depends(require_roles(Role.admin))], summary="Update user (admin)")
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.hashed_password = hash_password(data.pop("password"))
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user