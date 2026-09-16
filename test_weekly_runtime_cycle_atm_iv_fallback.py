from __future__ import annotations

from datetime import date
from pathlib import Path

from weekly.providers.weekly_provider_factory import WeeklyProviders
from weekly.services.market_context_service import MarketContextService
from weekly.services.weekly_runtime_cycle import WeeklyRuntimeCycle
from weekly.services.weekly_runtime_factory import build_weekly_runtime_services

from test_weekly_runtime_cycle import (
    TEMP_DB,
    FakeOptionsProvider,
    FakeStockProvider,
    FakeTradingClient,
    FakeUWProvider,
    create_temp_database,
    patch_repositories,
)


class FakeUWFallbackProvider(FakeUWProvider):
    def fetch_volatility_term_structure(
        self,
        *,
        ticker,
    ):
        # Deliberately no exact 2026-09-18 row.
        return [
            {
                "expiry": "2026-09-25",
                "implied_move": 10.0,
                "volatility": 0.35,
                "implied_move_perc": 0.05,
            }
        ]


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        trading_client = FakeTradingClient()
        options_provider = FakeOptionsProvider()

        providers = WeeklyProviders(
            stock=FakeStockProvider(),
            options=options_provider,
            unusual_whales=FakeUWFallbackProvider(),
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
                ticker_result.target_expiry
                == date(2026, 9, 18)
            )

            assert (
                len(
                    ticker_result
                    .expected_move_evaluations
                )
                == 1
            )

            evaluation = (
                ticker_result
                .expected_move_evaluations[0]
            )

            assert (
                evaluation.result.source
                == "ATM_IV_FALLBACK"
            )

            assert (
                evaluation.result.atm_iv
                == 0.45
            )

            assert (
                evaluation.result.expected_move
                is not None
            )

            assert (
                ticker_result.option_candidates_result
                is not None
            )

            assert (
                ticker_result
                .option_candidates_result.provider
                == "ALPACA"
            )

            assert (
                ticker_result
                .option_candidates_result.feed
                == "indicative"
            )

        assert (
            options_provider.contract_candidate_calls
            == 5
        )

        print(
            "WEEKLY RUNTIME ATM IV FALLBACK: "
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
