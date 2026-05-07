"""Dev-only schema-drift patcher.

`Base.metadata.create_all()` only creates tables that don't yet exist — it
never adds missing columns to a table that predates the code change, and it
never removes stale UNIQUE constraints inherited from an earlier revision.
In dev we want to keep your `data/app.db` (which may already have registered
users and conversations) while evolving the schema on the fly.

Two safe operations are supported here:

1. **Add missing nullable columns** via `ALTER TABLE ADD COLUMN`. Non-nullable
   additions require an Alembic migration + backfill.
2. **Drop stale column-level UNIQUE constraints** listed in
   ``KNOWN_UNIQUE_DRIFTS``. SQLite implements column UNIQUE as an auto-index
   that cannot be dropped directly, so the table is rebuilt via the standard
   rename → recreate → copy → drop dance. Data is preserved for every column
   that exists in both the old and new schema.

Deliberately gated on ``settings.app_env in {"dev", "test"}``. In production,
schema changes must always go through Alembic; this module refuses to run
there.
"""

from __future__ import annotations

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Engine

from app.config import get_settings
from app.logging_config import get_logger

_log = get_logger(__name__)


# Columns that were previously declared UNIQUE and have since been relaxed.
# Each entry causes a table rebuild if the live DB still carries the UNIQUE.
KNOWN_UNIQUE_DRIFTS: list[tuple[str, str]] = [
    # ``messages.request_id`` was UNIQUE originally, but a single user turn
    # produces multiple message rows (user + assistant + tool) sharing the
    # same request_id for log correlation, so it must be non-unique.
    ("messages", "request_id"),
]


def add_missing_columns_dev(engine: Engine, metadata: MetaData) -> tuple[list[str], list[str]]:
    """Return (added, needs_manual). No-op outside dev/test."""
    settings = get_settings()
    if settings.app_env not in {"dev", "test"}:
        return [], []

    inspector = inspect(engine)
    added: list[str] = []
    needs_manual: list[str] = []

    for table in metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in existing:
                continue
            fqcn = f"{table.name}.{col.name}"
            if not col.nullable:
                needs_manual.append(fqcn)
                continue
            col_type = col.type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(fqcn)

    if added:
        _log.warning("dev.schema.migrated", added_columns=added)
    if needs_manual:
        _log.error(
            "dev.schema.needs_manual_migration",
            not_nullable_columns=needs_manual,
            hint="Add via Alembic, or drop data/app.db and let create_all rebuild.",
        )
    return added, needs_manual


def _has_column_unique(engine: Engine, table: str, column: str) -> bool:
    """True if there's a single-column UNIQUE index on ``(column)`` in ``table``."""
    if engine.dialect.name != "sqlite":
        # For Postgres / others rely on the inspector.
        inspector = inspect(engine)
        for idx in inspector.get_indexes(table):
            if idx.get("unique") and idx.get("column_names") == [column]:
                return True
        return False

    with engine.connect() as conn:
        rows = conn.execute(text(f'PRAGMA index_list("{table}")')).fetchall()
        for _seq, name, unique, _origin, _partial in rows:
            if not unique:
                continue
            idx_info = conn.execute(text(f'PRAGMA index_info("{name}")')).fetchall()
            if len(idx_info) == 1 and idx_info[0][2] == column:
                return True
    return False


def _rebuild_table(engine: Engine, metadata: MetaData, table_name: str) -> None:
    """Rebuild ``table_name`` from its metadata definition, preserving common columns.

    Uses SQLite's standard rename→recreate→copy→drop dance so column-level
    UNIQUE auto-indexes are removed and any newly-declared indexes are put in
    place. Foreign keys are disabled for the duration of the swap so children
    aren't cascaded.
    """
    md_table = metadata.tables[table_name]
    inspector = inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
    expected_cols = {c.name for c in md_table.columns}
    common = existing_cols & expected_cols
    if not common:
        return

    col_list = ", ".join(f'"{c}"' for c in sorted(common))
    tmp_name = f"__{table_name}_pre_rebuild"

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text(f'DROP TABLE IF EXISTS "{tmp_name}"'))
        conn.execute(text(f'ALTER TABLE "{table_name}" RENAME TO "{tmp_name}"'))

    # `Table.create` builds the table AND all its declared indexes.
    md_table.create(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                f'INSERT INTO "{table_name}" ({col_list}) '
                f'SELECT {col_list} FROM "{tmp_name}"'
            )
        )
        conn.execute(text(f'DROP TABLE "{tmp_name}"'))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def drop_stale_unique_indexes_dev(engine: Engine, metadata: MetaData) -> list[str]:
    """Rebuild any table whose live schema still carries a UNIQUE we removed."""
    settings = get_settings()
    if settings.app_env not in {"dev", "test"}:
        return []

    inspector = inspect(engine)
    rebuilt: list[str] = []

    for table, column in KNOWN_UNIQUE_DRIFTS:
        if not inspector.has_table(table):
            continue
        if not _has_column_unique(engine, table, column):
            continue

        # Only rebuild if the current ORM says the column should NOT be unique.
        md_table = metadata.tables.get(table)
        if md_table is None:
            continue
        col = md_table.columns.get(column)
        if col is None:
            continue
        if col.unique:
            continue  # ORM still declares unique — nothing to do.

        _rebuild_table(engine, metadata, table)
        rebuilt.append(f"{table}.{column}")

    if rebuilt:
        _log.warning("dev.schema.unique_drift_removed", tables=rebuilt)
    return rebuilt
