from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from weekly.db.position_repository import PositionRepository
from weekly.db.signal_repository import SignalRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import TradeIntent, TradeSide, TradeStatus
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

        from dataclasses import replace

        position = position_repository.create(
            replace(
                make_position(signal.id),
                opened_at=None,
                entry_price=None,
                entry_bid=None,
                entry_ask=None,
                entry_mark=None,
            )
        )

        assert position.id is not None
        assert position.opened_at is None

        trade = trade_repository.create(
            replace(
                make_trade(
                    position_id=position.id,
                    signal_id=signal.id,
                    intent=TradeIntent.OPEN,
                    side=TradeSide.BUY,
                    broker_order_id=None,
                    minute=21,
                ),
                status=TradeStatus.REQUESTED,
                filled_at=None,
                fill_price=None,
            )
        )

        assert trade.id is not None

        filled_at = datetime(
            2026,
            9,
            4,
            10,
            22,
            tzinfo=ET,
        )

        filled_trade = trade_repository.update_status(
            trade_id=trade.id,
            new_status=TradeStatus.FILLED,
            expected_status=TradeStatus.REQUESTED,
            broker_order_id="paper-fill-001",
            filled_at=filled_at,
            fill_price=5.00,
        )

        assert filled_trade.status is TradeStatus.FILLED

        service = PaperExecutionFillService(
            trade_repository=trade_repository,
            position_repository=position_repository,
        )

        result = service.apply_open_fill(
            trade_id=trade.id,
        )

        assert result.persisted is True
        assert result.reason == "OPEN_FILL_APPLIED"
        assert result.position.opened_at == filled_at
        assert result.position.entry_price == 5.00
        assert result.position.entry_bid == 4.80
        assert result.position.entry_ask == 5.00
        assert result.position.entry_mark == 4.90

        repeated = service.apply_open_fill(
            trade_id=trade.id,
        )

        assert repeated.persisted is False
        assert (
            repeated.reason
            == "POSITION_ENTRY_ALREADY_RECORDED"
        )

        persisted_position = (
            position_repository.get_by_id(
                position.id
            )
        )

        assert persisted_position is not None
        assert persisted_position.opened_at == filled_at
        assert persisted_position.entry_price == 5.00

        print(
            "PAPER EXECUTION FILL SERVICE: PASS"
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
