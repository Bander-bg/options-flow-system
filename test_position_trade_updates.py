from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from weekly.db.position_repository import (
    PositionRepository,
)
from weekly.db.signal_repository import (
    SignalRepository,
)
from weekly.db.trade_repository import (
    TradeRepository,
)
from weekly.domain.enums import (
    ExecutionMode,
    PositionStatus,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.domain.models import Trade

from test_trade_repository import (
    ET,
    TEMP_DB,
    create_temp_database,
    make_position,
    make_signal,
    patch_repositories,
)


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        signal_repository = SignalRepository()
        position_repository = PositionRepository()
        trade_repository = TradeRepository()

        signal = signal_repository.create(
            make_signal()
        )

        assert signal.id is not None

        pending_position = replace(
            make_position(signal.id),
            opened_at=None,
            entry_price=None,
            entry_bid=None,
            entry_ask=None,
            entry_mark=None,
        )

        position = position_repository.create(
            pending_position
        )

        assert position.id is not None
        assert position.status == PositionStatus.OPEN

        requested_trade = trade_repository.create(
            Trade(
                position_id=position.id,
                signal_id=signal.id,
                execution_mode=ExecutionMode.PAPER,
                intent=TradeIntent.OPEN,
                side=TradeSide.BUY,
                quantity=1,
                requested_at=datetime(
                    2026,
                    9,
                    4,
                    10,
                    21,
                    tzinfo=ET,
                ),
                bid_at_action=4.80,
                ask_at_action=5.00,
                mark_at_action=4.90,
                options_data_provider="ALPACA",
                options_data_feed="INDICATIVE",
                status=TradeStatus.REQUESTED,
            )
        )

        assert requested_trade.id is not None

        filled_at = datetime(
            2026,
            9,
            4,
            10,
            21,
            30,
            tzinfo=ET,
        )

        filled_trade = trade_repository.update_status(
            trade_id=requested_trade.id,
            new_status=TradeStatus.FILLED,
            expected_status=TradeStatus.REQUESTED,
            broker_order_id="paper-order-001",
            filled_at=filled_at,
            fill_price=5.00,
        )

        assert (
            filled_trade.status
            == TradeStatus.FILLED
        )
        assert (
            filled_trade.broker_order_id
            == "paper-order-001"
        )
        assert filled_trade.fill_price == 5.00
        assert filled_trade.filled_at is not None

        entered_position = (
            position_repository.update_entry(
                position_id=position.id,
                opened_at=filled_at,
                entry_price=5.00,
                entry_bid=4.80,
                entry_ask=5.00,
                entry_mark=4.90,
            )
        )

        assert entered_position.opened_at == filled_at
        assert entered_position.entry_price == 5.00
        assert entered_position.entry_bid == 4.80
        assert entered_position.entry_ask == 5.00
        assert entered_position.entry_mark == 4.90

        try:
            position_repository.update_entry(
                position_id=position.id,
                opened_at=filled_at,
                entry_price=5.00,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                "Position entry duplicate guard failed."
            )

        closed_position = (
            position_repository.update_status(
                position_id=position.id,
                new_status=PositionStatus.CLOSED,
                expected_status=PositionStatus.OPEN,
                closed_at=datetime(
                    2026,
                    9,
                    4,
                    11,
                    0,
                    tzinfo=ET,
                ),
                exit_price=5.50,
                exit_bid=5.40,
                exit_ask=5.60,
                exit_mark=5.50,
            )
        )

        assert (
            closed_position.status
            == PositionStatus.CLOSED
        )
        assert closed_position.closed_at is not None
        assert closed_position.exit_price == 5.50
        assert closed_position.exit_bid == 5.40
        assert closed_position.exit_ask == 5.60
        assert closed_position.exit_mark == 5.50

        try:
            position_repository.update_status(
                position_id=position.id,
                new_status=PositionStatus.CANCELLED,
                expected_status=PositionStatus.OPEN,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                "Position expected_status guard failed."
            )

        try:
            trade_repository.update_status(
                trade_id=requested_trade.id,
                new_status=TradeStatus.CANCELLED,
                expected_status=TradeStatus.REQUESTED,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                "Trade expected_status guard failed."
            )

        print(
            "POSITION + TRADE UPDATE STATUS: PASS"
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
