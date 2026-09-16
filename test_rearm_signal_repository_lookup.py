from pathlib import Path
from dataclasses import replace
from datetime import datetime

import test_signal_repository as base

from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, SignalState


ET = base.ET


def main():
    print("=" * 78)
    print("REARM SIGNAL REPOSITORY LOOKUP TEST")
    print("=" * 78)

    base.create_temp_database()

    try:
        base.patch_repository_database()

        repository = SignalRepository()

        strategy = "weekly_v1_rearm_lookup_test"

        signal_1 = repository.create(
            replace(
                base.make_signal(1),
                strategy_version=strategy,
            )
        )

        confirmed_at = datetime(
            2026,
            9,
            4,
            10,
            45,
            tzinfo=ET,
        )

        signal_1 = repository.update_state(
            signal_id=signal_1.id,
            new_state=SignalState.CONFIRMED,
            expected_state=SignalState.CANDIDATE,
            confirmed_at=confirmed_at,
            net_flow_at_confirmation=650_000,
        )

        signal_1 = repository.update_state(
            signal_id=signal_1.id,
            new_state=SignalState.ACTIVE,
            expected_state=SignalState.CONFIRMED,
        )

        signal_2 = repository.create(
            replace(
                base.make_signal(2),
                strategy_version=strategy,
            )
        )

        latest = repository.get_latest(
            strategy_version=strategy,
            ticker="AAPL",
            trading_date_et=signal_2.trading_date_et,
            target_expiry=signal_2.target_expiry,
            direction=Direction.BULLISH,
        )

        if latest is None or latest.id != signal_2.id:
            raise AssertionError(
                "get_latest should return newest raw sequence."
            )

        confirmed = repository.get_latest_with_confirmation(
            strategy_version=strategy,
            ticker="AAPL",
            trading_date_et=signal_2.trading_date_et,
            target_expiry=signal_2.target_expiry,
            direction=Direction.BULLISH,
        )

        if confirmed is None:
            raise AssertionError(
                "Confirmed provenance signal was not found."
            )

        if confirmed.id != signal_1.id:
            raise AssertionError(
                "Lookup did not skip newer unconfirmed signal."
            )

        if confirmed.state is not SignalState.ACTIVE:
            raise AssertionError(
                "Lookup incorrectly depends on CONFIRMED state."
            )

        if confirmed.confirmed_at != confirmed_at:
            raise AssertionError(
                "confirmed_at provenance mismatch."
            )

        if confirmed.net_flow_at_confirmation != 650_000:
            raise AssertionError(
                "net_flow_at_confirmation provenance mismatch."
            )

        bearish = repository.get_latest_with_confirmation(
            strategy_version=strategy,
            ticker="AAPL",
            trading_date_et=signal_2.trading_date_et,
            target_expiry=signal_2.target_expiry,
            direction=Direction.BEARISH,
        )

        if bearish is not None:
            raise AssertionError(
                "Scope isolation failed."
            )

        print("1. newer unconfirmed sequence skipped: PASS")
        print("2. confirmed provenance returned: PASS")
        print("3. ACTIVE state remains eligible for lookup: PASS")
        print("4. confirmation fields preserved: PASS")
        print("5. direction scope isolation: PASS")
        print()
        print("REARM SIGNAL REPOSITORY LOOKUP: PASS 5/5")

    finally:
        for path in [
            base.TEMP_DB,
            Path(str(base.TEMP_DB) + "-wal"),
            Path(str(base.TEMP_DB) + "-shm"),
        ]:
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
