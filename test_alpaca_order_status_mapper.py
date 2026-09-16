from __future__ import annotations

from alpaca.trading.enums import OrderStatus

from weekly.domain.enums import TradeStatus
from weekly.services.alpaca_order_status_mapper import (
    map_alpaca_order_status,
)


def main() -> None:
    requested_statuses = (
        OrderStatus.NEW,
        OrderStatus.ACCEPTED,
        OrderStatus.PENDING_NEW,
        OrderStatus.PENDING_REVIEW,
        OrderStatus.ACCEPTED_FOR_BIDDING,
        OrderStatus.PENDING_CANCEL,
        OrderStatus.PENDING_REPLACE,
        OrderStatus.REPLACED,
        OrderStatus.HELD,
        OrderStatus.CALCULATED,
    )

    for status in requested_statuses:
        assert (
            map_alpaca_order_status(status)
            == TradeStatus.REQUESTED
        )

    assert (
        map_alpaca_order_status(
            OrderStatus.FILLED
        )
        == TradeStatus.FILLED
    )

    assert (
        map_alpaca_order_status(
            OrderStatus.PARTIALLY_FILLED
        )
        == TradeStatus.PARTIALLY_FILLED
    )

    for status in (
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.DONE_FOR_DAY,
    ):
        assert (
            map_alpaca_order_status(status)
            == TradeStatus.CANCELLED
        )

    for status in (
        OrderStatus.REJECTED,
        OrderStatus.STOPPED,
        OrderStatus.SUSPENDED,
    ):
        assert (
            map_alpaca_order_status(status)
            == TradeStatus.REJECTED
        )

    print(
        "ALPACA ORDER STATUS MAPPER: PASS"
    )


if __name__ == "__main__":
    main()
