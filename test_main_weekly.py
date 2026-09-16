from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import main_weekly
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesError,
)


class FakeScanner:
    def __init__(self) -> None:
        self.run_forever_calls = 0
        self.kwargs = None

    def run_forever(self, **kwargs) -> None:
        self.run_forever_calls += 1
        self.kwargs = kwargs


def main() -> None:
    fake_services = object()
    fake_providers = object()
    fake_cycle = object()
    fake_scanner = FakeScanner()
    fake_coordinator = object()
    fake_signal_alert_service = object()
    fake_execution_services = SimpleNamespace(
        coordinator=fake_coordinator,
        signal_alert_service=fake_signal_alert_service,
    )

    with (
        patch(
            "main_weekly.build_weekly_runtime_services",
            return_value=fake_services,
        ) as services_mock,
        patch(
            "main_weekly.build_weekly_providers",
            return_value=fake_providers,
        ) as providers_mock,
        patch(
            "main_weekly.build_paper_execution_services",
            return_value=fake_execution_services,
        ) as execution_services_mock,
        patch(
            "main_weekly.WeeklyRuntimeCycle",
            return_value=fake_cycle,
        ) as cycle_mock,
        patch.object(
            main_weekly.WeeklyScanner,
            "from_weekly_config",
            return_value=fake_scanner,
        ) as scanner_mock,
    ):
        main_weekly.main()

    services_mock.assert_called_once_with()
    providers_mock.assert_called_once_with()

    execution_services_mock.assert_called_once_with(
        runtime_services=fake_services,
        providers=fake_providers,
        signal_alert_sender=main_weekly.print_signal_alert,
    )

    cycle_mock.assert_called_once_with(
        services=fake_services,
        providers=fake_providers,
    )

    scanner_mock.assert_called_once_with(
        cycle=fake_cycle,
    )

    assert fake_scanner.run_forever_calls == 1
    assert fake_scanner.kwargs is not None

    on_result = fake_scanner.kwargs["on_result"]

    assert callable(on_result)
    assert on_result is not main_weekly.print_cycle_result

    assert (
        fake_scanner.kwargs[
            "recoverable_exceptions"
        ]
        == (UnusualWhalesError,)
    )

    assert (
        fake_scanner.kwargs[
            "on_recoverable_error"
        ]
        is main_weekly.print_recoverable_error
    )

    print("MAIN WEEKLY INTEGRATION: PASS")


if __name__ == "__main__":
    main()
