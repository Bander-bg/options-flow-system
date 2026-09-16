from __future__ import annotations

import hashlib
import sqlite3
import tempfile

from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


from config import load_weekly_config

import weekly.db.signal_feature_repository as repository_module

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)

from weekly.domain.enums import (
    Direction,
    GateStatus,
)

from weekly.domain.models import SignalFeature

from weekly.services.price_action_service import (
    PriceActionService,
    PriceBar,
)

from weekly.services.price_action_evaluation_service import (
    PriceActionEvaluationService,
)


PROJECT_ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    PROJECT_ROOT
    / "weekly_trading.db"
)

ET = ZoneInfo(
    "America/New_York"
)


def file_hash(
    path: Path,
) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            hasher.update(
                chunk
            )

    return hasher.hexdigest()


def copy_database(
    source_path: Path,
    destination_path: Path,
) -> None:
    source = sqlite3.connect(
        f"file:{source_path.as_posix()}?mode=ro",
        uri=True,
    )

    destination = sqlite3.connect(
        destination_path
    )

    try:
        source.backup(
            destination
        )

    finally:
        destination.close()
        source.close()


def make_bar(
    start_at: datetime,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> PriceBar:
    return PriceBar(
        start_at=start_at,
        end_at=(
            start_at
            + timedelta(minutes=15)
        ),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def build_prior_bars(
    trigger_start: datetime,
) -> list[PriceBar]:
    bars: list[PriceBar] = []

    first_start = (
        trigger_start
        - timedelta(minutes=150)
    )

    for i in range(9):
        start_at = (
            first_start
            + timedelta(
                minutes=15 * i
            )
        )

        bars.append(
            make_bar(
                start_at,
                open_=100.00,
                high=100.40,
                low=99.80,
                close=100.20,
                volume=100000.0,
            )
        )

    # Previous candle bearish so the trigger
    # can qualify as bullish engulfing.
    bars.append(
        make_bar(
            trigger_start
            - timedelta(minutes=15),
            open_=100.30,
            high=100.40,
            low=99.90,
            close=100.10,
            volume=100000.0,
        )
    )

    return bars


def main() -> None:
    if not PRODUCTION_DB.exists():
        raise RuntimeError(
            "weekly_trading.db not found"
        )

    production_hash_before = (
        file_hash(
            PRODUCTION_DB
        )
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db = (
            Path(temp_dir)
            / "price_action_evaluation_test.db"
        )

        copy_database(
            PRODUCTION_DB,
            temp_db,
        )

        @contextmanager
        def temp_database_connection():
            connection = sqlite3.connect(
                temp_db,
                timeout=5.0,
            )

            connection.row_factory = (
                sqlite3.Row
            )

            # Synthetic signal_id is used only
            # inside this disposable test.
            connection.execute(
                "PRAGMA foreign_keys = OFF;"
            )

            try:
                yield connection

            finally:
                connection.close()

        @contextmanager
        def temp_database_transaction():
            connection = sqlite3.connect(
                temp_db,
                timeout=5.0,
            )

            connection.row_factory = (
                sqlite3.Row
            )

            connection.execute(
                "PRAGMA foreign_keys = OFF;"
            )

            try:
                connection.execute(
                    "BEGIN;"
                )

                yield connection

                connection.commit()

            except Exception:
                connection.rollback()
                raise

            finally:
                connection.close()

        # Redirect SignalFeatureRepository
        # to TEMP database only.
        repository_module.database_connection = (
            temp_database_connection
        )

        repository_module.database_transaction = (
            temp_database_transaction
        )

        repository = (
            SignalFeatureRepository()
        )

        config = load_weekly_config()

        price_action_service = (
            PriceActionService
            .from_weekly_config(
                config
            )
        )

        evaluation_service = (
            PriceActionEvaluationService(
                price_action_service=(
                    price_action_service
                ),
                feature_repository=(
                    repository
                ),
            )
        )

        test_signal_id = 987654321

        trigger_start = datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=ET,
        )

        candidate_at = (
            trigger_start
        )

        deadline = (
            candidate_at
            + timedelta(minutes=30)
        )

        trigger_bar = make_bar(
            trigger_start,
            open_=100.00,
            high=101.10,
            low=99.90,
            close=101.00,
            volume=200000.0,
        )

        prior_bars = (
            build_prior_bars(
                trigger_start
            )
        )

        historical_volumes = [
            100000.0
            for _ in range(20)
        ]

        # ==================================================
        # 1. CREATE PREVIOUS FEATURE SNAPSHOT
        #
        # This simulates data that existed before
        # Price Action evaluation.
        # ==================================================

        previous = SignalFeature(
            signal_id=test_signal_id,
            evaluation_sequence=1,
            captured_at=(
                trigger_start
                - timedelta(minutes=1)
            ),

            flow_net=750000.0,
            flow_threshold=500000.0,

            weekly_vwap=99.50,
            underlying_price=100.00,

            vwap_status=GateStatus.PASS,

            efficiency_ratio=0.42,
            efficiency_ratio_status=(
                GateStatus.PASS
            ),

            expected_move=5.0,
            expected_move_perc=0.05,

            atr_1h=2.50,
        )

        created_previous = (
            repository.create(
                previous
            )
        )

        assert (
            created_previous.id
            is not None
        )

        assert (
            created_previous
            .evaluation_sequence
            == 1
        )

        print(
            "1. previous feature snapshot: PASS"
        )

        # ==================================================
        # 2. PRICE ACTION → PERSIST
        # ==================================================

        evaluation = (
            evaluation_service
            .evaluate_and_persist(
                signal_id=test_signal_id,
                direction=Direction.BULLISH,
                candidate_at=candidate_at,
                confirmation_deadline_at=(
                    deadline
                ),
                captured_at=(
                    trigger_bar.end_at
                ),
                trigger_bar=trigger_bar,
                prior_bars=prior_bars,
                atr_15m=1.0,
                atr_1h=2.60,
                historical_same_slot_volumes=(
                    historical_volumes
                ),
            )
        )

        assert (
            evaluation.result
            .price_action_status
            == GateStatus.PASS
        )

        assert (
            evaluation.result
            .price_action_pass_count
            == 3
        )

        print(
            "2. Price Action calculation: PASS"
        )

        # ==================================================
        # 3. NEW IMMUTABLE SNAPSHOT
        # ==================================================

        created = evaluation.feature

        assert created.id is not None

        assert (
            created.id
            != created_previous.id
        )

        assert (
            created.evaluation_sequence
            == 2
        )

        print(
            "3. immutable evaluation snapshot: PASS"
        )

        # ==================================================
        # 4. OLD NON-PRICE-ACTION VALUES PRESERVED
        # ==================================================

        assert (
            created.flow_net
            == 750000.0
        )

        assert (
            created.flow_threshold
            == 500000.0
        )

        assert (
            created.weekly_vwap
            == 99.50
        )

        assert (
            created.underlying_price
            == 100.00
        )

        assert (
            created.vwap_status
            == GateStatus.PASS
        )

        assert (
            created.efficiency_ratio
            == 0.42
        )

        assert (
            created
            .efficiency_ratio_status
            == GateStatus.PASS
        )

        assert (
            created.expected_move
            == 5.0
        )

        print(
            "4. previous feature data preserved: PASS"
        )

        # ==================================================
        # 5. PRICE ACTION STATUS/EVIDENCE PERSISTED
        # ==================================================

        assert (
            created.structure_status
            == GateStatus.PASS
        )

        assert (
            created.impulse_status
            == GateStatus.PASS
        )

        assert (
            created.participation_status
            == GateStatus.PASS
        )

        assert (
            created.price_action_status
            == GateStatus.PASS
        )

        assert (
            created.price_action_pass_count
            == 3
        )

        assert (
            created.impulse_engulfing_match
            is True
        )

        assert (
            created.impulse_expansion_match
            is True
        )

        assert (
            created
            .participation_median_slot_volume
            == 100000.0
        )

        assert (
            created
            .participation_reference_sessions
            == 20
        )

        assert (
            created.participation_rvol
            == 2.0
        )

        assert (
            created.atr_15m
            == 1.0
        )

        assert (
            created.atr_1h
            == 2.60
        )

        print(
            "5. Price Action evidence persisted: PASS"
        )

        # ==================================================
        # 6. VERIFY READ-BACK FROM SQLITE
        # ==================================================

        loaded = (
            repository.get_by_id(
                created.id
            )
        )

        assert loaded is not None

        assert (
            loaded.evaluation_sequence
            == 2
        )

        assert (
            loaded.price_action_status
            == GateStatus.PASS
        )

        assert (
            loaded.flow_net
            == 750000.0
        )

        assert (
            loaded.impulse_engulfing_match
            is True
        )

        assert (
            loaded.impulse_expansion_match
            is True
        )

        assert (
            loaded
            .participation_reference_sessions
            == 20
        )

        print(
            "6. SQLite round-trip: PASS"
        )

        # ==================================================
        # 7. LATEST SNAPSHOT
        # ==================================================

        latest = (
            repository
            .get_latest_for_signal(
                test_signal_id
            )
        )

        assert latest is not None

        assert (
            latest.id
            == created.id
        )

        assert (
            latest.evaluation_sequence
            == 2
        )

        assert (
            repository
            .next_evaluation_sequence(
                test_signal_id
            )
            == 3
        )

        print(
            "7. latest/next sequence: PASS"
        )

        # ==================================================
        # 8. VERIFY BOTH SNAPSHOTS EXIST
        # ==================================================

        with temp_database_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    evaluation_sequence
                FROM signal_features
                WHERE signal_id = ?
                ORDER BY evaluation_sequence ASC
                """,
                (
                    test_signal_id,
                ),
            ).fetchall()

        assert len(rows) == 2

        assert (
            rows[0]["evaluation_sequence"]
            == 1
        )

        assert (
            rows[1]["evaluation_sequence"]
            == 2
        )

        print(
            "8. snapshot history preserved: PASS"
        )

    # ==================================================
    # PRODUCTION DATABASE SAFETY
    # ==================================================

    production_hash_after = (
        file_hash(
            PRODUCTION_DB
        )
    )

    assert (
        production_hash_before
        == production_hash_after
    ), (
        "Production weekly_trading.db "
        "was modified."
    )

    print(
        "9. production database modified: NO"
    )

    print()
    print("=" * 70)
    print(
        "PRICE ACTION EVALUATION PIPELINE: PASS 9/9"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()