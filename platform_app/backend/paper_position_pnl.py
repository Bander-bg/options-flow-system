from __future__ import annotations

import math
from typing import Any


CONTRACT_MULTIPLIER = 100


def calculate_long_option_pnl(
    *,
    entry_price: float,
    current_mark: float,
    quantity: int,
) -> dict[str, float | str]:
    """
    Calculate unrealized P/L for a long option position.

    Uses the option contract price itself:
        P/L % =
        ((current_mark - entry_price) / entry_price) * 100

        P/L $ =
        (current_mark - entry_price)
        * 100
        * quantity
    """

    entry = float(entry_price)
    mark = float(current_mark)
    qty = int(quantity)

    if (
        not math.isfinite(entry)
        or entry <= 0
    ):
        raise ValueError(
            "entry_price must be a positive finite number."
        )

    if (
        not math.isfinite(mark)
        or mark < 0
    ):
        raise ValueError(
            "current_mark must be a non-negative finite number."
        )

    if qty <= 0:
        raise ValueError(
            "quantity must be greater than zero."
        )

    price_change = mark - entry

    pnl_percent = (
        price_change
        / entry
        * 100.0
    )

    pnl_dollars = (
        price_change
        * CONTRACT_MULTIPLIER
        * qty
    )

    if pnl_percent > 0:
        pnl_state = "PROFIT"
    elif pnl_percent < 0:
        pnl_state = "LOSS"
    else:
        pnl_state = "FLAT"

    return {
        "entry_price": entry,
        "current_mark": mark,
        "pnl_percent": pnl_percent,
        "pnl_dollars": pnl_dollars,
        "pnl_state": pnl_state,
    }


def enrich_position_with_live_pnl(
    position: dict[str, Any],
    *,
    options_provider,
) -> dict[str, Any]:
    """
    Add live option-contract quote and unrealized P/L fields
    to one Paper position.

    Failure to obtain a quote does NOT break the page.
    """

    enriched = dict(position)

    enriched.update(
        {
            "current_bid": None,
            "current_ask": None,
            "current_mark": None,
            "pnl_percent": None,
            "pnl_dollars": None,
            "pnl_state": "UNAVAILABLE",
            "pnl_quote_status": "UNAVAILABLE",
        }
    )

    entry_price = position.get(
        "entry_price"
    )

    if entry_price is None:
        enriched[
            "pnl_quote_status"
        ] = "ENTRY_NOT_FILLED"
        return enriched

    ticker = position.get(
        "ticker"
    )
    expiry = position.get(
        "expiry"
    )
    contract_symbol = position.get(
        "contract_symbol"
    )
    quantity = position.get(
        "quantity"
    )

    if (
        not ticker
        or not expiry
        or not contract_symbol
        or quantity is None
    ):
        enriched[
            "pnl_quote_status"
        ] = "POSITION_DATA_INCOMPLETE"
        return enriched

    try:
        quote_result = (
            options_provider
            .get_contract_candidates(
                ticker=str(ticker),
                target_expiry=expiry,
            )
        )

        contract = next(
            (
                candidate
                for candidate
                in quote_result.candidates
                if candidate.symbol
                == contract_symbol
            ),
            None,
        )

        if contract is None:
            enriched[
                "pnl_quote_status"
            ] = "CONTRACT_NOT_FOUND"
            return enriched

        if (
            contract.bid is None
            or contract.ask is None
        ):
            enriched[
                "pnl_quote_status"
            ] = "QUOTE_UNAVAILABLE"
            return enriched

        bid = float(
            contract.bid
        )
        ask = float(
            contract.ask
        )

        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid < 0
            or ask < 0
            or ask < bid
        ):
            enriched[
                "pnl_quote_status"
            ] = "QUOTE_INVALID"
            return enriched

        mark = (
            bid + ask
        ) / 2.0

        pnl = calculate_long_option_pnl(
            entry_price=float(
                entry_price
            ),
            current_mark=mark,
            quantity=int(
                quantity
            ),
        )

        enriched.update(
            {
                "current_bid": bid,
                "current_ask": ask,
                "current_mark": mark,
                "pnl_percent": pnl[
                    "pnl_percent"
                ],
                "pnl_dollars": pnl[
                    "pnl_dollars"
                ],
                "pnl_state": pnl[
                    "pnl_state"
                ],
                "pnl_quote_status": "LIVE",
                "pnl_quote_provider": getattr(
                    quote_result,
                    "provider",
                    None,
                ),
                "pnl_quote_feed": getattr(
                    quote_result,
                    "feed",
                    None,
                ),
            }
        )

    except Exception:
        enriched[
            "pnl_quote_status"
        ] = "PROVIDER_UNAVAILABLE"

    return enriched
