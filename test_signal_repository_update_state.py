from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, SignalState
from weekly.domain.models import Signal


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    production_db = dbmod.get_database_path().resolve()

    if not production_db.exists():
        raise RuntimeError(
            f"Production database not found: {production_db}"
        )

    before = sha256(production_db)

    with tempfile.TemporaryDirectory(
        prefix="weekly_signal_state_test_"
    ) as temp_dir:
        temp_db = Path(temp_dir) / "weekly_trading_test.db"

        source = sqlite3.connect(
            f"{production_db.as_uri()}?mode=ro",
            uri=True,
        )
        target = sqlite3.connect(temp_db)

        try:
            source.backup(target)
        finally:
            target.close()
            source.close()

        original_get_database_path = dbmod.get_database_path
        dbmod.get_database_path = lambda: temp_db

        try:
            repo = SignalRepository()

            trading_day = date(2099, 1, 5)
            expiry = date(2099, 1, 9)

            seq = repo.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=trading_day,
                target_expiry=expiry,
                direction=Direction.BULLISH,
            )

            candidate_at = datetime(
                2099, 1, 5, 15, 0,
                tzinfo=timezone.utc,
            )

            signal = Signal(
                strategy_version="weekly_v1",
                config_hash="state-update-temp-test",
                ticker="AAPL",
                trading_date_et=trading_day,
                target_expiry=expiry,
                direction=Direction.BULLISH,
                candidate_sequence=seq,
                state=SignalState.CANDIDATE,
                candidate_at=candidate_at,
                net_flow_at_candidate=600000.0,
                flow_dedup_level="alert_uuid",
                stock_data_provider="ALPACA",
                stock_data_feed="IEX",
                options_data_provider="ALPACA",
                options_data_feed="INDICATIVE",
                scenario_return_enabled=False,
            )

            created = repo.create(signal)

            assert created.id is not None
            assert created.state is SignalState.CANDIDATE
            assert created.signal_sign == 1

            confirmed_at = datetime(
                2099, 1, 5, 15, 10,
                tzinfo=timezone.utc,
            )

            updated = repo.update_state(
                signal_id=created.id,
                new_state=SignalState.CONFIRMED,
                expected_state=SignalState.CANDIDATE,
                confirmed_at=confirmed_at,
                net_flow_at_confirmation=750000.0,
            )

            assert updated.state is SignalState.CONFIRMED
            assert updated.confirmed_at == confirmed_at
            assert updated.net_flow_at_confirmation == 750000.0

            reloaded = repo.get_by_id(created.id)

            assert reloaded is not None
            assert reloaded.state is SignalState.CONFIRMED
            assert reloaded.confirmed_at == confirmed_at
            assert reloaded.net_flow_at_confirmation == 750000.0

            stale_guard_passed = False

            try:
                repo.update_state(
                    signal_id=created.id,
                    new_state=SignalState.ACTIVE,
                    expected_state=SignalState.CANDIDATE,
                )
            except RuntimeError:
                stale_guard_passed = True

            assert stale_guard_passed

            after_failed = repo.get_by_id(created.id)

            assert after_failed is not None
            assert after_failed.state is SignalState.CONFIRMED

        finally:
            dbmod.get_database_path = original_get_database_path

    after = sha256(production_db)
    assert before == after

    print("1. temporary database copy: PASS")
    print("2. signal create: PASS")
    print("3. CANDIDATE -> CONFIRMED update: PASS")
    print("4. confirmed_at persistence: PASS")
    print("5. net_flow_at_confirmation persistence: PASS")
    print("6. expected_state stale-write guard: PASS")
    print("7. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("SIGNAL REPOSITORY UPDATE_STATE: PASS 7/7")
    print("=" * 70)


if __name__ == "__main__":
    main()
