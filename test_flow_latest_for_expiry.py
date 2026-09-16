from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.database as dbmod
import weekly.db.flow_snapshot_repository as repo_module
from weekly.db.flow_snapshot_repository import FlowSnapshotRepository
from weekly.domain.models import FlowSnapshot


UTC = ZoneInfo("UTC")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def configure_connection(
    connection: sqlite3.Connection,
) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")


def make_snapshot(
    *,
    target_expiry: date,
    captured_at: datetime,
    net_flow: float,
) -> FlowSnapshot:
    return FlowSnapshot(
        ticker="AAPL",
        trading_date_et=date(2099, 1, 5),
        captured_at=captured_at,
        target_expiry=target_expiry,

        call_ask_premium=net_flow + 100_000.0,
        put_ask_premium=100_000.0,
        net_flow=net_flow,

        call_bid_premium=50_000.0,
        put_bid_premium=25_000.0,

        bullish_premium=net_flow + 125_000.0,
        bearish_premium=150_000.0,
        directional_net=net_flow - 25_000.0,

        raw_alert_count=10,
        clean_alert_count=10,
        deduped_alert_count=10,

        flow_dedup_level="alert_uuid",
        trade_overlap_detected=False,

        sweep_alert_count=2,
        opening_alert_count=0,

        provider="UNUSUAL_WHALES",
        feed="UNKNOWN",

        source_timestamp=captured_at,
        fetched_at=captured_at,
        freshness_status="PASS",

        total_premium=2_000_000.0,
        sweep_premium=600_000.0,
    )


def main() -> None:
    prod = dbmod.get_database_path().resolve()

    if not prod.exists():
        raise RuntimeError(
            f"Production database not found: {prod}"
        )

    before = sha256_file(prod)

    with tempfile.TemporaryDirectory(
        prefix="flow_latest_expiry_test_"
    ) as td:
        temp_db = Path(td) / "weekly_trading_test.db"

        src = sqlite3.connect(
            f"{prod.as_uri()}?mode=ro",
            uri=True,
        )
        dst = sqlite3.connect(temp_db)

        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        @contextmanager
        def test_database_connection():
            conn = sqlite3.connect(
                temp_db,
                timeout=5,
            )
            configure_connection(conn)

            try:
                yield conn
            finally:
                conn.close()

        @contextmanager
        def test_database_transaction():
            conn = sqlite3.connect(
                temp_db,
                timeout=5,
            )
            configure_connection(conn)

            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        original_connection = (
            repo_module.database_connection
        )
        original_transaction = (
            repo_module.database_transaction
        )

        repo_module.database_connection = (
            test_database_connection
        )
        repo_module.database_transaction = (
            test_database_transaction
        )

        try:
            repository = FlowSnapshotRepository()

            expiry_a = date(2099, 1, 9)
            expiry_b = date(2099, 1, 16)

            repository.create(
                make_snapshot(
                    target_expiry=expiry_a,
                    captured_at=datetime(
                        2099,
                        1,
                        5,
                        15,
                        0,
                        tzinfo=UTC,
                    ),
                    net_flow=700_000.0,
                )
            )

            repository.create(
                make_snapshot(
                    target_expiry=expiry_a,
                    captured_at=datetime(
                        2099,
                        1,
                        5,
                        15,
                        5,
                        tzinfo=UTC,
                    ),
                    net_flow=900_000.0,
                )
            )

            # This snapshot is newer globally, but belongs
            # to a different target expiry.
            repository.create(
                make_snapshot(
                    target_expiry=expiry_b,
                    captured_at=datetime(
                        2099,
                        1,
                        5,
                        15,
                        10,
                        tzinfo=UTC,
                    ),
                    net_flow=2_000_000.0,
                )
            )

            latest_a = repository.get_latest_for_expiry(
                ticker="aapl",
                trading_date_et=date(2099, 1, 5),
                target_expiry=expiry_a,
            )

            latest_b = repository.get_latest_for_expiry(
                ticker="AAPL",
                trading_date_et=date(2099, 1, 5),
                target_expiry=expiry_b,
            )

            missing = repository.get_latest_for_expiry(
                ticker="AAPL",
                trading_date_et=date(2099, 1, 5),
                target_expiry=date(2099, 1, 23),
            )

            assert latest_a is not None
            assert latest_a.target_expiry == expiry_a
            assert latest_a.net_flow == 900_000.0

            assert latest_b is not None
            assert latest_b.target_expiry == expiry_b
            assert latest_b.net_flow == 2_000_000.0

            assert missing is None

        finally:
            repo_module.database_connection = (
                original_connection
            )
            repo_module.database_transaction = (
                original_transaction
            )

    assert before == sha256_file(prod)

    print("1. same ticker/session with multiple expiries: PASS")
    print("2. latest snapshot selected within exact expiry: PASS")
    print("3. newer different-expiry snapshot ignored: PASS")
    print("4. missing expiry returns None: PASS")
    print("5. ticker normalization preserved: PASS")
    print("6. production database unchanged: PASS")

    print()
    print("=" * 70)
    print("FLOW LATEST-FOR-EXPIRY: PASS 6/6")
    print("=" * 70)


if __name__ == "__main__":
    main()
