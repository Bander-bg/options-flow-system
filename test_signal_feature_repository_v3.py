from __future__ import annotations

import hashlib
import sqlite3
import tempfile

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


import weekly.db.signal_feature_repository as repository_module

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)

from weekly.domain.enums import GateStatus

from weekly.domain.models import SignalFeature


PROJECT_ROOT = Path(__file__).resolve().parent

PRODUCTION_DB = (
    PROJECT_ROOT
    / "weekly_trading.db"
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
            / "signal_feature_v3_test.db"
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

        # Redirect repository to TEMP database.
        repository_module.database_connection = (
            temp_database_connection
        )

        repository_module.database_transaction = (
            temp_database_transaction
        )

        repository = (
            SignalFeatureRepository()
        )

        test_signal_id = 987654321

        captured_at = datetime(
            2026,
            9,
            11,
            16,
            15,
            tzinfo=timezone.utc,
        )

        bar_at = datetime(
            2026,
            9,
            11,
            16,
            15,
            tzinfo=timezone.utc,
        )

        # ------------------------------------------
        # Sequence before insert
        # ------------------------------------------

        assert (
            repository
            .next_evaluation_sequence(
                test_signal_id
            )
            == 1
        )

        print(
            "1. initial evaluation sequence: PASS"
        )

        # ------------------------------------------
        # Create V3 SignalFeature
        # ------------------------------------------

        feature = SignalFeature(
            signal_id=test_signal_id,
            evaluation_sequence=1,
            captured_at=captured_at,

            structure_status=(
                GateStatus.PASS
            ),

            impulse_status=(
                GateStatus.PASS
            ),

            participation_status=(
                GateStatus.PASS
            ),

            price_action_pass_count=3,

            price_action_status=(
                GateStatus.PASS
            ),

            price_action_bar_at=bar_at,

            trigger_open=100.00,
            trigger_high=101.10,
            trigger_low=99.90,
            trigger_close=101.00,
            trigger_volume=200000.0,

            structure_reference_level=(
                100.40
            ),

            structure_break_level=(
                100.50
            ),

            impulse_body=1.00,
            impulse_median_body=0.20,
            impulse_body_atr_ratio=1.00,

            impulse_engulfing_match=True,
            impulse_expansion_match=False,

            participation_avg_slot_volume=None,

            participation_median_slot_volume=(
                100000.0
            ),

            participation_reference_sessions=20,

            participation_rvol=2.00,

            atr_15m=1.00,

            iv_percentile=85.0,

            absolute_flow_strength=750000.0,
            absolute_flow_strength_status=GateStatus.PASS,

            relative_flow_strength=None,
            relative_flow_strength_status=GateStatus.UNKNOWN,

            vwap_distance_atr=0.75,
            vwap_distance_atr_status=GateStatus.PASS,

            sweep_ratio=0.65,
            sweep_ratio_status=GateStatus.PASS,

            opening_evidence=10.0,
            opening_evidence_status=GateStatus.PASS,

            risk_reversal=None,
            risk_reversal_status=GateStatus.UNKNOWN,

            target_expiry_gex_alignment=True,
            target_expiry_gex_alignment_status=GateStatus.PASS,

            negative_gamma_regime=True,
            negative_gamma_regime_status=GateStatus.PASS,

            off_exchange_cluster_score=None,
            off_exchange_cluster_score_status=GateStatus.UNKNOWN,

            directional_flow_confirmation=0.32,
            directional_flow_confirmation_status=GateStatus.PASS,

            iv_percentile_status=GateStatus.FAIL,

            term_structure_inversion=None,
            term_structure_inversion_status=GateStatus.UNKNOWN,

            iv_vs_realized_vol=None,
            iv_vs_realized_vol_status=GateStatus.UNKNOWN,

            target_expiry_iv=0.42,
            iv_30d=0.38,
            term_structure_ratio=1.105,
        )

        created = repository.create(
            feature
        )

        assert created.id is not None

        print(
            "2. create V3 feature: PASS"
        )

        # ------------------------------------------
        # Read back through domain model
        # ------------------------------------------

        loaded = repository.get_by_id(
            created.id
        )

        assert loaded is not None

        assert (
            loaded.impulse_engulfing_match
            is True
        )

        assert (
            loaded.impulse_expansion_match
            is False
        )

        assert (
            loaded
            .participation_median_slot_volume
            == 100000.0
        )

        assert (
            loaded
            .participation_reference_sessions
            == 20
        )

        assert (
            loaded.participation_rvol
            == 2.0
        )

        assert loaded.absolute_flow_strength == 750000.0
        assert loaded.absolute_flow_strength_status is GateStatus.PASS

        assert loaded.relative_flow_strength is None
        assert loaded.relative_flow_strength_status is GateStatus.UNKNOWN

        assert loaded.vwap_distance_atr == 0.75
        assert loaded.vwap_distance_atr_status is GateStatus.PASS

        assert loaded.sweep_ratio == 0.65
        assert loaded.sweep_ratio_status is GateStatus.PASS

        assert loaded.opening_evidence == 10.0
        assert loaded.opening_evidence_status is GateStatus.PASS

        assert loaded.target_expiry_gex_alignment is True
        assert loaded.negative_gamma_regime is True

        assert loaded.directional_flow_confirmation == 0.32
        assert loaded.directional_flow_confirmation_status is GateStatus.PASS

        assert loaded.iv_percentile == 85.0
        assert loaded.iv_percentile_status is GateStatus.FAIL

        assert loaded.term_structure_inversion is None
        assert loaded.term_structure_inversion_status is GateStatus.UNKNOWN

        assert loaded.target_expiry_iv == 0.42
        assert loaded.iv_30d == 0.38
        assert loaded.term_structure_ratio == 1.105

        print(
            "3. V3 model round-trip: PASS"
        )

        # ------------------------------------------
        # Verify raw SQLite storage
        # ------------------------------------------

        with temp_database_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    impulse_engulfing_match,
                    impulse_expansion_match,
                    participation_median_slot_volume,
                    participation_reference_sessions
                FROM signal_features
                WHERE id = ?
                """,
                (
                    created.id,
                ),
            ).fetchone()

        assert row is not None

        assert (
            row[
                "impulse_engulfing_match"
            ]
            == 1
        )

        assert (
            row[
                "impulse_expansion_match"
            ]
            == 0
        )

        assert (
            row[
                "participation_median_slot_volume"
            ]
            == 100000.0
        )

        assert (
            row[
                "participation_reference_sessions"
            ]
            == 20
        )

        print(
            "4. raw SQLite V3 fields: PASS"
        )

        # ------------------------------------------
        # Latest query
        # ------------------------------------------

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

        print(
            "5. latest feature query: PASS"
        )

        # ------------------------------------------
        # Next sequence
        # ------------------------------------------

        assert (
            repository
            .next_evaluation_sequence(
                test_signal_id
            )
            == 2
        )

        print(
            "6. next evaluation sequence: PASS"
        )

        # ------------------------------------------
        # All snapshots for signal
        # ------------------------------------------

        second = repository.create(
            SignalFeature(
                signal_id=test_signal_id,
                evaluation_sequence=2,
                captured_at=datetime(
                    2026,
                    9,
                    11,
                    16,
                    30,
                    tzinfo=timezone.utc,
                ),
                price_action_bar_at=datetime(
                    2026,
                    9,
                    11,
                    16,
                    30,
                    tzinfo=timezone.utc,
                ),
                price_action_status=GateStatus.FAIL,
            )
        )

        all_features = repository.get_all_for_signal(
            test_signal_id
        )

        assert len(all_features) == 2
        assert all_features[0].id == created.id
        assert all_features[0].evaluation_sequence == 1
        assert all_features[1].id == second.id
        assert all_features[1].evaluation_sequence == 2

        print(
            "7. all signal snapshots ordered ASC: PASS"
        )
    # ----------------------------------------------
    # Production DB must remain untouched
    # ----------------------------------------------

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
        "8. production database modified: NO"
    )

    print()
    print("=" * 70)
    print(
        "SIGNAL FEATURE REPOSITORY V3: PASS 8/8"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()