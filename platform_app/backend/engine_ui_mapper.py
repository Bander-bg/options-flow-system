from __future__ import annotations


def _enum_text(value):
    return value.value if hasattr(value, "value") else value


def _contract_amount(ask):
    if ask is None:
        return None
    return round(float(ask) * 100, 2)


def map_signal(row: dict) -> dict:
    net_flow = (
        row.get("net_flow_at_confirmation")
        if row.get("net_flow_at_confirmation") is not None
        else row.get("net_flow_at_candidate")
    )

    return {
        "signal_id": row.get("id"),
        "ticker": row.get("ticker"),
        "state": _enum_text(row.get("state")),
        "direction": _enum_text(row.get("direction")),
        "quality_grade": row.get("final_grade") or "UNRATED",
        "quality_score": row.get("final_score"),
        "net_flow": net_flow,
        "target_expiry": row.get("target_expiry"),
        "contract_right": row.get("selected_contract_right"),
        "strike": row.get("selected_contract_strike"),
        "contract_amount": _contract_amount(
            row.get("selected_contract_ask")
        ),
    }


def map_signal_detail(row: dict) -> dict:
    net_flow = (
        row.get("net_flow_at_confirmation")
        if row.get("net_flow_at_confirmation") is not None
        else row.get("net_flow_at_candidate")
    )

    bullish = row.get("bullish_premium")
    bearish = row.get("bearish_premium")

    strength = None
    if bullish is not None and bearish is not None:
        total = float(bullish) + float(bearish)
        if total:
            strength = (
                float(bullish) - float(bearish)
            ) / total

    ask = row.get("selected_contract_ask")

    return {
        "ticker": row.get("ticker"),
        "direction": _enum_text(row.get("direction")),
        "state": _enum_text(row.get("state")),
        "quality_grade": row.get("final_grade") or "UNRATED",
        "quality_score": row.get("final_score"),
        "net_flow": net_flow,
        "target_expiry": row.get("target_expiry"),

        "flow": {
            "call_ask_premium": row.get("call_ask_premium"),
            "put_ask_premium": row.get("put_ask_premium"),
            "bullish_premium": bullish,
            "bearish_premium": bearish,
            "strength": strength,
        },

        "price_action": {
            "structure": row.get("structure_status") or "UNKNOWN",
            "impulse": row.get("impulse_status") or "UNKNOWN",
            "participation": row.get("participation_status") or "UNKNOWN",
            "final": row.get("price_action_status") or "UNKNOWN",
        },

        "market_regime": {
            "weekly_vwap": row.get("vwap_status") or "UNKNOWN",
            "efficiency_ratio": (
                row.get("efficiency_ratio_status")
                or "UNKNOWN"
            ),
            "atr": (
                "PASS"
                if row.get("atr_1h") is not None
                else "UNKNOWN"
            ),
        },

        "contract": {
            "symbol": row.get("selected_contract_symbol"),
            "right": row.get("selected_contract_right"),
            "strike": row.get("selected_contract_strike"),
            "delta": row.get("selected_contract_delta"),
            "spread_pct": row.get(
                "selected_contract_spread_pct"
            ),
            "estimated_cost": _contract_amount(ask),
        },
    }


def map_position(row: dict) -> dict:
    current_price = None

    if row.get("status") not in ("OPEN", "ACTIVE"):
        current_price = row.get("exit_price")

    return {
        "position_id": row.get("id"),
        "ticker": row.get("ticker"),
        "contract_symbol": row.get("contract_symbol"),
        "direction": _enum_text(row.get("direction")),
        "quantity": row.get("quantity"),
        "entry_price": row.get("entry_price"),
        "current_price": current_price,
        "status": row.get("status"),
        "opened_at": row.get("opened_at"),
    }


def map_trade(row: dict) -> dict:
    return {
        "trade_id": row.get("id"),
        "position_id": row.get("position_id"),
        "ticker": row.get("ticker"),
        "contract_symbol": row.get("contract_symbol"),
        "intent": row.get("intent"),
        "side": row.get("side"),
        "quantity": row.get("quantity"),
        "status": row.get("status"),
        "fill_price": row.get("fill_price"),
        "requested_at": row.get("requested_at"),
        "filled_at": row.get("filled_at"),
        "mode": row.get("execution_mode"),
    }


def map_outcome(row: dict) -> dict:
    def pct(value):
        if value is None:
            return None
        return float(value) * 100

    return {
        "ticker": row.get("ticker"),
        "scope": row.get("outcome_scope"),
        "checkpoint": row.get("checkpoint_name"),
        "underlying_return_pct": pct(
            row.get("underlying_raw_return")
        ),
        "directional_return_pct": pct(
            row.get("underlying_directional_return")
        ),
        "option_executable_return_pct": pct(
            row.get("option_executable_return")
        ),
        "option_mark_return_pct": pct(
            row.get("option_mark_return")
        ),
        "status": row.get("outcome_status"),
    }


def map_data_health(row: dict) -> dict:
    return {
        "component": row.get("component"),
        "status": row.get("status"),
        "provider": row.get("provider"),
        "feed": row.get("feed"),
        "message": row.get("message"),
    }
