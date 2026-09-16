from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.signal_feature_repository as feature_repo_module
import weekly.db.signal_repository as signal_repo_module

from weekly.db.database import get_database_path
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import (
    Direction,
    GateStatus,
    OptionRight,
    SignalState,
)
from weekly.domain.models import (
    Signal,
    SignalFeature,
)


ET = ZoneInfo("America/New_York")

TEMP_DB = Path(
    "weekly_signal_feature_repository_test.db"
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

    feature_repo_module.database_connection = (
        temp_database_connection
    )

    feature_repo_module.database_transaction = (
        temp_database_transaction
    )


def make_signal() -> Signal:
    return Signal(
        strategy_version="weekly_v1",
        config_hash="feature_repo_test_hash",

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

        state=SignalState.CANDIDATE,

        candidate_at=datetime(
            2026,
            9,
            4,
            10,
            0,
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

        net_flow_at_candidate=650_000,

        flow_dedup_level="alert_composite",

        stock_data_provider="ALPACA",
        stock_data_feed="IEX",

        options_data_provider="ALPACA",
        options_data_feed="INDICATIVE",

        theta_convention_status="UNRESOLVED",

        scenario_return_enabled=False,
    )


def make_feature(
    *,
    signal_id: int,
    sequence: int,
) -> SignalFeature:
    return SignalFeature(
        signal_id=signal_id,
        evaluation_sequence=sequence,

        captured_at=datetime(
            2026,
            9,
            4,
            10,
            sequence,
            tzinfo=ET,
        ),

        flow_net=700_000,
        flow_threshold=500_000,

        weekly_vwap=318.50,
        underlying_price=320.25,

        vwap_status=GateStatus.PASS,

        efficiency_ratio=0.42,
        efficiency_ratio_status=GateStatus.PASS,

        next_earnings_date=date(
            2026,
            10,
            29,
        ),

        earnings_event_risk_status=GateStatus.PASS,

        expected_move=8.075,
        expected_move_perc=0.02525,

        selected_contract_symbol=(
            "AAPL260911C00320000"
        ),

        selected_contract_right=OptionRight.CALL,

        selected_contract_strike=320.0,

        selected_contract_bid=4.80,
        selected_contract_ask=5.00,
        selected_contract_mark=4.90,

        selected_contract_delta=0.51,
        selected_contract_gamma=0.04,
        selected_contract_theta=-0.08,
        selected_contract_vega=0.12,
        selected_contract_iv=0.27,

        selected_contract_spread_pct=0.04,

        selected_contract_quote_age_seconds=12.5,

        eligible_contract_status=GateStatus.PASS,

        structure_status=GateStatus.PASS,
        impulse_status=GateStatus.FAIL,
        participation_status=GateStatus.PASS,

        price_action_pass_count=2,
        price_action_status=GateStatus.PASS,

        atr_1h=5.20,
        atr_15m=1.35,

        iv_percentile=62.0,

        base_score=82.0,
        volatility_penalty=3.0,
        final_score=79.0,

        coverage_points=115.0,
        coverage_pct=100.0,

        raw_grade="B",
        final_grade="B",
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
        "WEEKLY_V1 SIGNAL FEATURE REPOSITORY TEST"
    )
    print("=" * 78)
    print()

    create_temp_database()

    try:
        patch_repositories()

        signal_repository = SignalRepository()
        feature_repository = (
            SignalFeatureRepository()
        )

        # --------------------------------------------------
        # TEST 1 - parent signal
        # --------------------------------------------------

        signal = signal_repository.create(
            make_signal()
        )

        if signal.id is None:
            raise AssertionError(
                "Signal id missing."
            )

        print(
            "PASS - parent signal created"
        )

        # --------------------------------------------------
        # TEST 2 - initial evaluation sequence
        # --------------------------------------------------

        next_sequence = (
            feature_repository
            .next_evaluation_sequence(
                signal.id
            )
        )

        assert_equal(
            next_sequence,
            1,
            "initial evaluation sequence",
        )

        print(
            "PASS - initial evaluation_sequence = 1"
        )

        # --------------------------------------------------
        # TEST 3 - create feature
        # --------------------------------------------------

        feature_1 = (
            feature_repository.create(
                make_feature(
                    signal_id=signal.id,
                    sequence=1,
                )
            )
        )

        if feature_1.id is None:
            raise AssertionError(
                "Feature id missing."
            )

        print(
            "PASS - create signal feature"
        )

        # --------------------------------------------------
        # TEST 4 - round-trip mapping
        # --------------------------------------------------

        loaded = (
            feature_repository.get_by_id(
                feature_1.id
            )
        )

        if loaded is None:
            raise AssertionError(
                "Feature could not be read."
            )

        assert_equal(
            loaded.vwap_status,
            GateStatus.PASS,
            "vwap_status",
        )

        assert_equal(
            loaded.impulse_status,
            GateStatus.FAIL,
            "impulse_status",
        )

        assert_equal(
            loaded.selected_contract_right,
            OptionRight.CALL,
            "option right",
        )

        assert_equal(
            loaded.price_action_pass_count,
            2,
            "price action pass count",
        )

        assert_equal(
            loaded.price_action_status,
            GateStatus.PASS,
            "price action status",
        )

        assert_close(
            loaded.selected_contract_delta,
            0.51,
            "delta",
        )

        assert_close(
            loaded.selected_contract_spread_pct,
            0.04,
            "spread pct",
        )

        assert_close(
            loaded.final_score,
            79.0,
            "final score",
        )

        assert_close(
            loaded.coverage_pct,
            100.0,
            "coverage pct",
        )

        assert_equal(
            loaded.raw_grade,
            "B",
            "raw grade",
        )

        assert_equal(
            loaded.final_grade,
            "B",
            "final grade",
        )

        print(
            "PASS - feature round-trip mapping"
        )

        # --------------------------------------------------
        # TEST 5 - evaluation sequence increments
        # --------------------------------------------------

        next_sequence = (
            feature_repository
            .next_evaluation_sequence(
                signal.id
            )
        )

        assert_equal(
            next_sequence,
            2,
            "second evaluation sequence",
        )

        print(
            "PASS - evaluation_sequence increments"
        )

        # --------------------------------------------------
        # TEST 6 - second feature + latest
        # --------------------------------------------------

        feature_2 = (
            feature_repository.create(
                make_feature(
                    signal_id=signal.id,
                    sequence=2,
                )
            )
        )

        latest = (
            feature_repository
            .get_latest_for_signal(
                signal.id
            )
        )

        if latest is None:
            raise AssertionError(
                "Latest feature missing."
            )

        assert_equal(
            latest.id,
            feature_2.id,
            "latest feature id",
        )

        assert_equal(
            latest.evaluation_sequence,
            2,
            "latest evaluation sequence",
        )

        print(
            "PASS - get_latest_for_signal"
        )

        # --------------------------------------------------
        # TEST 7 - duplicate sequence blocked
        # --------------------------------------------------

        duplicate_blocked = False

        try:
            feature_repository.create(
                make_feature(
                    signal_id=signal.id,
                    sequence=2,
                )
            )

        except sqlite3.IntegrityError:
            duplicate_blocked = True

        if not duplicate_blocked:
            raise AssertionError(
                "Duplicate evaluation_sequence "
                "was not blocked."
            )

        print(
            "PASS - duplicate evaluation_sequence blocked"
        )

        # --------------------------------------------------
        # TEST 8 - FK protection
        # --------------------------------------------------

        foreign_key_blocked = False

        try:
            feature_repository.create(
                make_feature(
                    signal_id=999999,
                    sequence=1,
                )
            )

        except sqlite3.IntegrityError:
            foreign_key_blocked = True

        if not foreign_key_blocked:
            raise AssertionError(
                "Invalid signal_id foreign key "
                "was not blocked."
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
            "SignalFeatureRepository: PASS"
        )

        print(
            "GateStatus round-trip: PASS"
        )

        print(
            "Contract/Greeks round-trip: PASS"
        )

        print(
            "Score/Coverage round-trip: PASS"
        )

        print(
            "evaluation_sequence protection: PASS"
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