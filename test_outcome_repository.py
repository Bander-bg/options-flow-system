from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.outcome_repository as outcome_repo_module
import weekly.db.signal_repository as signal_repo_module

from weekly.db.database import get_database_path
from weekly.db.outcome_repository import OutcomeRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import (
    Direction,
    OutcomeScope,
    OutcomeStatus,
    SignalState,
)
from weekly.domain.models import (
    Outcome,
    Signal,
)


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_outcome_repository_test.db"
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


def patch_repositories() -> None:
    signal_repo_module.database_connection = (
        temp_database_connection
    )

    signal_repo_module.database_transaction = (
        temp_database_transaction
    )

    outcome_repo_module.database_connection = (
        temp_database_connection
    )

    outcome_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_signal() -> Signal:
    return Signal(
        strategy_version="weekly_v1",
        config_hash="outcome_repo_test_hash",

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

        candidate_sequence=1,

        state=SignalState.CONFIRMED,

        candidate_at=datetime(
            2026,
            9,
            4,
            10,
            0,
            tzinfo=ET,
        ),

        confirmed_at=datetime(
            2026,
            9,
            4,
            10,
            15,
            tzinfo=ET,
        ),

        net_flow_at_candidate=600_000,

        net_flow_at_confirmation=750_000,

        flow_dedup_level="alert_composite",

        stock_data_provider="ALPACA",
        stock_data_feed="IEX",

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",

        theta_convention_status="UNRESOLVED",

        scenario_return_enabled=False,
    )


def make_outcome(
    *,
    signal_id: int,
    scope: OutcomeScope,
    checkpoint: str,
    minute: int,
) -> Outcome:

    return Outcome(
        signal_id=signal_id,

        outcome_scope=scope,

        checkpoint_name=checkpoint,

        outcome_status=OutcomeStatus.OBSERVED,

        scheduled_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=ET,
        ),

        observed_at=datetime(
            2026,
            9,
            4,
            10,
            minute,
            tzinfo=ET,
        ),

        baseline_at=datetime(
            2026,
            9,
            4,
            10,
            0,
            tzinfo=ET,
        ),

        baseline_underlying_price=320.00,
        observed_underlying_price=323.20,

        underlying_raw_return=0.01,
        underlying_directional_return=0.01,

        contract_symbol="AAPL260911C00320000",

        baseline_option_bid=4.80,
        baseline_option_ask=5.00,
        baseline_option_mark=4.90,

        observed_option_bid=5.50,
        observed_option_ask=5.70,
        observed_option_mark=5.60,

        option_executable_return=0.10,
        option_mark_return=(
            (5.60 - 4.90) / 4.90
        ),

        settlement_value=None,

        stock_data_provider="ALPACA",
        stock_data_feed="IEX",

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",
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


