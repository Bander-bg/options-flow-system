from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from weekly.domain.enums import TradeIntent, TradeStatus
from weekly.services.paper_execution_recovery_service import (
    PaperExecutionRecoveryService,
)


@dataclass
class FakeTrade:
    id: int
    status: TradeStatus
    intent: TradeIntent


class FakeTradeRepository:
    def __init__(self):
        self.trades = [
            FakeTrade(
                id=1,
                status=TradeStatus.REQUESTED,
                intent=TradeIntent.OPEN,
            ),
            FakeTrade(
                id=2,
                status=TradeStatus.PARTIALLY_FILLED,
                intent=TradeIntent.CLOSE,
            ),
            FakeTrade(
                id=3,
                status=TradeStatus.FILLED,
                intent=TradeIntent.OPEN,
            ),
            FakeTrade(
                id=4,
                status=TradeStatus.FILLED,
                intent=TradeIntent.CLOSE,
            ),
        ]

    def list_execution_recovery_candidates(self):
        return list(self.trades)


class FakeLifecycleService:
    def __init__(self):
        self.calls = []

    def sync(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(trade_id)

        return SimpleNamespace(
            trade_id=trade_id,
            reason="FAKE_LIFECYCLE",
        )


class FakeFillService:
    def __init__(self):
        self.calls = []

    def apply_open_fill(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(("OPEN", trade_id))

        return SimpleNamespace(
            trade_id=trade_id,
            reason="FAKE_OPEN_FILL",
        )

    def apply_close_fill(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(("CLOSE", trade_id))

        return SimpleNamespace(
            trade_id=trade_id,
            reason="FAKE_CLOSE_FILL",
        )


def main() -> None:
    trade_repository = FakeTradeRepository()
    lifecycle_service = FakeLifecycleService()
    fill_service = FakeFillService()

    service = PaperExecutionRecoveryService(
        trade_repository=trade_repository,
        lifecycle_service=lifecycle_service,
        fill_service=fill_service,
    )

    result = service.recover()

    assert lifecycle_service.calls == [1, 2]
    assert fill_service.calls == [("OPEN", 3), ("CLOSE", 4)]

    assert tuple(
        item.trade_id
        for item in result.items
    ) == (
        1,
        2,
        3,
        4,
    )

    assert result.items[0].reason == (
        "BROKER_ORDER_RECONCILED"
    )

    assert result.items[1].reason == (
        "BROKER_ORDER_RECONCILED"
    )

    assert result.items[2].reason == (
        "LOCAL_FILLED_POSITION_ENTRY_RECOVERED"
    )

    assert result.items[3].reason == (
        "LOCAL_FILLED_POSITION_EXIT_RECOVERED"
    )

    assert (
        result.items[0].lifecycle_result
        is not None
    )
    assert (
        result.items[1].lifecycle_result
        is not None
    )
    assert (
        result.items[2].lifecycle_result
        is None
    )
    assert (
        result.items[3].lifecycle_result
        is None
    )

    assert (
        result.items[0].fill_result
        is None
    )
    assert (
        result.items[1].fill_result
        is None
    )
    assert (
        result.items[2].fill_result
        is not None
    )
    assert (
        result.items[3].fill_result
        is not None
    )

    print(
        "PAPER EXECUTION RECOVERY SERVICE: PASS"
    )


if __name__ == "__main__":
    main()
