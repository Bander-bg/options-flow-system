from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import weekly.db.signal_feature_repository as signal_feature_repo_module
from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import SignalState
from weekly.domain.models import SignalFeature
from weekly.services.signal_alert_service import (
    SignalAlertService,
)
from weekly.services.signal_operational_transition_service import (
    SignalOperationalTransitionService,
)

from test_trade_repository import (
    TEMP_DB,
    create_temp_database,
    make_signal,
    patch_repositories,
    temp_database_connection,
    temp_database_transaction,
)


def main() -> None:
    create_temp_database()
    patch_repositories()
    signal_feature_repo_module.database_connection = (
        temp_database_connection
    )
    signal_feature_repo_module.database_transaction = (
        temp_database_transaction
    )

    try:
        signal_repository = SignalRepository()
        feature_repository = SignalFeatureRepository()

        signal = signal_repository.create(
            make_signal()
        )

        assert signal.id is not None
        assert signal.state is SignalState.CONFIRMED

        feature = feature_repository.create(
            SignalFeature(
                signal_id=signal.id,
                evaluation_sequence=1,
                captured_at=signal.candidate_at,
                selected_contract_symbol=(
                    "AAPL260918C00200000"
                ),
                selected_contract_strike=200.0,
                final_score=82.0,
                final_grade="A",
                coverage_pct=0.90,
            )
        )

        transition_service = (
            SignalOperationalTransitionService(
                signal_repository=signal_repository,
            )
        )

        sent = []

        service = SignalAlertService(
            signal_repository=signal_repository,
            feature_repository=feature_repository,
            transition_service=transition_service,
            sender=sent.append,
        )

        result = service.send_and_activate(
            signal_id=signal.id,
        )

        assert result.sent is True
        assert (
            result.reason
            == "ALERT_SENT_AND_ACTIVATED"
        )
        assert len(sent) == 1
        assert sent[0].signal.id == signal.id
        assert sent[0].feature.id == feature.id
        assert result.transition is not None
        assert (
            result.transition.signal.state
            is SignalState.ACTIVE
        )

        persisted = signal_repository.get_by_id(
            signal.id
        )
        assert persisted is not None
        assert persisted.state is SignalState.ACTIVE

        repeated = service.send_and_activate(
            signal_id=signal.id,
        )
        assert repeated.sent is False
        assert repeated.reason == "ALREADY_ACTIVE"
        assert len(sent) == 1

        failing_signal = signal_repository.create(
            replace(
                make_signal(),
                candidate_sequence=2,
            )
        )
        assert failing_signal.id is not None

        feature_repository.create(
            SignalFeature(
                signal_id=failing_signal.id,
                evaluation_sequence=1,
                captured_at=failing_signal.candidate_at,
            )
        )

        def fail_sender(alert) -> None:
            raise RuntimeError("SEND_FAILED")

        failing_service = SignalAlertService(
            signal_repository=signal_repository,
            feature_repository=feature_repository,
            transition_service=transition_service,
            sender=fail_sender,
        )

        try:
            failing_service.send_and_activate(
                signal_id=failing_signal.id,
            )
        except RuntimeError as exc:
            assert str(exc) == "SEND_FAILED"
        else:
            raise AssertionError(
                "Expected sender failure."
            )

        still_confirmed = signal_repository.get_by_id(
            failing_signal.id
        )
        assert still_confirmed is not None
        assert (
            still_confirmed.state
            is SignalState.CONFIRMED
        )

        print("SIGNAL ALERT SERVICE: PASS")

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
