from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from weekly.domain.enums import SignalState, TradeIntent
from weekly.services.paper_execution_coordinator import (
    PaperExecutionCoordinator,
)

from test_trade_repository import make_signal


class FakeSelector:
    def __init__(self, signals):
        self.signals = signals
        self.calls = 0

    def select(self, *, cycle_result):
        self.calls += 1
        return SimpleNamespace(
            signals=tuple(self.signals),
        )


class FakeRecoveryService:
    def __init__(self):
        self.calls = 0

    def recover(self):
        self.calls += 1
        return SimpleNamespace(
            items=(),
        )


class FakePositionRepository:
    def __init__(self):
        self.open_signal_ids = {20}

    def get_open_for_signal(self, signal_id):
        if signal_id in self.open_signal_ids:
            return SimpleNamespace(
                id=200,
                signal_id=signal_id,
            )
        return None


class FakeTradeRepository:
    def list_for_signal(self, signal_id):
        if signal_id == 30:
            return [
                SimpleNamespace(
                    intent=TradeIntent.OPEN,
                )
            ]
        return []


def main() -> None:
    awaiting = replace(
        make_signal(),
        id=10,
        state=SignalState.CONFIRMED,
    )

    existing_position = replace(
        make_signal(),
        id=20,
        state=SignalState.CONFIRMED,
        candidate_sequence=2,
    )

    existing_history = replace(
        make_signal(),
        id=30,
        state=SignalState.CONFIRMED,
        candidate_sequence=3,
    )

    selector = FakeSelector(
        (
            awaiting,
            existing_position,
            existing_history,
        )
    )

    recovery_service = FakeRecoveryService()

    coordinator = PaperExecutionCoordinator(
        signal_selector=selector,
        recovery_service=recovery_service,
        position_repository=FakePositionRepository(),
        trade_repository=FakeTradeRepository(),
    )

    result = coordinator.coordinate(
        cycle_result=SimpleNamespace(),
    )

    assert recovery_service.calls == 1
    assert selector.calls == 1

    assert tuple(
        item.signal.id
        for item in result.signals
    ) == (
        10,
        20,
        30,
    )

    assert tuple(
        item.reason
        for item in result.signals
    ) == (
        "AWAITING_MANUAL_ENTRY",
        "EXISTING_OPEN_POSITION",
        "EXISTING_EXECUTION_HISTORY",
    )

    print(
        "PAPER EXECUTION COORDINATOR: PASS"
    )


if __name__ == "__main__":
    main()
