from __future__ import annotations

from dataclasses import fields

from weekly.db.database import (
    database_connection,
)
from weekly.domain.models import (
    SignalFeature,
)


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 SIGNAL FEATURE CONTRACT AUDIT"
    )
    print("=" * 78)
    print()

    # --------------------------------------------------
    # DOMAIN MODEL
    # --------------------------------------------------

    model_fields = [
        field.name
        for field in fields(
            SignalFeature
        )
    ]

    print("SIGNALFEATURE DOMAIN MODEL FIELDS")
    print("-" * 78)

    for name in model_fields:
        print(name)

    # --------------------------------------------------
    # DATABASE
    # --------------------------------------------------

    with database_connection() as conn:

        table_rows = conn.execute(
            """
            PRAGMA table_info(
                signal_features
            )
            """
        ).fetchall()

        db_columns = [
            row["name"]
            for row in table_rows
        ]

        foreign_keys = conn.execute(
            """
            PRAGMA foreign_key_list(
                signal_features
            )
            """
        ).fetchall()

        indexes = conn.execute(
            """
            PRAGMA index_list(
                signal_features
            )
            """
        ).fetchall()

        index_details = []

        for index in indexes:

            index_name = (
                index["name"]
            )

            columns = conn.execute(
                f"""
                PRAGMA index_info(
                    "{index_name}"
                )
                """
            ).fetchall()

            index_details.append(
                {
                    "name": index_name,
                    "unique": bool(
                        index["unique"]
                    ),
                    "columns": [
                        column["name"]
                        for column in columns
                    ],
                }
            )

        create_row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'signal_features'
            """
        ).fetchone()

    # --------------------------------------------------
    # DATABASE COLUMNS
    # --------------------------------------------------

    print()
    print("SIGNAL_FEATURES DATABASE COLUMNS")
    print("-" * 78)

    for name in db_columns:
        print(name)

    # --------------------------------------------------
    # MODEL VS DATABASE
    # --------------------------------------------------

    model_not_db = [
        name
        for name in model_fields
        if (
            name != "id"
            and name not in db_columns
        )
    ]

    db_not_model = [
        name
        for name in db_columns
        if (
            name
            not in model_fields
            and name
            not in (
                "created_at",
                "updated_at",
            )
        )
    ]

    print()
    print("MODEL FIELDS MISSING FROM DATABASE")
    print("-" * 78)

    if model_not_db:
        for name in model_not_db:
            print(name)
    else:
        print("NONE")

    print()
    print("DATABASE FIELDS MISSING FROM MODEL")
    print("-" * 78)

    if db_not_model:
        for name in db_not_model:
            print(name)
    else:
        print("NONE")

    # --------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------

    print()
    print("SIGNAL_FEATURES FOREIGN KEYS")
    print("-" * 78)

    if not foreign_keys:
        print("NONE")

    else:
        for foreign_key in foreign_keys:
            print(
                "from:",
                foreign_key["from"],
                "->",
                foreign_key["table"],
                ".",
                foreign_key["to"],
            )

    # --------------------------------------------------
    # INDEXES
    # --------------------------------------------------

    print()
    print("SIGNAL_FEATURES INDEXES")
    print("-" * 78)

    if not index_details:
        print("NONE")

    else:
        for item in index_details:

            print(
                "name:",
                item["name"],
            )

            print(
                "unique:",
                item["unique"],
            )

            print(
                "columns:",
                item["columns"],
            )

            print()

    # --------------------------------------------------
    # FULL TABLE SQL
    # --------------------------------------------------

    print()
    print("SIGNAL_FEATURES CREATE TABLE SQL")
    print("-" * 78)

    if create_row is None:
        print(
            "signal_features table not found"
        )

    else:
        print(
            create_row["sql"]
        )

    # --------------------------------------------------
    # PRICE ACTION FIELD DISCOVERY
    # --------------------------------------------------

    keywords = (
        "structure",
        "impulse",
        "participation",
        "price_action",
        "rvol",
        "atr",
        "bar",
        "trigger",
    )

    pa_model_fields = [
        name
        for name in model_fields
        if any(
            keyword in name.lower()
            for keyword in keywords
        )
    ]

    pa_db_fields = [
        name
        for name in db_columns
        if any(
            keyword in name.lower()
            for keyword in keywords
        )
    ]

    print()
    print("POTENTIAL PRICE-ACTION MODEL FIELDS")
    print("-" * 78)

    if pa_model_fields:
        for name in pa_model_fields:
            print(name)
    else:
        print("NONE")

    print()
    print("POTENTIAL PRICE-ACTION DATABASE FIELDS")
    print("-" * 78)

    if pa_db_fields:
        for name in pa_db_fields:
            print(name)
    else:
        print("NONE")

    # --------------------------------------------------
    # FINAL
    # --------------------------------------------------

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

    if (
        not model_not_db
        and not db_not_model
    ):
        print(
            "Current SignalFeature model/schema: ALIGNED"
        )
    else:
        print(
            "Current SignalFeature model/schema: REVIEW REQUIRED"
        )

    print()
    print(
        "Next decision: determine whether existing "
        "fields are sufficient for weekly_v1 "
        "15m Price Action confirmation."
    )


if __name__ == "__main__":
    main()