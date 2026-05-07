"""Custom SQLAlchemy column types."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import String, TypeDecorator
from sqlalchemy.types import TEXT

from app.crypto import decrypt, encrypt


class EncryptedString(TypeDecorator):
    """Transparent Fernet encrypt/decrypt for text columns."""

    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value: Any, _dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        return encrypt(value)

    def process_result_value(self, value: Any, _dialect) -> Any:
        if value is None:
            return None
        return decrypt(value)


class EncryptedJSON(TypeDecorator):
    """Encrypt JSON at rest (used for header dicts, env allow-lists)."""

    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value: Any, _dialect) -> Any:
        if value is None:
            return None
        return encrypt(json.dumps(value, ensure_ascii=False, sort_keys=True))

    def process_result_value(self, value: Any, _dialect) -> Any:
        if value is None:
            return None
        return json.loads(decrypt(value))


class UUIDString(TypeDecorator):
    """Stringly-typed UUID column (CHAR(36))."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, _dialect) -> Any:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, _dialect) -> Any:
        return value
