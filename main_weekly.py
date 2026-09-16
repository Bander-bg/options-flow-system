from __future__ import annotations

from weekly.providers.weekly_provider_factory import (
    build_weekly_providers,
)
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesError,
)
from weekly.services.paper_execution_factory import (
    build_paper_execution_services,
)
from weekly.services.signal_alert_service import (
    SignalAlert,
)
from weekly.services.weekly_runtime_cycle import (
    WeeklyRuntimeCycle,
    WeeklyRuntimeCycleResult,
)
from weekly.services.weekly_runtime_factory import (
    build_weekly_runtime_services,
)
from weekly.services.weekly_scanner import (
    WeeklyScanner,
)


def print_cycle_result(
    result: WeeklyRuntimeCycleResult,
) -> None:
    print(
        "WEEKLY RUNTIME CYCLE:",
        result.reason,
    )

    print(
        "MARKET TIMESTAMP:",
        result.market_context.market_timestamp,
    )

    print(
        "TRADING DATE ET:",
        result.market_context.trading_date_et,
    )

    print(
        "MARKET OPEN:",
        result.market_context.market_is_open,
    )

    for ticker_result in result.ticker_results:
        print(
            ticker_result.ticker,
            "| expiry:",
            ticker_result.target_expiry,
            "| reason:",
            ticker_result.reason,
        )


def print_signal_alert(
    alert: SignalAlert,
) -> None:
    signal = alert.signal
    feature = alert.feature

    print("SIGNAL ALERT")
    print("TICKER:", signal.ticker)
    print("DIRECTION:", signal.direction.value)
    print("EXPIRY:", signal.target_expiry)
    print(
        "CONTRACT:",
        feature.selected_contract_symbol,
    )
    print(
        "STRIKE:",
        feature.selected_contract_strike,
    )
    print(
        "ASK:",
        feature.selected_contract_ask,
    )
    print(
        "MARK:",
        feature.selected_contract_mark,
    )
    print(
        "SCORE:",
        feature.final_score,
    )
    print(
        "GRADE:",
        feature.final_grade,
    )
    print(
        "COVERAGE:",
        feature.coverage_pct,
    )


def make_cycle_result_handler(
    execution_coordinator,
    signal_alert_service,
):
    def handle_result(
        result: WeeklyRuntimeCycleResult,
    ) -> None:
        print_cycle_result(result)

        coordination = (
            execution_coordinator.coordinate(
                cycle_result=result,
            )
        )

        for item in coordination.signals:
            print(
                item.signal.ticker,
                "| PAPER EXECUTION:",
                item.reason,
            )

            if (
                item.reason
                == "AWAITING_MANUAL_ENTRY"
                and item.signal.id is not None
            ):
                alert_result = (
                    signal_alert_service.send_and_activate(
                        signal_id=item.signal.id,
                    )
                )

                print(
                    item.signal.ticker,
                    "| SIGNAL ALERT:",
                    alert_result.reason,
                )

    return handle_result


def print_recoverable_error(
    exc: BaseException,
) -> None:
    if isinstance(exc, UnusualWhalesError):
        print(
            "WEEKLY RUNTIME CYCLE: DATA_SOURCE_BLOCKED"
        )
        print(
            "SOURCE: UNUSUAL_WHALES"
        )
        print(
            "REASON:",
            str(exc),
        )
        return

    print(
        "WEEKLY RUNTIME CYCLE: RECOVERABLE_ERROR"
    )
    print(
        "REASON:",
        str(exc),
    )


def main() -> None:
    """
    Continuous weekly_v1 scanner entrypoint.

    This entrypoint is intentionally separate from
    the legacy main.py.

    The scanner cadence comes from weekly_config.yaml.
    weekly_v1 currently runs every 3 minutes.

    Recoverable external-data failures do not stop
    the scanner. Trading logic remains inside the
    existing WeeklyRuntimeCycle.
    """
    services = build_weekly_runtime_services()
    providers = build_weekly_providers()

    execution_services = (
        build_paper_execution_services(
            runtime_services=services,
            providers=providers,
            signal_alert_sender=print_signal_alert,
        )
    )

    cycle = WeeklyRuntimeCycle(
        services=services,
        providers=providers,
    )

    scanner = WeeklyScanner.from_weekly_config(
        cycle=cycle,
    )

    cycle_result_handler = make_cycle_result_handler(
        execution_services.coordinator,
        execution_services.signal_alert_service,
    )

    scanner.run_forever(
        on_result=cycle_result_handler,
        recoverable_exceptions=(
            UnusualWhalesError,
        ),
        on_recoverable_error=(
            print_recoverable_error
        ),
    )


if __name__ == "__main__":
    main()
