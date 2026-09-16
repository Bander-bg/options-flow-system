from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

import weekly.db.flow_snapshot_repository as repo_module

from weekly.db.flow_snapshot_repository import (
    FlowSnapshotRepository,
)
from weekly.domain.models import (
    FlowSnapshot,
)
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesProvider,
)
from weekly.services.flow_service import (
    calculate_flow,
    get_base_flow_direction,
)


load_dotenv()


ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    ROOT
    / "weekly_trading.db"
)

TEST_DB = (
    ROOT
    / "weekly_flow_pipeline_integration_test.db"
)


ET = ZoneInfo(
    "America/New_York"
)


TICKER = "AAPL"

TRADING_DATE = date(
    2026,
    9,
    4,
)

TARGET_EXPIRY = date(
    2026,
    9,
    11,
)

SESSION_OPEN_ET = datetime(
    2026,
    9,
    4,
    9,
    30,
    tzinfo=ET,
)

SESSION_CLOSE_ET = datetime(
    2026,
    9,
    4,
    16,
    0,
    tzinfo=ET,
)

FLOW_THRESHOLD = 500_000


def file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def clone_database():
    if TEST_DB.exists():
        TEST_DB.unlink()

    source = sqlite3.connect(
        PRODUCTION_DB
    )

    target = sqlite3.connect(
        TEST_DB
    )

    source.backup(
        target
    )

    source.close()
    target.close()


def configure_connection(
    connection: sqlite3.Connection,
):
    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA busy_timeout = 5000"
    )


