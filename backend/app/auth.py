"""Authentication & user-management endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .database import get_db
from .security import (
    Role,
    create_access_token,
    get_current_active_user,
    hash_password,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_user(db: Session, *, email: str, password: str, full_name: str, role: str) -> models.User:
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = models.User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
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
    token = create_access_token(subject=user.id, role=user.role)
    return schemas.Token(
        access_token=token, role=user.role,
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
        full_name=payload.full_name, role=payload.role,
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
