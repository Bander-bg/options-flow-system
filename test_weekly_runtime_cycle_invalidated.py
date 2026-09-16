from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from weekly.providers.weekly_provider_factory import WeeklyProviders
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


class SecondCycleTradingClient(FakeTradingClient):
    def get_clock(self):
        base = super().get_clock()

        return SimpleNamespace(
            timestamp=datetime(
                2026, 9, 11, 12, 20,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=base.next_open,
            next_close=base.next_close,
        )


class ReversedFakeUWProvider(FakeUWProvider):
    def fetch_session_to_date_flow_alerts(
        self,
        *,
        ticker,
        session_open_et,
        max_pages=20,
        page_limit=500,
        require_complete=True,
    ):
        batch = super().fetch_session_to_date_flow_alerts(
            ticker=ticker,
            session_open_et=session_open_et,
            max_pages=max_pages,
            page_limit=page_limit,
            require_complete=require_complete,
        )

        alerts = [
            {
                "created_at": "2026-09-11T14:10:00Z",
                "expiry": "2026-09-18",
                "option_chain": (
                    f"{ticker}260918P00200000"
                ),
                "alert_rule": "Sweep",
                "type": "put",
                "total_ask_side_prem": 650_000.0,
                "total_bid_side_prem": 25_000.0,
                "has_multileg": False,
                "has_singleleg": True,
                "has_sweep": True,
                "all_opening_trades": True,
                "total_premium": 675_000.0,
            },
            {
                "created_at": "2026-09-11T14:15:00Z",
                "expiry": "2026-09-18",
                "option_chain": (
                    f"{ticker}260918C00200000"
                ),
                "alert_rule": "RepeatedHitsDescendingFill",
                "type": "call",
                "total_ask_side_prem": 100_000.0,
                "total_bid_side_prem": 200_000.0,
                "has_multileg": False,
                "has_singleleg": True,
                "has_sweep": False,
                "all_opening_trades": False,
                "total_premium": 300_000.0,
            },
        ]

        return replace(
            batch,
            alerts=alerts,
            rows_fetched=len(alerts),
            fetched_at=datetime(
                2026, 9, 11, 12, 20, 30,
                tzinfo=ET,
            ),
            freshness_status="PASS",
        )


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        first_trading_client = FakeTradingClient()

        first_cycle = WeeklyRuntimeCycle(
            services=services,
            providers=WeeklyProviders(
                stock=FakeStockProvider(),
                options=FakeOptionsProvider(),
                unusual_whales=FakeUWProvider(),
                trading_client=first_trading_client,
            ),
            market_context_service=(
                MarketContextService(
                    trading_client=first_trading_client
                )
            ),
        )

        first_result = first_cycle.run()

        assert first_result.reason == "CYCLE_COMPLETED"

        old_signal_ids = {
            ticker_result
            .resolution_results[0]
            .transition
            .signal
            .id
            for ticker_result in first_result.ticker_results
        }

        assert len(old_signal_ids) == 5

        second_trading_client = SecondCycleTradingClient()

        second_cycle = WeeklyRuntimeCycle(
            services=services,
            providers=WeeklyProviders(
                stock=FakeStockProvider(),
                options=FakeOptionsProvider(),
                unusual_whales=ReversedFakeUWProvider(),
                trading_client=second_trading_client,
            ),
            market_context_service=(
                MarketContextService(
                    trading_client=second_trading_client
                )
            ),
        )

        second_result = second_cycle.run()

        assert second_result.reason == "CYCLE_COMPLETED"
        assert len(second_result.ticker_results) == 5

        invalidated_ids = set()

        for ticker_result in second_result.ticker_results:
            matching_invalidations = [
                record
                for record in ticker_result.invalidations
                if (
                    record.signal_id in old_signal_ids
                    and record.result.invalidated
                    and record.result.reason
                    == "FLOW_DIRECTION_REVERSED"
                )
            ]

            assert len(matching_invalidations) == 1

            old_id = matching_invalidations[0].signal_id

            matching_resolutions = [
                item
                for item in ticker_result.resolution_results
                if (
                    item.transition.signal.id
                    == old_id
                )
            ]

            assert len(matching_resolutions) == 1

            resolution = matching_resolutions[0]

            assert (
                resolution
                .transition
                .resolution
                .target_state
                .value
                == "INVALIDATED"
            )

            assert (
                resolution
                .transition
                .resolution
                .reason
                == "SIGNAL_INVALIDATED"
            )

            assert (
                resolution.transition.persisted
                is True
            )

            assert (
                resolution.transition.signal.state.value
                == "INVALIDATED"
            )

            invalidated_ids.add(old_id)

        assert invalidated_ids == old_signal_ids

        print(
            "WEEKLY RUNTIME INVALIDATED: "
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
