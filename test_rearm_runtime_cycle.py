from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from weekly.providers.unusual_whales_provider import (
    FlowAlertsBatch,
)
from weekly.providers.weekly_provider_factory import (
    WeeklyProviders,
)
from weekly.services.market_context_service import (
    MarketContextService,
)
from weekly.services.weekly_runtime_cycle import (
    WeeklyRuntimeCycle,
)
from weekly.services.weekly_runtime_factory import (
    build_weekly_runtime_services,
)

from test_weekly_runtime_cycle import (
    ET,
    TEMP_DB,
    FakeUWProvider,
    create_temp_database,
    patch_repositories,
)
from test_weekly_runtime_cycle_confirmed import (
    ConfirmedTradingClient,
    ConfirmedStockProvider,
    ConfirmedOptionsProvider,
)


class ReArmTradingClient(ConfirmedTradingClient):
    def get_clock(self):
        base = super().get_clock()

        return SimpleNamespace(
            timestamp=datetime(
                2026, 9, 11, 14, 1,
                tzinfo=ET,
            ),
            is_open=True,
            next_open=base.next_open,
            next_close=base.next_close,
        )


class ReArmUWProvider(FakeUWProvider):
    def fetch_session_to_date_flow_alerts(
        self,
        *,
        ticker,
        session_open_et,
        max_pages=20,
        page_limit=500,
        require_complete=True,
    ):
        base = super().fetch_session_to_date_flow_alerts(
            ticker=ticker,
            session_open_et=session_open_et,
            max_pages=max_pages,
            page_limit=page_limit,
            require_complete=require_complete,
        )

        alerts = [
            dict(row)
            for row in base.alerts
        ]

        # Base Flow:
        # Call Ask 1,150,000
        # Put Ask    100,000
        # Net      1,050,000
        #
        # Previous confirmation = 550,000
        # Additional aligned flow = +500,000
        alerts[0]["total_ask_side_prem"] = (
            1_150_000.0
        )

        captured_at = datetime(
            2026, 9, 11, 14, 0, 30,
            tzinfo=ET,
        )

        return FlowAlertsBatch(
            ticker=ticker,
            alerts=alerts,
            pages_fetched=base.pages_fetched,
            rows_fetched=len(alerts),
            session_coverage_complete=True,
            session_start_reached=True,
            history_exhausted=False,
            newest_created_at=datetime(
                2026, 9, 11, 13, 55,
                tzinfo=ET,
            ),
            oldest_created_at=(
                base.oldest_created_at
            ),
            provider=base.provider,
            feed=base.feed,
            source_timestamp=datetime(
                2026, 9, 11, 13, 55,
                tzinfo=ET,
            ),
            fetched_at=captured_at,
            freshness_status="PASS",
        )


class ReArmStockProvider(ConfirmedStockProvider):
    def get_minute_bars(
        self,
        *,
        ticker,
        start,
        end,
    ):
        base = super().get_minute_bars(
            ticker=ticker,
            start=start,
            end=end,
        )

        bars = list(base.bars)

        # Fresh completed trigger AFTER the first
        # confirmation timestamp (~12:46 ET).
        #
        # Large bullish body + structure breakout
        # is enough for the existing 2-of-3 PA rule.
        bars.append(
            self._bar(
                start_at=datetime(
                    2026, 9, 11, 13, 45,
                    tzinfo=ET,
                ),
                open_price=205.0,
                high=211.0,
                low=204.5,
                close=210.5,
                volume=1200.0,
            )
        )

        return replace(
            base,
            requested_start=start,
            requested_end=end,
            bars=tuple(bars),
        )


def build_cycle(
    *,
    services,
    trading_client,
    stock_provider,
    uw_provider,
):
    providers = WeeklyProviders(
        stock=stock_provider,
        options=ConfirmedOptionsProvider(),
        unusual_whales=uw_provider,
        trading_client=trading_client,
    )

    return WeeklyRuntimeCycle(
        services=services,
        providers=providers,
        market_context_service=(
            MarketContextService(
                trading_client=trading_client
            )
        ),
    )


def main() -> None:
    create_temp_database()
    patch_repositories()

    try:
        services = build_weekly_runtime_services()

        # --------------------------------------------------
        # CYCLE 1
        # Create + fully CONFIRM Candidate #1.
        # --------------------------------------------------

        first_client = ConfirmedTradingClient()

        first_cycle = build_cycle(
            services=services,
            trading_client=first_client,
            stock_provider=ConfirmedStockProvider(),
            uw_provider=FakeUWProvider(),
        )

        first_result = first_cycle.run()

        assert first_result.reason == "CYCLE_COMPLETED"

        for ticker_result in first_result.ticker_results:
            assert (
                len(ticker_result.resolution_results)
                == 1
            )

            signal = (
                ticker_result
                .resolution_results[0]
                .transition
                .signal
            )

            assert signal.state.value == "CONFIRMED"

            assert (
                signal.net_flow_at_confirmation
                == 550_000.0
            )

            assert signal.confirmed_at is not None

            assert ticker_result.rearm_result is None

        # --------------------------------------------------
        # CYCLE 2
        # After cooldown:
        # - same session
        # - +500k aligned flow
        # - fresh PA trigger after confirmed_at
        # --------------------------------------------------

        second_client = ReArmTradingClient()

        second_cycle = build_cycle(
            services=services,
            trading_client=second_client,
            stock_provider=ReArmStockProvider(),
            uw_provider=ReArmUWProvider(),
        )

        second_result = second_cycle.run()

        assert second_result.reason == "CYCLE_COMPLETED"

        for ticker_result in second_result.ticker_results:
            assert (
                ticker_result.flow_snapshot.net_flow
                == 1_050_000.0
            )

            candidate = ticker_result.candidate_result

            assert candidate is not None
            assert candidate.created is False

            assert (
                candidate.reason
                == "EXISTING_SIGNAL_REQUIRES_REARM"
            )

            rearm = ticker_result.rearm_result

            assert rearm is not None
            assert rearm.allowed is True

            assert rearm.reason == "REARM_ALLOWED"

            assert rearm.aligned_flow == 500_000.0

            # ReArm is diagnostic only for now.
            # No Candidate #2 and no new resolution.
            assert (
                len(ticker_result.resolution_results)
                == 0
            )

            next_sequence = (
                services.signal_repository
                .next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker=ticker_result.ticker,
                    trading_date_et=date(
                        2026, 9, 11
                    ),
                    target_expiry=date(
                        2026, 9, 18
                    ),
                    direction=candidate.direction,
                )
            )

            assert next_sequence == 2

        print(
            "1. first cycle CONFIRMED: PASS"
        )
        print(
            "2. cooldown elapsed: PASS"
        )
        print(
            "3. +500k aligned flow recognized: PASS"
        )
        print(
            "4. fresh post-confirmation PA trigger: PASS"
        )
        print(
            "5. REARM_ALLOWED without Candidate #2: PASS"
        )
        print()
        print(
            "REARM RUNTIME DIAGNOSTIC: PASS 5/5"
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
