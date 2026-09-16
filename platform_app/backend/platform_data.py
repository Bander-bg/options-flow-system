from __future__ import annotations

from platform_app.backend.engine_reader import (
    load_engine_signals,
    load_engine_signal_detail,
    load_engine_positions,
    load_engine_trades,
    load_engine_outcomes,
    load_engine_data_health,
)
from platform_app.backend.engine_ui_mapper import (
    map_signal,
    map_signal_detail,
    map_position,
    map_trade,
    map_outcome,
    map_data_health,
)


def signals():
    rows = load_engine_signals()
    return [map_signal(row) for row in rows], "ENGINE"


def signal_detail(ticker: str):
    row = load_engine_signal_detail(ticker)
    if row is None:
        return None, "ENGINE"

    return map_signal_detail(row), "ENGINE"


def positions():
    rows = load_engine_positions()
    return [map_position(row) for row in rows], "ENGINE"


def trades():
    rows = load_engine_trades()
    return [map_trade(row) for row in rows], "ENGINE"


def outcomes():
    rows = load_engine_outcomes()
    return [map_outcome(row) for row in rows], "ENGINE"


def data_health():
    rows = load_engine_data_health()
    return [map_data_health(row) for row in rows], "ENGINE"