@contextmanager
def test_database_connection():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def test_database_transaction():
    connection = sqlite3.connect(
        TEST_DB,
        timeout=5,
    )

    configure_connection(
        connection
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def patch_repository_database():
    repo_module.database_connection = (
        test_database_connection
    )

    repo_module.database_transaction = (
        test_database_transaction
    )


def clear_test_flow_snapshots():
    connection = sqlite3.connect(
        TEST_DB
    )

    connection.execute(
        "DELETE FROM flow_snapshots"
    )

    connection.commit()
    connection.close()


def cleanup():
    for suffix in (
        "",
        "-wal",
        "-shm",
    ):
        path = Path(
            str(TEST_DB) + suffix
        )

        if path.exists():
            path.unlink()


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 REAL FLOW PIPELINE INTEGRATION TEST"
    )
    print("=" * 78)
    print()

    production_hash_before = (
        file_sha256(
            PRODUCTION_DB
        )
    )

    try:
        # --------------------------------------------------
        # TEMP DATABASE
        # --------------------------------------------------

        clone_database()

        clear_test_flow_snapshots()

        patch_repository_database()

        repository = (
            FlowSnapshotRepository()
        )

        print(
            "PASS - Temporary SQLite environment ready"
        )

        # --------------------------------------------------
        # 1. REAL UW PROVIDER
        # --------------------------------------------------

        provider = (
            UnusualWhalesProvider()
        )

        batch = (
            provider
            .fetch_session_to_date_flow_alerts(
                ticker=TICKER,
                session_open_et=SESSION_OPEN_ET,
                max_pages=20,
                page_limit=500,
                require_complete=True,
            )
        )

        if not (
            batch.session_coverage_complete
        ):
            raise AssertionError(
                "UW session coverage "
                "is incomplete."
            )

        if (
            batch.source_timestamp
            is None
        ):
            raise AssertionError(
                "Provider source_timestamp "
                "is missing."
            )

        if (
            batch.fetched_at
            is None
        ):
            raise AssertionError(
                "Provider fetched_at "
                "is missing."
            )

        print(
            "PASS - Real UW Provider"
        )

        print(
            "      rows_fetched:",
            batch.rows_fetched,
        )

        print(
            "      session_coverage_complete:",
            batch.session_coverage_complete,
        )

        # --------------------------------------------------
        # 2. PRODUCTION FLOW SERVICE
        # --------------------------------------------------

        calculation = (
            calculate_flow(
                ticker=TICKER,
                alerts=batch.alerts,
                trading_date_et=TRADING_DATE,
                target_expiry=TARGET_EXPIRY,
                session_open_et=SESSION_OPEN_ET,
                session_close_et=SESSION_CLOSE_ET,
            )
        )

        expected_net = (
            calculation.call_ask_premium
            - calculation.put_ask_premium
        )

        if (
            abs(
                calculation.net_flow
                - expected_net
            )
            > 1e-9
        ):
            raise AssertionError(
                "FlowService Net Flow "
                "math mismatch."
            )

        print(
            "PASS - Production FlowService"
        )

        print(
            "      clean_alert_count:",
            calculation.clean_alert_count,
        )

        print(
            "      deduped_alert_count:",
            calculation.deduped_alert_count,
        )

        print(
            "      flow_dedup_level:",
            calculation.flow_dedup_level,
        )

        print(
            "      net_flow:",
            calculation.net_flow,
        )

        # --------------------------------------------------
        # BASE DIRECTION
        # --------------------------------------------------

        base_direction = (
            get_base_flow_direction(
                net_flow=(
                    calculation.net_flow
                ),
                threshold=FLOW_THRESHOLD,
            )
        )

        print(
            "      base_direction:",
            (
                base_direction.value
                if base_direction
                else None
            ),
        )

        # --------------------------------------------------
        # 3. MAP TO DOMAIN MODEL
        # --------------------------------------------------

        captured_at = (
            batch.source_timestamp
            .astimezone(
                ET
            )
        )

        snapshot = FlowSnapshot(
            ticker=TICKER,

            trading_date_et=(
                TRADING_DATE
            ),

            captured_at=(
                captured_at
            ),

            target_expiry=(
                TARGET_EXPIRY
            ),

            call_ask_premium=(
                calculation
                .call_ask_premium
            ),

            put_ask_premium=(
                calculation
                .put_ask_premium
            ),

            net_flow=(
                calculation
                .net_flow
            ),

            call_bid_premium=(
                calculation
                .call_bid_premium
            ),

            put_bid_premium=(
                calculation
                .put_bid_premium
            ),

            bullish_premium=(
                calculation
                .bullish_premium
            ),

            bearish_premium=(
                calculation
                .bearish_premium
            ),

            directional_net=(
                calculation
                .directional_net
            ),

            raw_alert_count=(
                calculation
                .raw_alert_count
            ),

            clean_alert_count=(
                calculation
                .clean_alert_count
            ),

            deduped_alert_count=(
                calculation
                .deduped_alert_count
            ),

            flow_dedup_level=(
                calculation
                .flow_dedup_level
            ),

            trade_overlap_detected=(
                calculation
                .trade_overlap_detected
            ),

            sweep_alert_count=(
                calculation
                .sweep_alert_count
            ),

            opening_alert_count=(
                calculation
                .opening_alert_count
            ),

            provider=(
                batch.provider
            ),

            feed=(
                batch.feed
            ),

            source_timestamp=(
                batch.source_timestamp
            ),

            fetched_at=(
                batch.fetched_at
            ),

            freshness_status=(
                batch.freshness_status
            ),
        )

        print(
            "PASS - FlowSnapshot domain mapping"
        )

        # --------------------------------------------------
        # 4. PERSIST TO TEMP SQLITE
        # --------------------------------------------------

        created = repository.create(
            snapshot
        )

        if created.id is None:
            raise AssertionError(
                "Persisted snapshot "
                "has no id."
            )

        loaded = repository.get_by_id(
            created.id
        )

        if loaded is None:
            raise AssertionError(
                "Persisted snapshot "
                "could not be read back."
            )

        print(
            "PASS - FlowSnapshotRepository persistence"
        )

        # --------------------------------------------------
        # 5. END-TO-END FIELD VALIDATION
        # --------------------------------------------------

        comparisons = {
            "ticker": (
                loaded.ticker,
                TICKER,
            ),

            "target_expiry": (
                loaded.target_expiry,
                TARGET_EXPIRY,
            ),

            "call_ask_premium": (
                loaded.call_ask_premium,
                calculation.call_ask_premium,
            ),

            "put_ask_premium": (
                loaded.put_ask_premium,
                calculation.put_ask_premium,
            ),

            "net_flow": (
                loaded.net_flow,
                calculation.net_flow,
            ),

            "directional_net": (
                loaded.directional_net,
                calculation.directional_net,
            ),

            "raw_alert_count": (
                loaded.raw_alert_count,
                calculation.raw_alert_count,
            ),

            "clean_alert_count": (
                loaded.clean_alert_count,
                calculation.clean_alert_count,
            ),

            "deduped_alert_count": (
                loaded.deduped_alert_count,
                calculation.deduped_alert_count,
            ),

            "flow_dedup_level": (
                loaded.flow_dedup_level,
                calculation.flow_dedup_level,
            ),

            "provider": (
                loaded.provider,
                batch.provider,
            ),

            "feed": (
                loaded.feed,
                batch.feed,
            ),

            "source_timestamp": (
                loaded.source_timestamp,
                batch.source_timestamp,
            ),

            "fetched_at": (
                loaded.fetched_at,
                batch.fetched_at,
            ),

            "freshness_status": (
                loaded.freshness_status,
                batch.freshness_status,
            ),
        }

        for (
            field_name,
            (
                actual,
                expected,
            ),
        ) in comparisons.items():

            if actual != expected:
                raise AssertionError(
                    f"{field_name}: "
                    f"expected {expected!r}, "
                    f"got {actual!r}"
                )

        print(
            "PASS - End-to-end field integrity"
        )

        # --------------------------------------------------
        # 6. LEGACY COMPATIBILITY
        # --------------------------------------------------

        connection = sqlite3.connect(
            TEST_DB
        )

        connection.row_factory = (
            sqlite3.Row
        )

        legacy_row = (
            connection.execute(
                """
                SELECT
                    alert_count,
                    source_provider
                FROM flow_snapshots
                WHERE id = ?
                """,
                (
                    created.id,
                ),
            ).fetchone()
        )

        connection.close()

        if legacy_row is None:
            raise AssertionError(
                "Legacy validation row missing."
            )

        if (
            legacy_row["alert_count"]
            != calculation
            .deduped_alert_count
        ):
            raise AssertionError(
                "Legacy alert_count mismatch."
            )

        if (
            legacy_row["source_provider"]
            != batch.provider
        ):
            raise AssertionError(
                "Legacy source_provider mismatch."
            )

        print(
            "PASS - Legacy DB compatibility"
        )

        # --------------------------------------------------
        # PRODUCTION DB PROTECTION
        # --------------------------------------------------

        production_hash_after = (
            file_sha256(
                PRODUCTION_DB
            )
        )

        if (
            production_hash_before
            != production_hash_after
        ):
            raise AssertionError(
                "Production weekly_trading.db "
                "was modified."
            )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "Real UW -> FlowService -> "
            "FlowSnapshot -> SQLite: PASS"
        )

        print(
            "Session-to-Date completeness: PASS"
        )

        print(
            "Flow math integrity: PASS"
        )

        print(
            "Dedup provenance: PASS"
        )

        print(
            "Provider metadata integrity: PASS"
        )

        print(
            "Persistence round-trip: PASS"
        )

        print(
            "Production weekly_trading.db "
            "modified: NO"
        )

        print()

        print(
            "FLOW INGESTION FOUNDATION: READY"
        )

        print(
            "Candidate creation was NOT executed."
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()