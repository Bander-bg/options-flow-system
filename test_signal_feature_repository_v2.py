from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.signal_feature_repository as repo_module

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.domain.enums import (
    Direction,
    GateStatus,
    SignalState,
)
from weekly.domain.models import (
    Signal,
    SignalFeature,
)
from weekly.db.signal_repository import (
    SignalRepository,
)

import weekly.db.signal_repository as signal_repo_module


ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    ROOT
    / "weekly_trading.db"
)

TEST_DB = (
    ROOT
    / "weekly_signal_feature_repository_v2_test.db"
)


ET = ZoneInfo(
    "America/New_York"
)


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


def patch_repositories():
    repo_module.database_connection = (
        test_database_connection
    )

    repo_module.database_transaction = (
        test_database_transaction
    )

    signal_repo_module.database_connection = (
        test_database_connection
    )

    signal_repo_module.database_transaction = (
        test_database_transaction
    )


def clear_test_tables():
    connection = sqlite3.connect(
        TEST_DB
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "DELETE FROM signal_features"
    )

    connection.execute(
        "DELETE FROM signals"
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


def create_parent_signal() -> Signal:
    repository = (
        SignalRepository()
    )

    signal = Signal(
        strategy_version=(
            "weekly_v1"
        ),

        config_hash=(
            "test_config_hash"
        ),

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

        direction=(
            Direction.BULLISH
        ),

        candidate_sequence=1,

        state=(
            SignalState.CANDIDATE
        ),

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

        confirmed_at=None,

        terminal_at=None,

        terminal_reason=None,

        net_flow_at_candidate=(
            750_000.0
        ),

        net_flow_at_confirmation=None,

        flow_dedup_level=(
            "alert_uuid"
        ),

        stock_data_provider=None,
        stock_data_feed=None,

        options_data_provider=None,
        options_data_feed=None,

        theta_convention_status=(
            "UNRESOLVED"
        ),

        scenario_return_enabled=False,
    )

    return repository.create(
        signal
    )


def make_feature(
    *,
    signal_id: int,
    evaluation_sequence: int,
    captured_at: datetime,
) -> SignalFeature:
    return SignalFeature(
        signal_id=signal_id,

        evaluation_sequence=(
            evaluation_sequence
        ),

        captured_at=(
            captured_at
        ),

        flow_net=750_000.0,

        flow_threshold=500_000.0,

        weekly_vwap=220.50,

        underlying_price=225.40,

        vwap_status=(
            GateStatus.PASS
        ),

        efficiency_ratio=0.42,

        efficiency_ratio_status=(
            GateStatus.PASS
        ),

        next_earnings_date=date(
            2026,
            10,
            29,
        ),

        earnings_event_risk_status=(
            GateStatus.PASS
        ),

        expected_move=8.10,

        expected_move_perc=2.55,

        selected_contract_symbol=None,

        selected_contract_right=None,

        selected_contract_strike=None,

        selected_contract_bid=None,

        selected_contract_ask=None,

        selected_contract_mark=None,

        selected_contract_delta=None,

        selected_contract_gamma=None,

        selected_contract_theta=None,

        selected_contract_vega=None,

        selected_contract_iv=None,

        selected_contract_spread_pct=None,

        selected_contract_quote_age_seconds=None,

        eligible_contract_status=None,

        # ----------------------------------------------
        # PRICE ACTION STATUS
        # ----------------------------------------------

        structure_status=(
            GateStatus.PASS
        ),

        impulse_status=(
            GateStatus.FAIL
        ),

        participation_status=(
            GateStatus.PASS
        ),

        price_action_pass_count=2,

        price_action_status=(
            GateStatus.PASS
        ),

        # ----------------------------------------------
        # PRICE ACTION EVIDENCE
        # ----------------------------------------------

        price_action_bar_at=datetime(
            2026,
            9,
            4,
            10,
            15,
            tzinfo=ET,
        ),

        trigger_open=224.80,

        trigger_high=225.70,

        trigger_low=224.60,

        trigger_close=225.40,

        trigger_volume=1_250_000.0,

        structure_reference_level=(
            224.95
        ),

        structure_break_level=(
            225.05
        ),

        impulse_body=0.60,

        impulse_median_body=0.48,

        impulse_body_atr_ratio=0.47,

        participation_avg_slot_volume=(
            750_000.0
        ),

        participation_rvol=(
            1.6666666667
        ),

        atr_1h=4.25,

        atr_15m=1.28,

        iv_percentile=72.0,

        base_score=None,

        volatility_penalty=None,

        final_score=None,

        coverage_points=None,

        coverage_pct=None,

        raw_grade=None,

        final_grade=None,
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
    actual: float | None,
    expected: float,
    name: str,
    tolerance: float = 1e-9,
):
    if actual is None:
        raise AssertionError(
            f"{name}: actual is None"
        )

    if abs(
        actual - expected
    ) > tolerance:
        raise AssertionError(
            f"{name}: expected "
            f"{expected!r}, got {actual!r}"
        )


def main():
    print("=" * 78)
    print(
        "WEEKLY_V1 SIGNALFEATURE REPOSITORY V2 TEST"
    )
    print("=" * 78)
    print()

    production_hash_before = (
        file_sha256(
            PRODUCTION_DB
        )
    )

    try:
        clone_database()

        patch_repositories()

        clear_test_tables()

        # --------------------------------------------------
        # PARENT SIGNAL
        # --------------------------------------------------

        signal = (
            create_parent_signal()
        )

        if signal.id is None:
            raise AssertionError(
                "Parent signal has no id."
            )

        print(
            "PASS - Parent Signal created "
            "in temporary DB"
        )

        # --------------------------------------------------
        # FEATURE CREATE
        # --------------------------------------------------

        repository = (
            SignalFeatureRepository()
        )

        feature = make_feature(
            signal_id=signal.id,

            evaluation_sequence=1,

            captured_at=datetime(
                2026,
                9,
                4,
                10,
                16,
                tzinfo=ET,
            ),
        )

        created = repository.create(
            feature
        )

        if created.id is None:
            raise AssertionError(
                "SignalFeature has no id."
            )

        print(
            "PASS - SignalFeature created"
        )

        # --------------------------------------------------
        # READ BACK
        # --------------------------------------------------

        loaded = repository.get_by_id(
            created.id
        )

        if loaded is None:
            raise AssertionError(
                "SignalFeature could not "
                "be read back."
            )

        # --------------------------------------------------
        # STATUS ROUND TRIP
        # --------------------------------------------------

        assert_equal(
            loaded.structure_status,
            GateStatus.PASS,
            "structure_status",
        )

        assert_equal(
            loaded.impulse_status,
            GateStatus.FAIL,
            "impulse_status",
        )

        assert_equal(
            loaded.participation_status,
            GateStatus.PASS,
            "participation_status",
        )

        assert_equal(
            loaded.price_action_pass_count,
            2,
            "price_action_pass_count",
        )

        assert_equal(
            loaded.price_action_status,
            GateStatus.PASS,
            "price_action_status",
        )

        print(
            "PASS - Price Action status round-trip"
        )

        # --------------------------------------------------
        # BAR EVIDENCE ROUND TRIP
        # --------------------------------------------------

        assert_equal(
            loaded.price_action_bar_at,
            datetime(
                2026,
                9,
                4,
                10,
                15,
                tzinfo=ET,
            ),
            "price_action_bar_at",
        )

        assert_close(
            loaded.trigger_open,
            224.80,
            "trigger_open",
        )

        assert_close(
            loaded.trigger_high,
            225.70,
            "trigger_high",
        )

        assert_close(
            loaded.trigger_low,
            224.60,
            "trigger_low",
        )

        assert_close(
            loaded.trigger_close,
            225.40,
            "trigger_close",
        )

        assert_close(
            loaded.trigger_volume,
            1_250_000.0,
            "trigger_volume",
        )

        print(
            "PASS - Trigger-bar evidence round-trip"
        )

        # --------------------------------------------------
        # STRUCTURE EVIDENCE
        # --------------------------------------------------

        assert_close(
            loaded.structure_reference_level,
            224.95,
            "structure_reference_level",
        )

        assert_close(
            loaded.structure_break_level,
            225.05,
            "structure_break_level",
        )

        print(
            "PASS - Structure evidence round-trip"
        )

        # --------------------------------------------------
        # IMPULSE EVIDENCE
        # --------------------------------------------------

        assert_close(
            loaded.impulse_body,
            0.60,
            "impulse_body",
        )

        assert_close(
            loaded.impulse_median_body,
            0.48,
            "impulse_median_body",
        )

        assert_close(
            loaded.impulse_body_atr_ratio,
            0.47,
            "impulse_body_atr_ratio",
        )

        print(
            "PASS - Impulse evidence round-trip"
        )

        # --------------------------------------------------
        # PARTICIPATION EVIDENCE
        # --------------------------------------------------

        assert_close(
            loaded.participation_avg_slot_volume,
            750_000.0,
            "participation_avg_slot_volume",
        )

        assert_close(
            loaded.participation_rvol,
            1.6666666667,
            "participation_rvol",
        )

        print(
            "PASS - Participation evidence round-trip"
        )

        # --------------------------------------------------
        # ATR
        # --------------------------------------------------

        assert_close(
            loaded.atr_1h,
            4.25,
            "atr_1h",
        )

        assert_close(
            loaded.atr_15m,
            1.28,
            "atr_15m",
        )

        print(
            "PASS - ATR evidence round-trip"
        )

        # --------------------------------------------------
        # NEXT SEQUENCE
        # --------------------------------------------------

        next_sequence = (
            repository
            .next_evaluation_sequence(
                signal.id
            )
        )

        assert_equal(
            next_sequence,
            2,
            "next evaluation sequence",
        )

        print(
            "PASS - Next evaluation sequence"
        )

        # --------------------------------------------------
        # SECOND FEATURE / LATEST
        # --------------------------------------------------

        second_feature = make_feature(
            signal_id=signal.id,

            evaluation_sequence=2,

            captured_at=datetime(
                2026,
                9,
                4,
                10,
                19,
                tzinfo=ET,
            ),
        )

        repository.create(
            second_feature
        )

        latest = (
            repository
            .get_latest_for_signal(
                signal.id
            )
        )

        if latest is None:
            raise AssertionError(
                "Latest feature missing."
            )

        assert_equal(
            latest.evaluation_sequence,
            2,
            "latest evaluation sequence",
        )

        print(
            "PASS - Latest evaluation query"
        )

        # --------------------------------------------------
        # UNIQUE PROTECTION
        # --------------------------------------------------

        duplicate_error = False

        try:
            repository.create(
                second_feature
            )

        except sqlite3.IntegrityError:
            duplicate_error = True

        if not duplicate_error:
            raise AssertionError(
                "Duplicate evaluation_sequence "
                "was not rejected."
            )

        print(
            "PASS - Duplicate evaluation protection"
        )

        # --------------------------------------------------
        # FOREIGN KEY PROTECTION
        # --------------------------------------------------

        invalid_feature = make_feature(
            signal_id=999999,

            evaluation_sequence=1,

            captured_at=datetime(
                2026,
                9,
                4,
                10,
                20,
                tzinfo=ET,
            ),
        )

        fk_error = False

        try:
            repository.create(
                invalid_feature
            )

        except sqlite3.IntegrityError:
            fk_error = True

        if not fk_error:
            raise AssertionError(
                "Invalid signal_id was not "
                "rejected by foreign key."
            )

        print(
            "PASS - Signal foreign key protection"
        )

        # --------------------------------------------------
        # PRODUCTION DB PROTECTION
        # --------------------------------------------------

        production_hash_after = (
            file_sha256(
                PRODUCTION_DB
            )
        )

        production_unchanged = (
            production_hash_before
            == production_hash_after
        )

        if not production_unchanged:
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
            "SignalFeatureRepository V2: PASS"
        )

        print(
            "Price Action status persistence: PASS"
        )

        print(
            "Trigger-bar evidence persistence: PASS"
        )

        print(
            "Structure evidence persistence: PASS"
        )

        print(
            "Impulse evidence persistence: PASS"
        )

        print(
            "Participation evidence persistence: PASS"
        )

        print(
            "ATR persistence: PASS"
        )

        print(
            "Evaluation sequencing: PASS"
        )

        print(
            "Database uniqueness/FK protection: PASS"
        )

        print(
            "Production weekly_trading.db "
            "modified: NO"
        )

        print()

        print(
            "PRICE ACTION PERSISTENCE LAYER: READY"
        )

    finally:
        cleanup()


if __name__ == "__main__":
    main()