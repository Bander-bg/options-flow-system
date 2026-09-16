from __future__ import annotations

from dataclasses import dataclass

from weekly.domain.enums import SignalState
from weekly.domain.models import Signal
from weekly.services.weekly_runtime_cycle import (
    WeeklyRuntimeCycleResult,
)


@dataclass(frozen=True)
class PaperExecutionSignalSelection:
    signals: tuple[Signal, ...]


class PaperExecutionSignalSelector:
    """
    Extract unique CONFIRMED signals from a completed
    WeeklyRuntimeCycleResult.

    This service does NOT:
    - choose quantity
    - prepare Position/Trade records
    - submit orders
    - transition Signal state
    """

    def select(
        self,
        *,
        cycle_result: WeeklyRuntimeCycleResult,
    ) -> PaperExecutionSignalSelection:
        selected_by_id: dict[int, Signal] = {}

        for ticker_result in cycle_result.ticker_results:
            for resolution in ticker_result.resolution_results:
                signal = resolution.transition.signal

                if signal.id is None:
                    continue

                if signal.state is not SignalState.CONFIRMED:
                    continue

                selected_by_id[signal.id] = signal

        return PaperExecutionSignalSelection(
            signals=tuple(
                selected_by_id[signal_id]
                for signal_id in sorted(selected_by_id)
            )
        )
