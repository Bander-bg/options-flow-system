from __future__ import annotations

import hashlib
import re
from pathlib import Path

from weekly.db.database import database_connection


MIGRATIONS_DIR = (
    Path(__file__).resolve().parent
    / "migrations"
)

MIGRATION_FILE_PATTERN = re.compile(
    r"^(?P<version>\d{3})_(?P<name>[a-z0-9_]+)\.sql$"
)


def calculate_checksum(
    migration_path: Path,
) -> str:
    content = migration_path.read_bytes()

    return hashlib.sha256(
        content
    ).hexdigest()


def ensure_schema_migrations_table() -> None:
    """
    Bootstrap table used to track which migrations
    have already been applied.

    This table is intentionally created by the migration
    runner itself, so the runner can safely operate on a
    completely empty database.
    """

    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
                    DEFAULT (
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now'
                        )
                    )
            );
            """
        )

        connection.commit()


def discover_migrations() -> list[dict]:
    """
    Discover migration files in ascending version order.

    Required filename format:

        001_initial_schema.sql
        002_add_example.sql
    """

    discovered = []

    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(
            f"Migrations directory does not exist: "
            f"{MIGRATIONS_DIR}"
        )

    for path in MIGRATIONS_DIR.glob(
        "*.sql"
    ):
        match = MIGRATION_FILE_PATTERN.match(
            path.name
        )

        if not match:
            raise RuntimeError(
                "Invalid migration filename: "
                f"{path.name}"
            )

        discovered.append(
            {
                "version": int(
                    match.group("version")
                ),
                "name": match.group(
                    "name"
                ),
                "path": path,
                "checksum": (
                    calculate_checksum(path)
                ),
            }
        )

    discovered.sort(
        key=lambda item: item["version"]
    )

    versions = [
        item["version"]
        for item in discovered
    ]

    if len(versions) != len(
        set(versions)
    ):
        raise RuntimeError(
            "Duplicate migration version detected."
        )

    return discovered


def get_applied_migrations() -> dict[int, dict]:
    with database_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                version,
                name,
                checksum,
                applied_at
            FROM schema_migrations
            ORDER BY version;
            """
        ).fetchall()

    return {
        int(row["version"]): {
            "name": row["name"],
            "checksum": row["checksum"],
            "applied_at": row["applied_at"],
        }
        for row in rows
    }


def validate_applied_checksums(
    discovered: list[dict],
    applied: dict[int, dict],
) -> None:
    """
    An already-applied migration must never be silently
    edited afterward.

    If its SQL file changes, startup fails loudly.
    """

    discovered_by_version = {
        migration["version"]: migration
        for migration in discovered
    }

    for version, applied_row in applied.items():
        migration = discovered_by_version.get(
            version
        )

        if migration is None:
            raise RuntimeError(
                "Applied migration file is missing: "
                f"version {version:03d}"
            )

        if (
            migration["checksum"]
            != applied_row["checksum"]
        ):
            raise RuntimeError(
                "Migration checksum mismatch for "
                f"version {version:03d}. "
                "An already-applied migration was "
                "modified."
            )


def apply_single_migration(
    migration: dict,
) -> None:
    """
    Apply the schema change AND register its migration
    version inside one SQLite transaction.

    If any statement fails, neither the schema change
    nor schema_migrations record is committed.
    """

    sql = migration[
        "path"
    ].read_text(
        encoding="utf-8"
    )

    version = int(
        migration["version"]
    )

    name = migration["name"]
    checksum = migration["checksum"]

    # Filename regex only permits [a-z0-9_],
    # and checksum is hexadecimal, so both are safe
    # to embed after defensive quote escaping.
    safe_name = name.replace(
        "'",
        "''",
    )

    safe_checksum = checksum.replace(
        "'",
        "''",
    )

    migration_script = f"""
    BEGIN IMMEDIATE;

    {sql}

    INSERT INTO schema_migrations (
        version,
        name,
        checksum
    )
    VALUES (
        {version},
        '{safe_name}',
        '{safe_checksum}'
    );

    COMMIT;
    """

    with database_connection() as connection:
        try:
            connection.executescript(
                migration_script
            )

        except Exception:
            if connection.in_transaction:
                connection.rollback()

            raise
            

def run_migrations() -> list[int]:
    ensure_schema_migrations_table()

    discovered = discover_migrations()

    applied = get_applied_migrations()

    validate_applied_checksums(
        discovered,
        applied,
    )

    newly_applied = []

    for migration in discovered:
        version = migration[
            "version"
        ]

        if version in applied:
            continue

        apply_single_migration(
            migration
        )

        newly_applied.append(
            version
        )

    return newly_applied


def print_migration_status() -> None:
    ensure_schema_migrations_table()

    discovered = discover_migrations()

    applied = get_applied_migrations()

    validate_applied_checksums(
        discovered,
        applied,
    )

    print(
        "weekly_v1 migration system: VALID"
    )

    print(
        "migrations_directory:",
        MIGRATIONS_DIR,
    )

    print(
        "migration_files_found:",
        len(discovered),
    )

    print(
        "migrations_applied:",
        len(applied),
    )

    for migration in discovered:
        version = migration[
            "version"
        ]

        status = (
            "APPLIED"
            if version in applied
            else "PENDING"
        )

        print(
            f"{version:03d}_"
            f"{migration['name']}: "
            f"{status}"
        )


if __name__ == "__main__":
    newly_applied = run_migrations()

    print_migration_status()

    if newly_applied:
        print(
            "newly_applied:",
            [
                f"{version:03d}"
                for version in newly_applied
            ],
        )
    else:
        print(
            "newly_applied: none"
        )