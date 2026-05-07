"""Fernet-based encryption for secrets at rest.

Master key comes from ``MASTER_KEY`` env var (base64 urlsafe 32 bytes).
In dev, when unset, a deterministic key is derived so tests don't need extra
setup — that path emits a loud warning and refuses to run in non-dev envs.
"""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoError(RuntimeError):
    pass


def _derive_dev_key() -> bytes:
    """Deterministic key derived from the app name — dev/test convenience only."""
    seed = b"agent-ui-dev-master-key-do-not-use-in-prod"
    return base64.urlsafe_b64encode(hashlib.sha256(seed).digest())


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.master_key.strip()

    if not key:
        if settings.app_env not in {"dev", "test"}:
            raise CryptoError(
                "MASTER_KEY is required in non-dev environments. "
                "Generate one with: python -c \"import secrets, base64; "
                "print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\""
            )
        # Dev fallback
        os.environ.setdefault("MASTER_KEY_IS_DEV", "1")
        return Fernet(_derive_dev_key())

    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"MASTER_KEY is not a valid Fernet key: {exc}") from exc


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        raise CryptoError("Cannot encrypt None")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    if token is None:
        raise CryptoError("Cannot decrypt None")
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoError("Invalid ciphertext / wrong master key") from exc


def reset_cache() -> None:
    """Clear the cached Fernet — call after env changes in tests."""
    _fernet.cache_clear()
