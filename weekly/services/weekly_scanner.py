from __future__ import annotations

import time
from collections.abc import Callable

from config import load_weekly_config
from weekly.services.weekly_runtime_cycle import (
    WeeklyRuntimeCycle,
    WeeklyRuntimeCycleResult,
)


class WeeklyScanner:
    """
    Scheduling layer for weekly_v1.

    Responsibilities:
    - execute the existing WeeklyRuntimeCycle
    - respect scanner.scan_interval_minutes
    - keep scheduling separate from trading logic

    The runtime remains responsible for:
    - Candidate / state handling
    - confirmation deadlines
    - hard gates
    - terminal state resolution

    With deadline_processing_grace_polls=1, the first
    post-deadline runtime cycle is the only practical
    grace processing opportunity because resolution
    then moves the signal to a terminal state.
    """

    def __init__(
        self,
        *,
        cycle: WeeklyRuntimeCycle,
        scan_interval_seconds: float,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if scan_interval_seconds <= 0:
            raise ValueError(
                "scan_interval_seconds must be > 0"
            )

        self.cycle = cycle
        self.scan_interval_seconds = float(
            scan_interval_seconds
        )
        self.sleep_fn = sleep_fn

    @classmethod
    def from_weekly_config(
        cls,
        *,
        cycle: WeeklyRuntimeCycle,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> "WeeklyScanner":
        config = load_weekly_config(
            require_runtime_ready=True
        )

        scanner = config["scanner"]

        scan_interval_minutes = int(
            scanner["scan_interval_minutes"]
        )

        deadline_grace_polls = int(
            scanner[
                "deadline_processing_grace_polls"
            ]
        )

        if deadline_grace_polls != 1:
            raise ValueError(
                "weekly_v1 currently requires "
                "deadline_processing_grace_polls=1"
            )

        return cls(
            cycle=cycle,
            scan_interval_seconds=(
                scan_interval_minutes * 60
            ),
            sleep_fn=sleep_fn,
        )

    def run_once(
        self,
    ) -> WeeklyRuntimeCycleResult:
        return self.cycle.run()

    def run_forever(
        self,
        *,
        on_result: Callable[
            [WeeklyRuntimeCycleResult],
            None,
        ] | None = None,
        recoverable_exceptions: tuple[
            type[BaseException],
            ...,
        ] = (),
        on_recoverable_error: Callable[
            [BaseException],
            None,
        ] | None = None,
    ) -> None:
        while True:
            try:
                result = self.run_once()
            except recoverable_exceptions as exc:
                if on_recoverable_error is not None:
                    on_recoverable_error(exc)
            else:
                if on_result is not None:
                    on_result(result)

            self.sleep_fn(
                self.scan_interval_seconds
            )
