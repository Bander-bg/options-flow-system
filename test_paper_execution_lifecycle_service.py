from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from weekly.domain.enums import (
    ExecutionMode,
    OptionRight,
    PositionStatus,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import Position, Trade
from weekly.services.paper_execution_fill_service import (
    PaperExecutionFillResult,
)
from weekly.services.paper_execution_lifecycle_service import (
    PaperExecutionLifecycleService,
)


ET = ZoneInfo("America/New_York")


def make_trade(
    *,
    status: TradeStatus,
    intent: TradeIntent = TradeIntent.OPEN,
) -> Trade:
    return Trade(
        id=10,
        position_id=20,
        signal_id=30,
        intent=intent,
        side=(
            TradeSide.BUY
            if intent is TradeIntent.OPEN
            else TradeSide.SELL
        ),
        quantity=1,
        requested_at=datetime(
            2026,
            9,
            4,
            10,
            20,
            tzinfo=ET,
        ),
        status=status,
        execution_mode=ExecutionMode.PAPER,
        filled_at=(
            datetime(
                2026,
                9,
                4,
                10,
                22,
                tzinfo=ET,
            )
            if status is TradeStatus.FILLED
            else None
        ),
        fill_price=(
            5.00
            if status is TradeStatus.FILLED
            else None
        ),
        bid_at_action=4.80,
        ask_at_action=5.00,
        mark_at_action=4.90,
        broker_order_id="paper-001",
    )


def make_position() -> Position:
    return Position(
        id=20,
        signal_id=30,
        contract_symbol="AAPL260911C00320000",
        option_right=OptionRight.CALL,
        strike=320.0,
        expiry=date(
            2026,
            9,
            11,
        ),
        quantity=1,
        status=PositionStatus.OPEN,
        execution_mode=ExecutionMode.PAPER,
        opened_at=datetime(
            2026,
            9,
            4,
            10,
            22,
            tzinfo=ET,
        ),
        entry_price=5.00,
        entry_bid=4.80,
        entry_ask=5.00,
        entry_mark=4.90,
    )


class FakeOrderSyncService:
    def __init__(
        self,
        trade: Trade,
    ):
        self.trade = trade
        self.calls = []

    def sync_trade(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(trade_id)

        return SimpleNamespace(
            trade=self.trade,
            alpaca_order_status="FAKE",
        )


class FakeFillService:
    def __init__(
        self,
        *,
        trade: Trade,
        position: Position,
    ):
        self.trade = trade
        self.position = position
        self.calls = []

    def apply_open_fill(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(("OPEN", trade_id))

        return PaperExecutionFillResult(
            trade=self.trade,
            position=self.position,
            persisted=True,
            reason="OPEN_FILL_APPLIED",
        )

    def apply_close_fill(
        self,
        *,
        trade_id: int,
    ):
        self.calls.append(("CLOSE", trade_id))

        return PaperExecutionFillResult(
            trade=self.trade,
            position=self.position,
            persisted=True,
            reason="CLOSE_FILL_APPLIED",
        )


def main() -> None:
    filled_trade = make_trade(
        status=TradeStatus.FILLED,
    )

    position = make_position()

    filled_sync = FakeOrderSyncService(
        filled_trade
    )

    filled_apply = FakeFillService(
        trade=filled_trade,
        position=position,
    )

    service = PaperExecutionLifecycleService(
        order_sync_service=filled_sync,
        fill_service=filled_apply,
    )

    result = service.sync(
        trade_id=10,
    )

    assert filled_sync.calls == [10]
    assert filled_apply.calls == [("OPEN", 10)]

    assert result.trade.status is TradeStatus.FILLED
    assert result.position is position
    assert result.fill_result is not None
    assert result.reason == "OPEN_FILL_APPLIED"

    requested_trade = make_trade(
        status=TradeStatus.REQUESTED,
    )

    requested_sync = FakeOrderSyncService(
        requested_trade
    )

    requested_fill = FakeFillService(
        trade=requested_trade,
        position=position,
    )

    service = PaperExecutionLifecycleService(
        order_sync_service=requested_sync,
        fill_service=requested_fill,
    )

    result = service.sync(
        trade_id=10,
    )

    assert requested_sync.calls == [10]
    assert requested_fill.calls == []

    assert (
        result.trade.status
        is TradeStatus.REQUESTED
    )
    assert result.position is None
    assert result.fill_result is None
    assert (
        result.reason
        == "NO_OPEN_FILL_TO_APPLY"
    )

    close_trade = make_trade(
        status=TradeStatus.FILLED,
        intent=TradeIntent.CLOSE,
    )

    close_sync = FakeOrderSyncService(
        close_trade
    )

    close_apply = FakeFillService(
        trade=close_trade,
        position=position,
    )

    service = PaperExecutionLifecycleService(
        order_sync_service=close_sync,
        fill_service=close_apply,
    )

    result = service.sync(
        trade_id=10,
    )

    assert close_sync.calls == [10]
    assert close_apply.calls == [("CLOSE", 10)]
    assert result.trade.intent is TradeIntent.CLOSE
    assert result.trade.status is TradeStatus.FILLED
    assert result.position is position
    assert result.fill_result is not None
    assert result.reason == "CLOSE_FILL_APPLIED"

    print(
        "PAPER EXECUTION LIFECYCLE SERVICE: PASS"
    )


if __name__ == "__main__":
    main()
