"""Schema bootstrap, run by the container entrypoint on every boot.

``create_all`` creates *missing tables* but never alters an existing one, so when
new columns are added to a model (e.g. the richer Fault fields), a database that
was first created by an older build keeps the old table shape — and inserts fail
with "column ... does not exist".

``ensure_schema`` closes that gap idempotently: after ``create_all`` it applies
additive, "IF NOT EXISTS" patches for known column/enum additions. It is safe to
run repeatedly and is a no-op once the schema is current. Postgres-only patches
are guarded by dialect (SQLite test runs build a fresh, correct schema via
``create_all`` and skip them).

For richer/destructive migrations, use Alembic (scaffolded in ``alembic/``).
"""
from __future__ import annotations

from sqlalchemy import text

from app import models  # noqa: F401 — register models on Base.metadata
from app.db import Base, engine

# Additive columns introduced after the initial schema (table -> [(name, DDL)]).
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "faults": [
        ("tip", "TEXT NOT NULL DEFAULT ''"),
        ("unit", "VARCHAR(16) NOT NULL DEFAULT ''"),
        ("confidence", "DOUBLE PRECISION NOT NULL DEFAULT 1.0"),
        ("joints", "JSON NOT NULL DEFAULT '[]'"),
    ],
    "sessions": [
        ("overall_score", "DOUBLE PRECISION DEFAULT 0.0"),
        ("summary", "JSON"),
        ("user_id", "INTEGER"),
        ("mode", "VARCHAR(16) NOT NULL DEFAULT 'upload'"),
    ],
    "reps": [
        ("set_index", "INTEGER"),
    ],
    # Email verification. Existing accounts predate the feature, so backfill them
    # as verified (DEFAULT TRUE) — new rows are inserted with FALSE by the ORM.
    "users": [
        ("email_verified", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("verified_at", "TIMESTAMP WITH TIME ZONE"),
    ],
}

# Columns that were originally NOT NULL but must now allow NULL to represent
# "no trustworthy score" (untrustworthy clips). DROP NOT NULL is idempotent.
_NULLABLE_COLUMNS: dict[str, list[str]] = {
    "sessions": ["overall_score"],
    "progress_snapshots": ["avg_score", "best_score"],
}

# Enum values added after a type was first created (type -> [values]).
_ADDED_ENUM_VALUES: dict[str, list[str]] = {
    "faultseverity": ["severe"],
}


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name != "postgresql":
        # SQLite (tests/local) gets a fresh, correct schema from create_all.
        return

    # 1. Add any missing columns (idempotent via ADD COLUMN IF NOT EXISTS).
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            for name, ddl in columns:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {ddl}'))

    # 1b. Relax columns that must now allow NULL (idempotent DROP NOT NULL).
    with engine.begin() as conn:
        for table, columns in _NULLABLE_COLUMNS.items():
            for name in columns:
                conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN {name} DROP NOT NULL'))

    # 2. Add any missing enum values. ALTER TYPE ... ADD VALUE must run outside a
    #    transaction block, so use an AUTOCOMMIT connection.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for type_name, values in _ADDED_ENUM_VALUES.items():
            for value in values:
                conn.execute(
                    text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'")
                )


def main() -> None:
    ensure_schema()
    print("physIQal schema ensured (create_all + additive patches).")


if __name__ == "__main__":
    main()
