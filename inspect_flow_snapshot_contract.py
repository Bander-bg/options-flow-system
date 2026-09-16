from __future__ import annotations

from dataclasses import fields

from weekly.db.database import (
    database_connection,
)
from weekly.domain.models import (
    FlowSnapshot,
)


REQUIRED_RUNTIME_FIELDS = [
    "ticker",
    "trading_date_et",
    "captured_at",

    "call_ask_premium",
    "put_ask_premium",
    "net_flow",

    "call_bid_premium",
    "put_bid_premium",

    "bullish_premium",
    "bearish_premium",
    "directional_net",

    "raw_alert_count",
    "clean_alert_count",
    "deduped_alert_count",

    "flow_dedup_level",
    "trade_overlap_detected",

    "sweep_alert_count",
    "opening_alert_count",

    "provider",
    "feed",
    "source_timestamp",
    "fetched_at",
    "freshness_status",
]


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 FLOW SNAPSHOT CONTRACT AUDIT"
    )
    print("=" * 78)
    print()

    # --------------------------------------------------
    # DOMAIN MODEL
    # --------------------------------------------------

    model_fields = [
        field.name
        for field in fields(
            FlowSnapshot
        )
    ]

    print("DOMAIN MODEL FIELDS")
    print("-" * 78)

    for name in model_fields:
        print(name)

    # --------------------------------------------------
    # DATABASE TABLE
    # --------------------------------------------------

    with database_connection() as conn:
        rows = conn.execute(
            """
            PRAGMA table_info(
                flow_snapshots
            )
            """
        ).fetchall()

    db_columns = [
        row["name"]
        for row in rows
    ]

    print()
    print("DATABASE COLUMNS")
    print("-" * 78)

    for name in db_columns:
        print(name)

    # --------------------------------------------------
    # REQUIRED RUNTIME CONTRACT
    # --------------------------------------------------

    missing_from_model = [
        name
        for name in REQUIRED_RUNTIME_FIELDS
        if name not in model_fields
    ]

    missing_from_db = [
        name
        for name in REQUIRED_RUNTIME_FIELDS
        if name not in db_columns
    ]

    print()
    print("MISSING FROM DOMAIN MODEL")
    print("-" * 78)

    if missing_from_model:
        for name in missing_from_model:
            print(name)
    else:
        print("NONE")

    print()
    print("MISSING FROM DATABASE")
    print("-" * 78)

    if missing_from_db:
        for name in missing_from_db:
            print(name)
    else:
        print("NONE")

    print()
    print("=" * 78)
    print("FINAL RESULT")
    print("=" * 78)
    print()

    if (
        not missing_from_model
        and not missing_from_db
    ):
        print(
            "FlowSnapshot contract: READY"
        )
    else:
        print(
            "FlowSnapshot contract: MIGRATION/UPDATE REQUIRED"
        )

        print(
            "Do NOT persist production FlowService "
            "results yet."
        )


if __name__ == "__main__":
    main()