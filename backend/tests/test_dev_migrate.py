"""Dev-only startup schema-drift patcher."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import Base, get_engine, init_engine
from app.dev_migrate import (
    _has_column_unique,
    add_missing_columns_dev,
    drop_stale_unique_indexes_dev,
)


def test_dev_migrate_adds_missing_nullable_column(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/drift.db")

    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    init_engine(get_settings().database_url)
    engine = get_engine()

    # Simulate a pre-existing DB that pre-dates the `api_version` column.
    with engine.begin() as con:
        con.execute(
            text(
                """
                CREATE TABLE provider_models (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    provider_type VARCHAR(32) NOT NULL,
                    endpoint_url VARCHAR(1024),
                    model_name VARCHAR(200) NOT NULL,
                    api_key_encrypted TEXT,
                    extra_headers_encrypted TEXT,
                    default_system_prompt TEXT,
                    supports_vision BOOLEAN NOT NULL DEFAULT 0,
                    supports_tools BOOLEAN NOT NULL DEFAULT 1,
                    context_window_tokens INTEGER,
                    price_input_per_mtok_usd NUMERIC(10,4),
                    price_output_per_mtok_usd NUMERIC(10,4),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    added, manual = add_missing_columns_dev(engine, Base.metadata)

    assert "provider_models.api_version" in added
    assert manual == [] or all("api_version" not in c for c in manual)

    cols = {c["name"] for c in inspect(engine).get_columns("provider_models")}
    assert "api_version" in cols

    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_dev_migrate_is_noop_in_prod(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("MASTER_KEY", "K2vG1r8i0V6oJ8XPoRw2Zg2QIvPCr7Bz1yA6cSc6a0M=")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/prod.db")

    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    init_engine(get_settings().database_url)
    engine = get_engine()

    with engine.begin() as con:
        con.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email TEXT)"))

    added, manual = add_missing_columns_dev(engine, Base.metadata)

    assert added == []
    assert manual == []

    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_drop_stale_unique_rebuilds_table_preserving_data(tmp_path, monkeypatch):
    """A pre-existing messages table with UNIQUE(request_id) must be rebuilt
    without the constraint, and every row must survive."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/stale_unique.db")

    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    init_engine(get_settings().database_url)
    engine = get_engine()

    # Build the pre-existing tables the way the OLD schema had them:
    # messages.request_id declared UNIQUE inline.
    with engine.begin() as con:
        con.execute(
            text(
                """
                CREATE TABLE conversations (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    title VARCHAR(200),
                    provider_model_id VARCHAR(36) NOT NULL,
                    system_prompt_override TEXT,
                    active_leaf_message_id VARCHAR(36),
                    is_shared BOOLEAN NOT NULL DEFAULT 0,
                    share_slug VARCHAR(64) UNIQUE,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        con.execute(
            text(
                """
                CREATE TABLE messages (
                    id VARCHAR(36) PRIMARY KEY,
                    conversation_id VARCHAR(36) NOT NULL,
                    request_id VARCHAR(36) NOT NULL UNIQUE,
                    parent_message_id VARCHAR(36),
                    role VARCHAR(16) NOT NULL,
                    content_json TEXT NOT NULL,
                    tool_calls_json TEXT,
                    tool_call_id VARCHAR(200),
                    tool_name VARCHAR(200),
                    provider_snapshot VARCHAR(200),
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_usd NUMERIC(12,6),
                    latency_ms INTEGER,
                    finish_reason VARCHAR(32),
                    error_message TEXT,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        con.execute(
            text(
                "INSERT INTO messages (id, conversation_id, request_id, role, content_json) "
                "VALUES ('m1', 'c1', 'req-A', 'user', '[]'), "
                "('m2', 'c1', 'req-B', 'assistant', '[]')"
            )
        )

    # Pre-check: the stale UNIQUE really exists.
    assert _has_column_unique(engine, "messages", "request_id") is True

    rebuilt = drop_stale_unique_indexes_dev(engine, Base.metadata)
    assert rebuilt == ["messages.request_id"]

    # Post-check: UNIQUE is gone AND rows survived.
    assert _has_column_unique(engine, "messages", "request_id") is False

    with engine.connect() as con:
        rows = con.execute(text("SELECT id, request_id, role FROM messages ORDER BY id")).fetchall()
    assert rows == [("m1", "req-A", "user"), ("m2", "req-B", "assistant")]

    # And the killer proof — inserting a duplicate request_id (representing the
    # assistant + tool rows of one turn) now succeeds.
    with engine.begin() as con:
        con.execute(
            text(
                "INSERT INTO messages (id, conversation_id, request_id, role, content_json, is_deleted) "
                "VALUES ('m3', 'c1', 'req-A', 'tool', '[]', 0)"
            )
        )

    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_drop_stale_unique_noop_when_not_present(tmp_path, monkeypatch):
    """If the live schema already matches the ORM, no rebuild happens."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/fresh.db")

    from app.config import get_settings
    from app.db import create_all

    get_settings.cache_clear()  # type: ignore[attr-defined]

    init_engine(get_settings().database_url)
    engine = get_engine()
    create_all()

    rebuilt = drop_stale_unique_indexes_dev(engine, Base.metadata)
    assert rebuilt == []

    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_drop_stale_unique_noop_in_prod(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("MASTER_KEY", "K2vG1r8i0V6oJ8XPoRw2Zg2QIvPCr7Bz1yA6cSc6a0M=")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/prod2.db")

    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]

    init_engine(get_settings().database_url)
    engine = get_engine()

    with engine.begin() as con:
        con.execute(text("CREATE TABLE messages (id VARCHAR(36), request_id TEXT UNIQUE)"))

    rebuilt = drop_stale_unique_indexes_dev(engine, Base.metadata)
    assert rebuilt == []

    get_settings.cache_clear()  # type: ignore[attr-defined]
