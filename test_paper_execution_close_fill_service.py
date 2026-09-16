from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import (
    PositionStatus,
    TradeIntent,
    TradeSide,
    TradeStatus,
)
from weekly.services.paper_execution_fill_service import (
    PaperExecutionFillService,
)

from test_trade_repository import (
    TEMP_DB,
    create_temp_database,
    make_position,
    make_signal,
    make_trade,
    patch_repositories,
)


ET = ZoneInfo("America/New_York")


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

        opened_at = datetime(
            2026, 9, 4, 10, 0,
            tzinfo=ET,
        )

        position = position_repository.create(
            replace(
                make_position(signal.id),
                status=PositionStatus.OPEN,
                opened_at=opened_at,
                entry_price=5.00,
                entry_bid=4.80,
                entry_ask=5.00,
                entry_mark=4.90,
            )
        )

        assert position.id is not None

        close_trade = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.CLOSE,
                    side=TradeSide.SELL,
                    broker_order_id=None,
                    minute=45,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        assert close_trade.id is not None

        filled_at = datetime(
            2026, 9, 4, 11, 0,
            tzinfo=ET,
        )

        filled_trade = trade_repository.update_status(
            trade_id=close_trade.id,
            new_status=TradeStatus.FILLED,
            expected_status=TradeStatus.REQUESTED,
            broker_order_id="paper-close-fill-001",
            filled_at=filled_at,
            fill_price=5.50,
        )

        assert filled_trade.status is TradeStatus.FILLED

        service = PaperExecutionFillService(
            trade_repository=trade_repository,
            position_repository=position_repository,
        )

        result = service.apply_close_fill(
            trade_id=close_trade.id,
        )

        assert result.persisted is True
        assert result.reason == "CLOSE_FILL_APPLIED"

        assert (
            result.position.status
            is PositionStatus.CLOSED
        )
        assert result.position.closed_at == filled_at
        assert result.position.exit_price == 5.50
        assert result.position.exit_bid == 4.80
        assert result.position.exit_ask == 5.00
        assert result.position.exit_mark == 4.90

        repeated = service.apply_close_fill(
            trade_id=close_trade.id,
        )

        assert repeated.persisted is False
        assert (
            repeated.reason
            == "POSITION_EXIT_ALREADY_RECORDED"
        )

        persisted_position = (
            position_repository.get_by_id(
                position.id
            )
        )

        assert persisted_position is not None
        assert (
            persisted_position.status
            is PositionStatus.CLOSED
        )
        assert (
            persisted_position.closed_at
            == filled_at
        )
        assert persisted_position.exit_price == 5.50

        print(
            "PAPER EXECUTION CLOSE FILL SERVICE: PASS"
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