def assert_close(
    actual,
    expected,
    name: str,
    tolerance: float = 1e-12,
):
    if actual is None:
        raise AssertionError(
            f"{name}: got None"
        )

    if abs(actual - expected) > tolerance:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 OUTCOME REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repositories()

        signal_repository = SignalRepository()
        outcome_repository = OutcomeRepository()

        # --------------------------------------------------
        # TEST 1 - create parent signal
        # --------------------------------------------------

        signal = signal_repository.create(
            make_signal()
        )

        if signal.id is None:
            raise AssertionError(
                "Parent signal id missing."
            )

        print(
            "PASS - parent signal created"
        )

        # --------------------------------------------------
        # TEST 2 - create candidate +15 outcome
        # --------------------------------------------------

        candidate_15 = (
            outcome_repository.create(
                make_outcome(
                    signal_id=signal.id,
                    scope=OutcomeScope.CANDIDATE,
                    checkpoint="+15m",
                    minute=15,
                )
            )
        )

        if candidate_15.id is None:
            raise AssertionError(
                "Outcome id missing."
            )

        print(
            "PASS - create candidate outcome"
        )

        # --------------------------------------------------
        # TEST 3 - round-trip Ask/Bid returns
        # --------------------------------------------------

        loaded = outcome_repository.get_by_id(
            candidate_15.id
        )

        if loaded is None:
            raise AssertionError(
                "Outcome could not be read."
            )

        assert_equal(
            loaded.outcome_scope,
            OutcomeScope.CANDIDATE,
            "outcome scope",
        )

        assert_equal(
            loaded.outcome_status,
            OutcomeStatus.OBSERVED,
            "outcome status",
        )

        assert_close(
            loaded.baseline_option_ask,
            5.00,
            "baseline ask",
        )

        assert_close(
            loaded.observed_option_bid,
            5.50,
            "observed bid",
        )

        assert_close(
            loaded.option_executable_return,
            0.10,
            "executable return",
        )

        assert_close(
            loaded.underlying_directional_return,
            0.01,
            "directional return",
        )

        assert_equal(
            loaded.options_data_feed,
            "INDICATIVE",
            "options feed",
        )

        print(
            "PASS - Ask/Bid + return round-trip"
        )

        # --------------------------------------------------
        # TEST 4 - get_by_key
        # --------------------------------------------------

        by_key = outcome_repository.get_by_key(
            signal_id=signal.id,
            outcome_scope=OutcomeScope.CANDIDATE,
            checkpoint_name="+15m",
        )

        if by_key is None:
            raise AssertionError(
                "Outcome not found by logical key."
            )

        assert_equal(
            by_key.id,
            candidate_15.id,
            "logical-key outcome id",
        )

        print(
            "PASS - get_by_key"
        )

        # --------------------------------------------------
        # TEST 5 - duplicate logical outcome blocked
        # --------------------------------------------------

        duplicate_blocked = False

        try:
            outcome_repository.create(
                make_outcome(
                    signal_id=signal.id,
                    scope=OutcomeScope.CANDIDATE,
                    checkpoint="+15m",
                    minute=15,
                )
            )

        except sqlite3.IntegrityError:
            duplicate_blocked = True

        if not duplicate_blocked:
            raise AssertionError(
                "Duplicate outcome key "
                "was not blocked."
            )

        print(
            "PASS - duplicate logical outcome blocked"
        )

        # --------------------------------------------------
        # TEST 6 - resolution scope is independent
        # --------------------------------------------------

        resolution_15 = (
            outcome_repository.create(
                make_outcome(
                    signal_id=signal.id,
                    scope=OutcomeScope.RESOLUTION,
                    checkpoint="+15m",
                    minute=30,
                )
            )
        )

        if resolution_15.id is None:
            raise AssertionError(
                "Resolution outcome id missing."
            )

        print(
            "PASS - Candidate/Resolution scopes independent"
        )

        # --------------------------------------------------
        # TEST 7 - additional checkpoint is independent
        # --------------------------------------------------

        candidate_30 = (
            outcome_repository.create(
                make_outcome(
                    signal_id=signal.id,
                    scope=OutcomeScope.CANDIDATE,
                    checkpoint="+30m",
                    minute=30,
                )
            )
        )

        if candidate_30.id is None:
            raise AssertionError(
                "+30m outcome id missing."
            )

        print(
            "PASS - checkpoint names independent"
        )

        # --------------------------------------------------
        # TEST 8 - list all outcomes for signal
        # --------------------------------------------------

        outcomes = (
            outcome_repository.list_for_signal(
                signal.id
            )
        )

        assert_equal(
            len(outcomes),
            3,
            "outcome count",
        )

        print(
            "PASS - list_for_signal"
        )

        # --------------------------------------------------
        # TEST 9 - FK protection
        # --------------------------------------------------

        fk_blocked = False

        try:
            outcome_repository.create(
                make_outcome(
                    signal_id=999999,
                    scope=OutcomeScope.CANDIDATE,
                    checkpoint="+60m",
                    minute=59,
                )
            )

        except sqlite3.IntegrityError:
            fk_blocked = True

        if not fk_blocked:
            raise AssertionError(
                "Invalid signal_id was not blocked."
            )

        print(
            "PASS - signal_id foreign key enforced"
        )

        print()
        print("=" * 78)
        print("FINAL RESULT")
        print("=" * 78)
        print()

        print(
            "OutcomeRepository: PASS"
        )

        print(
            "Ask/Bid executable fields: PASS"
        )

        print(
            "Return round-trip: PASS"
        )

        print(
            "Candidate/Resolution scope separation: PASS"
        )

        print(
            "Checkpoint uniqueness protection: PASS"
        )

        print(
            "foreign-key protection: PASS"
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