from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import load_weekly_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_database_path() -> Path:
    """
    Resolve the weekly_v1 SQLite database path.

    OPTIONS_FLOW_DB_PATH is a deployment-only override
    for persistent storage environments such as Render.

    When the environment variable is absent, local
    behavior remains unchanged and weekly_config.yaml
    remains authoritative.
    """

    env_path = os.getenv("OPTIONS_FLOW_DB_PATH")

    if env_path:
        return Path(env_path).expanduser().resolve()

    config = load_weekly_config(
        require_runtime_ready=True
    )

    configured_path = Path(
        config["database"]["path"]
    )

    if configured_path.is_absolute():
        return configured_path

    return PROJECT_ROOT / configured_path


def create_connection() -> sqlite3.Connection:
    """
    Create a weekly_v1 SQLite connection using the
    mandatory concurrency/safety PRAGMAs.
    """

    config = load_weekly_config(
        require_runtime_ready=True
    )

    db_path = get_database_path()

    db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    busy_timeout_ms = int(
        config["database"]["busy_timeout_ms"]
    )

    connection = sqlite3.connect(
        db_path,
        timeout=busy_timeout_ms / 1000,
        check_same_thread=False,
    )

    # Return rows that support:
    # row["column_name"]
    connection.row_factory = sqlite3.Row

    journal_mode = str(
        config["database"]["journal_mode"]
    ).upper()

    connection.execute(
        f"PRAGMA journal_mode={journal_mode};"
    )

    connection.execute(
        f"PRAGMA busy_timeout={busy_timeout_ms};"
    )

    foreign_keys = bool(
        config["database"]["foreign_keys"]
    )

    connection.execute(
        "PRAGMA foreign_keys="
        + ("ON" if foreign_keys else "OFF")
        + ";"
    )

    return connection


@contextmanager
def database_connection() -> Iterator[
    sqlite3.Connection
]:
    """
    Safe connection context.

    Usage:

        with database_connection() as conn:
            ...
    """

    connection = create_connection()

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def database_transaction() -> Iterator[
    sqlite3.Connection
]:
    """
    Short transactional context.

    weekly_v1 requires state transitions and related
    writes to happen atomically.

    Commit on success.
    Roll back automatically on failure.
    """

    connection = create_connection()

    try:
        connection.execute(
            "BEGIN IMMEDIATE;"
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def verify_database_settings() -> dict:
    """
    Verify the actual SQLite runtime settings.

    This checks SQLite itself, rather than merely
    trusting weekly_config.yaml.
    """

    with database_connection() as connection:

        journal_mode = connection.execute(
            "PRAGMA journal_mode;"
        ).fetchone()[0]

        busy_timeout = connection.execute(
            "PRAGMA busy_timeout;"
        ).fetchone()[0]

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()[0]

    return {
        "database_path": str(
            get_database_path()
        ),
        "journal_mode": str(
            journal_mode
        ).upper(),
        "busy_timeout_ms": int(
            busy_timeout
        ),
        "foreign_keys": bool(
            foreign_keys
        ),
    }


if __name__ == "__main__":

    settings = verify_database_settings()

    print(
        "weekly_v1 database connection: VALID"
    )

    print(
        "database_path:",
        settings["database_path"],
    )

    print(
        "journal_mode:",
        settings["journal_mode"],
    )

    print(
        "busy_timeout_ms:",
        settings["busy_timeout_ms"],
    )

    print(
        "foreign_keys:",
        settings["foreign_keys"],
    )