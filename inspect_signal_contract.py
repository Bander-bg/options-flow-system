from __future__ import annotations

from dataclasses import fields

from weekly.db.database import (
    database_connection,
)
from weekly.domain.models import (
    Signal,
)


# --------------------------------------------------
# MINIMUM FIELDS NEEDED TO CREATE A CANDIDATE
# --------------------------------------------------

CANDIDATE_CORE_FIELDS = [
    "strategy_version",
    "ticker",
    "trading_date_et",
    "target_expiry",
    "direction",
    "candidate_sequence",
    "state",
    "candidate_at",
]


# --------------------------------------------------
# FIELDS NEEDED FOR THE 30-MINUTE WINDOW
# --------------------------------------------------

CANDIDATE_DEADLINE_FIELDS = [
    "requested_confirmation_deadline_at",
    "confirmation_deadline_at",
]


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 SIGNAL CONTRACT AUDIT"
    )
    print("=" * 78)
    print()

    # --------------------------------------------------
    # DOMAIN MODEL
    # --------------------------------------------------

    model_fields = [
        field.name
        for field in fields(
            Signal
        )
    ]

    print("SIGNAL DOMAIN MODEL FIELDS")
    print("-" * 78)

    for name in model_fields:
        print(name)

    # --------------------------------------------------
    # DATABASE TABLE INFO
    # --------------------------------------------------

    with database_connection() as conn:

        table_rows = conn.execute(
            """
            PRAGMA table_info(
                signals
            )
            """
        ).fetchall()

        db_columns = [
            row["name"]
            for row in table_rows
        ]

        # ----------------------------------------------
        # FOREIGN KEYS
        # ----------------------------------------------

        foreign_keys = conn.execute(
            """
            PRAGMA foreign_key_list(
                signals
            )
            """
        ).fetchall()

        # ----------------------------------------------
        # INDEXES
        # ----------------------------------------------

        indexes = conn.execute(
            """
            PRAGMA index_list(
                signals
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

        # ----------------------------------------------
        # FULL CREATE TABLE SQL
        # ----------------------------------------------

        create_row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'signals'
            """
        ).fetchone()

    print()
    print("SIGNALS DATABASE COLUMNS")
    print("-" * 78)

    for name in db_columns:
        print(name)

    # --------------------------------------------------
    # CORE CANDIDATE CONTRACT
    # --------------------------------------------------

    missing_core_model = [
        name
        for name in CANDIDATE_CORE_FIELDS
        if name not in model_fields
    ]

    missing_core_db = [
        name
        for name in CANDIDATE_CORE_FIELDS
        if name not in db_columns
    ]

    print()
    print("MISSING CORE FIELDS FROM DOMAIN MODEL")
    print("-" * 78)

    if missing_core_model:
        for name in missing_core_model:
            print(name)
    else:
        print("NONE")

    print()
    print("MISSING CORE FIELDS FROM DATABASE")
    print("-" * 78)

    if missing_core_db:
        for name in missing_core_db:
            print(name)
    else:
        print("NONE")

    # --------------------------------------------------
    # DEADLINE CONTRACT
    # --------------------------------------------------

    missing_deadline_model = [
        name
        for name in CANDIDATE_DEADLINE_FIELDS
        if name not in model_fields
    ]

    missing_deadline_db = [
        name
        for name in CANDIDATE_DEADLINE_FIELDS
        if name not in db_columns
    ]

    print()
    print("MISSING DEADLINE FIELDS FROM DOMAIN MODEL")
    print("-" * 78)

    if missing_deadline_model:
        for name in missing_deadline_model:
            print(name)
    else:
        print("NONE")

    print()
    print("MISSING DEADLINE FIELDS FROM DATABASE")
    print("-" * 78)

    if missing_deadline_db:
        for name in missing_deadline_db:
            print(name)
    else:
        print("NONE")

    # --------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------

    print()
    print("SIGNALS FOREIGN KEYS")
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
    # INDEXES / UNIQUE KEYS
    # --------------------------------------------------

    print()
    print("SIGNALS INDEXES")
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
    print("SIGNALS CREATE TABLE SQL")
    print("-" * 78)

    if create_row is None:
        print(
            "signals table not found"
        )

    else:
        print(
            create_row["sql"]
        )

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

    core_ready = (
        not missing_core_model
        and not missing_core_db
    )

    deadline_ready = (
        not missing_deadline_model
        and not missing_deadline_db
    )

    print(
        "Candidate core contract:",
        (
            "READY"
            if core_ready
            else "UPDATE REQUIRED"
        ),
    )

    print(
        "Candidate deadline contract:",
        (
            "READY"
            if deadline_ready
            else "UPDATE REQUIRED"
        ),
    )

    print()

    if (
        core_ready
        and deadline_ready
    ):
        print(
            "Signal contract is ready "
            "for CandidateService review."
        )

    else:
        print(
            "Signal contract requires review "
            "before CandidateService is built."
        )

        print(
            "Do NOT create production "
            "Candidates yet."
        )


if __name__ == "__main__":
    main()