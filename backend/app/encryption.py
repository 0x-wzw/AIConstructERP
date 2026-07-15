"""Encryption for two-bid opening (encrypted financial proposals).

In a two-bid opening system:
  - Technical proposals are opened immediately at tender close
  - Financial proposals are encrypted and only opened after technical evaluation

This module provides:
  - Symmetric encryption (Fernet) for simplicity
  - Key management (auto-generate on first use)
  - Encrypt/decrypt for bid submissions
"""
from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import settings


_fernet_cache = None


def _get_fernet() -> Fernet:
    """Get or derive a Fernet key from settings.
    
    Caches the Fernet instance so encrypt/decrypt use the same key.
    If no encryption_key is configured, generates one (dev mode).
    In production, set ENCRYPTION_KEY to a stable value.
    """
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache

    key = settings.encryption_key
    if not key:
        # Dev mode: generate a key (will change on restart — dev only!)
        key = Fernet.generate_key().decode()
    elif len(key) != 44:
        # Derive a 32-byte key from the configured string
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"constructerp-encryption-salt",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
    else:
        key = key.encode() if isinstance(key, str) else key

    _fernet_cache = Fernet(key)
    return _fernet_cache


def encrypt_financial_proposal(data: bytes) -> bytes:
    """Encrypt financial proposal data.
    
    Returns encrypted bytes that can be stored in a file.
    """
    f = _get_fernet()
    return f.encrypt(data)


def decrypt_financial_proposal(encrypted_data: bytes) -> bytes:
    """Decrypt financial proposal data.
    
    Only callable by authorized users (e.g. after technical evaluation is complete).
    """
    f = _get_fernet()
    return f.decrypt(encrypted_data)


def encrypt_file_for_bidder(file_path: str) -> bytes:
    """Read a file and encrypt it for secure storage."""
    with open(file_path, "rb") as f:
        data = f.read()
    return encrypt_financial_proposal(data)


def generate_encryption_key() -> str:
    """Generate a new Fernet key for production use.
    
    Usage:
        python -c "from app.encryption import generate_encryption_key; print(generate_encryption_key())"
    """
    return Fernet.generate_key().decode()
