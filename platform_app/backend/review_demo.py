from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from weekly.db.database import get_database_path


SEED_PATH = (
    Path(__file__).resolve().parent
    / "review_demo_seed.sql"
)


def review_demo_enabled() -> bool:
    value = os.getenv(
        "REVIEW_DEMO_MODE",
        "",
    ).strip().lower()

    return value in {
        "1",
        "true",
        "yes",
        "on",
    }


def initialize_review_demo() -> bool:
    """
    Seed the deployment database with isolated review/demo
    data only when REVIEW_DEMO_MODE is explicitly enabled.

    Returns True when seeding happened in this call.
    Returns False when demo mode is disabled or already seeded.

    Refuses to seed a database that already contains engine
    trading rows without the review-demo marker.
    """

    if not review_demo_enabled():
        return False

    db_path = get_database_path()

    if not SEED_PATH.exists():
        raise RuntimeError(
            f"Review demo seed file not found: {SEED_PATH}"
        )

    seed_sql = SEED_PATH.read_text(
        encoding="utf-8"
    )

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            "PRAGMA foreign_keys=ON;"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_demo_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.commit()

        marker = connection.execute(
            """
            SELECT value
            FROM review_demo_meta
            WHERE key = 'seeded'
            """
        ).fetchone()

        if marker is not None:
            return False

        core_tables = [
            "signals",
            "signal_features",
            "flow_snapshots",
            "positions",
            "trades",
            "outcomes",
            "data_health",
        ]

        existing_rows = 0

        for table in core_tables:
            existing_rows += int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )

        if existing_rows != 0:
            raise RuntimeError(
                "Review demo mode refused to seed a "
                "non-empty engine database."
            )

        script = (
            "BEGIN IMMEDIATE;\n"
            + seed_sql
            + "\n"
            + """
            INSERT INTO review_demo_meta (
                key,
                value
            )
            VALUES (
                'seeded',
                'review_demo_v1'
            );
            """
            + "\nCOMMIT;\n"
        )

        try:
            connection.executescript(script)
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise

    # Seed the review-only universe once, alongside the
    # first review-demo database initialization.
    from platform_app.backend.engine_config_writer import (
        set_universe_tickers,
    )

    set_universe_tickers(
        [
            "AAPL",
            "TSLA",
            "NVDA",
            "GOOGL",
            "META",
            "MSFT",
            "AMZN",
            "AMD",
        ]
    )

    return True

class ReviewDemoOptionsProvider:
    """
    Read simulated option quotes from the isolated
    review-demo tables in the active deployment database.
    """

    def get_contract_candidates(
        self,
        *,
        ticker,
        target_expiry,
    ):
        db_path = get_database_path()

        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                """
                SELECT
                    contract_symbol,
                    bid,
                    ask
                FROM demo_quotes
                WHERE ticker = ?
                  AND expiry = ?
                ORDER BY contract_symbol
                """,
                (
                    str(ticker).upper(),
                    str(target_expiry),
                ),
            ).fetchall()

        candidates = [
            SimpleNamespace(
                symbol=row["contract_symbol"],
                bid=row["bid"],
                ask=row["ask"],
            )
            for row in rows
        ]

        return SimpleNamespace(
            candidates=candidates,
            provider="REVIEW_DEMO_OPTIONS",
            feed="SIMULATED",
        )


def load_review_demo_alerts() -> list[dict]:
    if not review_demo_enabled():
        return []

    db_path = get_database_path()

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT *
            FROM demo_alerts
            ORDER BY alert_id DESC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def mark_review_demo_alert_read(
    alert_id: str,
) -> None:
    if not review_demo_enabled():
        raise RuntimeError(
            "Review demo mode is not enabled."
        )

    db_path = get_database_path()

    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE demo_alerts
            SET status = 'READ'
            WHERE alert_id = ?
            """,
            (alert_id,),
        )

        if cursor.rowcount == 0:
            raise RuntimeError(
                "Review demo alert not found."
            )

        connection.commit()

