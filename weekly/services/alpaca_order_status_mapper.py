from __future__ import annotations

from alpaca.trading.enums import OrderStatus

from weekly.domain.enums import TradeStatus


REQUESTED_ORDER_STATUSES = frozenset(
    {
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
    }
)

CANCELLED_ORDER_STATUSES = frozenset(
    {
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.DONE_FOR_DAY,
    }
)

REJECTED_ORDER_STATUSES = frozenset(
    {
        OrderStatus.REJECTED,
        OrderStatus.STOPPED,
        OrderStatus.SUSPENDED,
    }
)


def map_alpaca_order_status(
    status: OrderStatus,
) -> TradeStatus:
    if status == OrderStatus.FILLED:
        return TradeStatus.FILLED

    if status == OrderStatus.PARTIALLY_FILLED:
        return TradeStatus.PARTIALLY_FILLED

    if status in CANCELLED_ORDER_STATUSES:
        return TradeStatus.CANCELLED

    if status in REJECTED_ORDER_STATUSES:
        return TradeStatus.REJECTED

    if status in REQUESTED_ORDER_STATUSES:
        return TradeStatus.REQUESTED

    raise ValueError(
        f"Unsupported Alpaca order status: {status!r}"
    )
