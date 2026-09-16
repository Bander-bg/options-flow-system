from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.signal_repository as repo_module

from weekly.db.database import get_database_path
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import (
    Direction,
    SignalState,
)
from weekly.domain.models import Signal


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_signal_repository_test.db"
)


def create_temp_database() -> None:
    if TEMP_DB.exists():
        TEMP_DB.unlink()

    source_path = get_database_path()

    source = sqlite3.connect(
        source_path
    )

    destination = sqlite3.connect(
        TEMP_DB
    )

    try:
        source.backup(
            destination
        )

    finally:
        destination.close()
        source.close()


def connect_temp() -> sqlite3.Connection:
    connection = sqlite3.connect(
        TEMP_DB,
        timeout=5,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode=WAL;"
    )

    connection.execute(
        "PRAGMA busy_timeout=5000;"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return connection


@contextmanager
def temp_database_connection():
    connection = connect_temp()

    try:
        yield connection

    finally:
        connection.close()


@contextmanager
def temp_database_transaction():
    connection = connect_temp()

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


def patch_repository_database() -> None:
    repo_module.database_connection = (
        temp_database_connection
    )

    repo_module.database_transaction = (
        temp_database_transaction
    )


def make_signal(
    sequence: int,
) -> Signal:
    return Signal(
        strategy_version="weekly_v1",
        config_hash="repository_test_hash",

        ticker="AAPL",

        trading_date_et=date(
            2026,
            9,
            4,
        ),

        target_expiry=date(
            2026,
            9,
            11,
        ),

        direction=Direction.BULLISH,

        candidate_sequence=sequence,

        state=SignalState.CANDIDATE,

        candidate_at=datetime(
            2026,
            9,
            4,
            10,
            sequence,
            tzinfo=ET,
        ),

        requested_confirmation_deadline_at=datetime(
            2026,
            9,
            4,
            10,
            30,
            tzinfo=ET,
        ),

        confirmation_deadline_at=datetime(
            2026,
            9,
            4,
            10,
            30,
            tzinfo=ET,
        ),

        net_flow_at_candidate=600_000,

        flow_dedup_level="alert_composite",

        stock_data_provider="ALPACA",
        stock_data_feed="IEX",

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",

        theta_convention_status="UNRESOLVED",

        scenario_return_enabled=False,
    )


def assert_equal(
    actual,
    expected,
    name: str,
):
    if actual != expected:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 SIGNAL REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repository_database()

        repository = SignalRepository()

        # --------------------------------------------------
        # TEST 1 - initial sequence
        # --------------------------------------------------

        next_sequence = (
            repository.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=date(
                    2026,
                    9,
                    4,
                ),
                target_expiry=date(
                    2026,
                    9,
                    11,
                ),
                direction=Direction.BULLISH,
            )
        )

        assert_equal(
            next_sequence,
            1,
            "initial candidate sequence",
        )

        print(
            "PASS - initial candidate_sequence = 1"
        )

        # --------------------------------------------------
        # TEST 2 - create
        # --------------------------------------------------

        signal_1 = repository.create(
            make_signal(1)
        )

        if signal_1.id is None:
            raise AssertionError(
                "Inserted signal has no id."
            )

        assert_equal(
            signal_1.signal_sign,
            1,
            "signal sign",
        )

        print(
            "PASS - create signal"
        )

        # --------------------------------------------------
        # TEST 3 - read by ID
        # --------------------------------------------------

        loaded = repository.get_by_id(
            signal_1.id
        )

        if loaded is None:
            raise AssertionError(
                "Signal could not be read by id."
            )

        assert_equal(
            loaded.ticker,
            "AAPL",
            "ticker",
        )

        assert_equal(
            loaded.direction,
            Direction.BULLISH,
            "direction",
        )

        assert_equal(
            loaded.state,
            SignalState.CANDIDATE,
            "state",
        )

        assert_equal(
            loaded.flow_dedup_level,
            "alert_composite",
            "flow_dedup_level",
        )

        assert_equal(
            loaded.stock_data_feed,
            "IEX",
            "stock_data_feed",
        )

        assert_equal(
            loaded.options_data_feed,
            "INDICATIVE",
            "options_data_feed",
        )

        assert_equal(
            loaded.scenario_return_enabled,
            False,
            "scenario_return_enabled",
        )

        print(
            "PASS - get_by_id + round-trip mapping"
        )

        # --------------------------------------------------
        # TEST 4 - sequence increments
        # --------------------------------------------------

        next_sequence = (
            repository.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=date(
                    2026,
                    9,
                    4,
                ),
                target_expiry=date(
                    2026,
                    9,
                    11,
                ),
                direction=Direction.BULLISH,
            )
        )

        assert_equal(
            next_sequence,
            2,
            "second candidate sequence",
        )

        print(
            "PASS - candidate_sequence increments"
        )

        # --------------------------------------------------
        # TEST 5 - second signal + latest
        # --------------------------------------------------

        signal_2 = repository.create(
            make_signal(2)
        )

        latest = repository.get_latest(
            strategy_version="weekly_v1",
            ticker="AAPL",
            trading_date_et=date(
                2026,
                9,
                4,
            ),
            target_expiry=date(
                2026,
                9,
                11,
            ),
            direction=Direction.BULLISH,
        )

        if latest is None:
            raise AssertionError(
                "Latest signal not found."
            )

        assert_equal(
            latest.id,
            signal_2.id,
            "latest signal id",
        )

        assert_equal(
            latest.candidate_sequence,
            2,
            "latest sequence",
        )

        print(
            "PASS - get_latest returns newest sequence"
        )

        # --------------------------------------------------
        # TEST 6 - database UNIQUE protection
        # --------------------------------------------------

        duplicate_blocked = False

        try:
            repository.create(
                make_signal(2)
            )

        except sqlite3.IntegrityError:
            duplicate_blocked = True

        if not duplicate_blocked:
            raise AssertionError(
                "Duplicate logical signal "
                "was not blocked."
            )

        print(
            "PASS - duplicate logical signal blocked"
        )

        # --------------------------------------------------
        # TEST 7 - opposite direction has independent scope
        # --------------------------------------------------

        bearish_next = (
            repository.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=date(
                    2026,
                    9,
                    4,
                ),
                target_expiry=date(
                    2026,
                    9,
                    11,
                ),
                direction=Direction.BEARISH,
            )
        )

        assert_equal(
            bearish_next,
            1,
            "bearish independent sequence",
        )

        print(
            "PASS - bullish/bearish sequence scopes independent"
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "SignalRepository: PASS"
        )

        print(
            "create/read mapping: PASS"
        )

        print(
            "candidate_sequence behavior: PASS"
        )

        print(
            "logical duplicate protection: PASS"
        )

        print(
            "Production weekly_trading.db modified: NO"
        )

    finally:
        for path in [
            TEMP_DB,
            Path(
                str(TEMP_DB) + "-wal"
            ),
            Path(
                str(TEMP_DB) + "-shm"
            ),
        ]:
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()