"""Password hashing (Argon2id) and JWT helpers."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


def new_opaque_token(nbytes: int = 48) -> str:
    return secrets.token_urlsafe(nbytes)


def create_access_token(
    *,
    user_id: str,
    email: str,
    role: str,
    ttl_min: int | None = None,
) -> tuple[str, datetime]:
    s = get_settings()
    ttl = ttl_min if ttl_min is not None else s.jwt_access_ttl_min
    exp = now_utc() + timedelta(minutes=ttl)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "jti": new_uuid(),
        "iat": int(now_utc().timestamp()),
        "exp": int(exp.timestamp()),
        "typ": "access",
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, exp


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])


def token_hash(opaque: str) -> str:
    """SHA-256 hex of a refresh token — never store the raw token."""
    import hashlib

    return hashlib.sha256(opaque.encode("utf-8")).hexdigest()
