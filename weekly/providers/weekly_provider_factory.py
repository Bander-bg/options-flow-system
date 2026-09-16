from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

from config import load_weekly_config

from weekly.providers.alpaca_options_provider import (
    AlpacaOptionsProvider,
)
from weekly.providers.alpaca_stock_provider import (
    AlpacaStockProvider,
)
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesProvider,
)


@dataclass(frozen=True)
class WeeklyProviders:
    stock: AlpacaStockProvider
    options: AlpacaOptionsProvider
    unusual_whales: UnusualWhalesProvider
    trading_client: TradingClient


def build_weekly_providers() -> WeeklyProviders:
    """
    Build external-data providers for weekly_v1.

    No external API request is made during construction.

    The TradingClient owned by AlpacaOptionsProvider is
    reused for:
    - Alpaca market clock
    - Alpaca trading calendar
    - option contract metadata
    """
    load_dotenv()

    config = load_weekly_config(
        require_runtime_ready=True
    )

    market = config["market"]

    options = AlpacaOptionsProvider(
        preferred_feed=market[
            "option_data_feed_preferred"
        ]
    )

    stock = AlpacaStockProvider(
        preferred_feed=market[
            "stock_data_feed_preferred"
        ]
    )

    unusual_whales = (
        UnusualWhalesProvider()
    )

    return WeeklyProviders(
        stock=stock,
        options=options,
        unusual_whales=unusual_whales,
        trading_client=(
            options.trading_client
        ),
    )
