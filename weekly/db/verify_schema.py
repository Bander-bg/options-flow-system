from __future__ import annotations

from weekly.db.database import database_connection


EXPECTED_TABLES = {
    "schema_migrations",
    "signals",
    "signal_features",
    "flow_snapshots",
    "outcomes",
    "positions",
    "trades",
    "data_health",
}


def get_tables(connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
        """
    ).fetchall()

    return {
        row["name"]
        for row in rows
    }


def get_unique_indexes(
    connection,
    table_name: str,
) -> list[list[str]]:
    result = []

    index_rows = connection.execute(
        f"PRAGMA index_list('{table_name}');"
    ).fetchall()

    for index_row in index_rows:
        # PRAGMA index_list columns:
        # seq, name, unique, origin, partial
        if not index_row["unique"]:
            continue

        index_name = index_row["name"]

        column_rows = connection.execute(
            f"PRAGMA index_info('{index_name}');"
        ).fetchall()

        columns = [
            row["name"]
            for row in column_rows
        ]

        result.append(columns)

    return result


def get_foreign_keys(
    connection,
    table_name: str,
) -> list[dict]:
    rows = connection.execute(
        f"PRAGMA foreign_key_list('{table_name}');"
    ).fetchall()

    return [
        {
            "from": row["from"],
            "table": row["table"],
            "to": row["to"],
            "on_delete": row["on_delete"],
        }
        for row in rows
    ]


def assert_unique_key(
    connection,
    table_name: str,
    expected_columns: list[str],
):
    indexes = get_unique_indexes(
        connection,
        table_name,
    )

    if expected_columns not in indexes:
        raise AssertionError(
            f"{table_name}: missing UNIQUE key "
            f"{expected_columns}. "
            f"Found: {indexes}"
        )


def assert_foreign_key(
    connection,
    *,
    table_name: str,
    from_column: str,
    referenced_table: str,
    referenced_column: str,
):
    foreign_keys = get_foreign_keys(
        connection,
        table_name,
    )

    match = any(
        fk["from"] == from_column
        and fk["table"] == referenced_table
        and fk["to"] == referenced_column
        for fk in foreign_keys
    )

    if not match:
        raise AssertionError(
            f"{table_name}: missing FK "
            f"{from_column} -> "
            f"{referenced_table}"
            f"({referenced_column})"
        )


def main():
    print("=" * 78)
    print("WEEKLY_V1 DATABASE SCHEMA VERIFICATION")
    print("=" * 78)
    print()

    with database_connection() as connection:

        tables = get_tables(
            connection
        )

        print(
            "tables_found:",
            sorted(tables),
        )

        missing_tables = (
            EXPECTED_TABLES - tables
        )

        unexpected_tables = (
            tables - EXPECTED_TABLES
        )

        if missing_tables:
            raise AssertionError(
                "Missing tables: "
                f"{sorted(missing_tables)}"
            )

        if unexpected_tables:
            print(
                "NOTE - additional tables:",
                sorted(unexpected_tables),
            )

        print(
            "PASS - required tables"
        )

        # --------------------------------------------------
        # Required logical UNIQUE keys
        # --------------------------------------------------

        assert_unique_key(
            connection,
            "signals",
            [
                "strategy_version",
                "ticker",
                "trading_date_et",
                "target_expiry",
                "direction",
                "candidate_sequence",
            ],
        )

        print(
            "PASS - signals logical UNIQUE key"
        )

        assert_unique_key(
            connection,
            "flow_snapshots",
            [
                "ticker",
                "trading_date_et",
                "captured_at",
            ],
        )

        print(
            "PASS - flow_snapshots UNIQUE key"
        )

        assert_unique_key(
            connection,
            "outcomes",
            [
                "signal_id",
                "outcome_scope",
                "checkpoint_name",
            ],
        )

        print(
            "PASS - outcomes UNIQUE key"
        )

        assert_unique_key(
            connection,
            "signal_features",
            [
                "signal_id",
                "evaluation_sequence",
            ],
        )

        print(
            "PASS - signal_features UNIQUE key"
        )

        # --------------------------------------------------
        # Foreign keys
        # --------------------------------------------------

        assert_foreign_key(
            connection,
            table_name="signal_features",
            from_column="signal_id",
            referenced_table="signals",
            referenced_column="id",
        )

        assert_foreign_key(
            connection,
            table_name="outcomes",
            from_column="signal_id",
            referenced_table="signals",
            referenced_column="id",
        )

        assert_foreign_key(
            connection,
            table_name="positions",
            from_column="signal_id",
            referenced_table="signals",
            referenced_column="id",
        )

        assert_foreign_key(
            connection,
            table_name="trades",
            from_column="position_id",
            referenced_table="positions",
            referenced_column="id",
        )

        assert_foreign_key(
            connection,
            table_name="trades",
            from_column="signal_id",
            referenced_table="signals",
            referenced_column="id",
        )

        print(
            "PASS - required foreign keys"
        )

        # --------------------------------------------------
        # Migration record
        # --------------------------------------------------

        migration = connection.execute(
            """
            SELECT
                version,
                name,
                checksum,
                applied_at
            FROM schema_migrations
            WHERE version = 1;
            """
        ).fetchone()

        if migration is None:
            raise AssertionError(
                "Migration 001 is not recorded."
            )

        if migration["name"] != "initial_schema":
            raise AssertionError(
                "Migration 001 name mismatch."
            )

        if not migration["checksum"]:
            raise AssertionError(
                "Migration 001 checksum missing."
            )

        print(
            "PASS - migration 001 record"
        )

        # --------------------------------------------------
        # Runtime PRAGMAs
        # --------------------------------------------------

        journal_mode = connection.execute(
            "PRAGMA journal_mode;"
        ).fetchone()[0]

        busy_timeout = connection.execute(
            "PRAGMA busy_timeout;"
        ).fetchone()[0]

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()[0]

        if str(journal_mode).lower() != "wal":
            raise AssertionError(
                "journal_mode is not WAL"
            )

        if int(busy_timeout) != 5000:
            raise AssertionError(
                "busy_timeout is not 5000"
            )

        if int(foreign_keys) != 1:
            raise AssertionError(
                "foreign_keys is not ON"
            )

        print(
            "PASS - SQLite runtime PRAGMAs"
        )

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()
    print(
        "weekly_v1 initial database schema: PASS"
    )


if __name__ == "__main__":
    main()