from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from weekly.providers.weekly_provider_factory import WeeklyProviders
from weekly.providers.alpaca_options_provider import (
    AlpacaOptionsProviderError,
)
from weekly.services.market_context_service import MarketContextService
from weekly.services.weekly_runtime_cycle import WeeklyRuntimeCycle
from weekly.services.weekly_runtime_factory import build_weekly_runtime_services

from test_weekly_runtime_cycle import (
    ET,
    TEMP_DB,
    FakeOptionsProvider,
    FakeStockProvider,
    FakeTradingClient,
    FakeUWProvider,
    create_temp_database,
    patch_repositories,
)


class UnavailableOptionsProvider(FakeOptionsProvider):
    def get_contract_candidates(
        self,
        *,
        ticker,
        target_expiry,
    ):
        raise AlpacaOptionsProviderError(
            "Synthetic options data unavailable."
        )


class LateFakeTradingClient(FakeTradingClient):
    def get_clock(self):
        base = super().get_clock()

        return SimpleNamespace(
            timestamp=datetime(
                2026, 9, 11, 13, 0,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=base.next_open,
            next_close=base.next_close,
        )


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        trading_client = LateFakeTradingClient()

        providers = WeeklyProviders(
            stock=FakeStockProvider(),
            options=UnavailableOptionsProvider(),
            unusual_whales=FakeUWProvider(),
            trading_client=trading_client,
        )

        cycle = WeeklyRuntimeCycle(
            services=services,
            providers=providers,
            market_context_service=(
                MarketContextService(
                    trading_client=trading_client
                )
            ),
        )

        result = cycle.run()

        assert result.reason == "CYCLE_COMPLETED"
        assert len(result.ticker_results) == 5

        for ticker_result in result.ticker_results:
            assert (
                len(ticker_result.resolution_results)
                == 1
            )

            resolution = (
                ticker_result.resolution_results[0]
            )

            assert (
                resolution.hard_gate_result.status.value
                == "UNKNOWN"
            )

            assert (
                resolution
                .transition
                .resolution
                .target_state
                .value
                == "DATA_UNRESOLVED"
            )

            assert (
                resolution
                .transition
                .resolution
                .reason
                == (
                    "RESOLUTION_WINDOW_CLOSED_"
                    "WITH_UNKNOWN_DATA"
                )
            )

            assert (
                resolution.transition.persisted
                is True
            )

            assert (
                resolution.transition.signal.state.value
                == "DATA_UNRESOLVED"
            )

        print(
            "WEEKLY RUNTIME DATA_UNRESOLVED: "
            "PASS 5/5"
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
