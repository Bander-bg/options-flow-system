from __future__ import annotations

from dataclasses import dataclass

from weekly.db.position_repository import PositionRepository
from weekly.db.trade_repository import TradeRepository
from weekly.domain.enums import TradeIntent
from weekly.domain.models import Signal
from weekly.services.paper_execution_recovery_service import (
    PaperExecutionRecoveryResult,
    PaperExecutionRecoveryService,
)
from weekly.services.paper_execution_signal_selector import (
    PaperExecutionSignalSelector,
)
from weekly.services.weekly_runtime_cycle import (
    WeeklyRuntimeCycleResult,
)


@dataclass(frozen=True)
class PaperExecutionSignalStatus:
    signal: Signal
    reason: str


@dataclass(frozen=True)
class PaperExecutionCoordinationResult:
    recovery: PaperExecutionRecoveryResult
    signals: tuple[PaperExecutionSignalStatus, ...]


class PaperExecutionCoordinator:
    """
    Coordinate PAPER execution readiness without
    inventing execution policy.

    Per cycle:
    1. Recover unfinished broker executions.
    2. Select CONFIRMED signals.
    3. Classify each signal safely.

    This service does NOT:
    - choose quantity
    - choose Market vs Limit
    - prepare new execution records
    - submit new orders
    - transition Signal state
    """

    def __init__(
        self,
        *,
        signal_selector: PaperExecutionSignalSelector,
        recovery_service: PaperExecutionRecoveryService,
        position_repository: PositionRepository,
        trade_repository: TradeRepository,
    ):
        self.signal_selector = signal_selector
        self.recovery_service = recovery_service
        self.position_repository = position_repository
        self.trade_repository = trade_repository

    def coordinate(
        self,
        *,
        cycle_result: WeeklyRuntimeCycleResult,
    ) -> PaperExecutionCoordinationResult:
        recovery = self.recovery_service.recover()

        selection = self.signal_selector.select(
            cycle_result=cycle_result,
        )

        statuses: list[PaperExecutionSignalStatus] = []

        for signal in selection.signals:
            if signal.id is None:
                continue

            open_position = (
                self.position_repository
                .get_open_for_signal(signal.id)
            )

            if open_position is not None:
                statuses.append(
                    PaperExecutionSignalStatus(
                        signal=signal,
                        reason="EXISTING_OPEN_POSITION",
                    )
                )
                continue

            trades = (
                self.trade_repository
                .list_for_signal(signal.id)
            )

            has_open_execution_history = any(
                trade.intent is TradeIntent.OPEN
                for trade in trades
            )

            if has_open_execution_history:
                statuses.append(
                    PaperExecutionSignalStatus(
                        signal=signal,
                        reason=(
                            "EXISTING_EXECUTION_HISTORY"
                        ),
                    )
                )
                continue

            statuses.append(
                PaperExecutionSignalStatus(
                    signal=signal,
                    reason="AWAITING_MANUAL_ENTRY",
                )
            )

        return PaperExecutionCoordinationResult(
            recovery=recovery,
            signals=tuple(statuses),
        )
