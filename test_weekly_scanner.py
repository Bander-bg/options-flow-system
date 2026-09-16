from __future__ import annotations

from dataclasses import dataclass

from weekly.services.weekly_scanner import WeeklyScanner


@dataclass(frozen=True)
class FakeResult:
    reason: str = "CYCLE_COMPLETED"


class FakeCycle:
    def __init__(self) -> None:
        self.calls = 0

    def run(self):
        self.calls += 1
        return FakeResult()


class RecoverableTestError(Exception):
    pass


class FailingCycle:
    def __init__(self) -> None:
        self.calls = 0

    def run(self):
        self.calls += 1
        raise RecoverableTestError("temporary source failure")


def main() -> None:
    cycle = FakeCycle()
    sleeps = []

    scanner = WeeklyScanner(
        cycle=cycle,
        scan_interval_seconds=180,
        sleep_fn=sleeps.append,
    )

    result = scanner.run_once()

    assert result.reason == "CYCLE_COMPLETED"
    assert cycle.calls == 1
    assert scanner.scan_interval_seconds == 180.0

    observed_results = []
    observed_sleeps = []

    def stop_after_first_sleep(seconds):
        observed_sleeps.append(seconds)
        raise StopIteration

    looping_cycle = FakeCycle()

    looping_scanner = WeeklyScanner(
        cycle=looping_cycle,
        scan_interval_seconds=180,
        sleep_fn=stop_after_first_sleep,
    )

    try:
        looping_scanner.run_forever(
            on_result=observed_results.append,
        )
    except StopIteration:
        pass

    assert looping_cycle.calls == 1
    assert len(observed_results) == 1
    assert observed_sleeps == [180.0]

    recoverable_errors = []
    recoverable_sleeps = []

    def stop_after_recoverable_sleep(seconds):
        recoverable_sleeps.append(seconds)
        raise StopIteration

    failing_cycle = FailingCycle()

    recoverable_scanner = WeeklyScanner(
        cycle=failing_cycle,
        scan_interval_seconds=180,
        sleep_fn=stop_after_recoverable_sleep,
    )

    try:
        recoverable_scanner.run_forever(
            recoverable_exceptions=(
                RecoverableTestError,
            ),
            on_recoverable_error=(
                recoverable_errors.append
            ),
        )
    except StopIteration:
        pass

    assert failing_cycle.calls == 1
    assert len(recoverable_errors) == 1
    assert isinstance(
        recoverable_errors[0],
        RecoverableTestError,
    )
    assert recoverable_sleeps == [180.0]

    print("WEEKLY SCANNER: PASS")


if __name__ == "__main__":
    main()
