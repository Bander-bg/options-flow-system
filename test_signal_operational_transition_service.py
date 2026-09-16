from __future__ import annotations

from pathlib import Path

from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import SignalState
from weekly.services.signal_operational_transition_service import (
    SignalOperationalTransitionService,
)

from test_trade_repository import (
    TEMP_DB,
    create_temp_database,
    make_signal,
    patch_repositories,
)


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        signal_repository = SignalRepository()

        signal = signal_repository.create(
            make_signal()
        )

        assert signal.id is not None
        assert signal.state is SignalState.CONFIRMED

        service = SignalOperationalTransitionService(
            signal_repository=signal_repository,
        )

        activated = service.activate(
            signal_id=signal.id,
        )

        assert activated.persisted is True
        assert (
            activated.reason
            == "CONFIRMED_TO_ACTIVE"
        )
        assert (
            activated.signal.state
            is SignalState.ACTIVE
        )

        repeated = service.activate(
            signal_id=signal.id,
        )

        assert repeated.persisted is False
        assert (
            repeated.reason
            == "ALREADY_ACTIVE"
        )
        assert (
            repeated.signal.state
            is SignalState.ACTIVE
        )

        persisted = signal_repository.get_by_id(
            signal.id
        )

        assert persisted is not None
        assert (
            persisted.state
            is SignalState.ACTIVE
        )

        print(
            "SIGNAL OPERATIONAL TRANSITION: PASS"
        )

    finally:
        for path in (
            TEMP_DB,
            Path(str(TEMP_DB) + "-wal"),
            Path(str(TEMP_DB) + "-shm"),
        ):
            try:
                if path.exists():
                    path.unlink()
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
