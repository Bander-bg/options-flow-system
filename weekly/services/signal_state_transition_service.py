
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import SignalState, TERMINAL_SIGNAL_STATES
from weekly.domain.models import Signal
from weekly.services.hard_gate_service import HardGateResult
from weekly.services.signal_state_resolution_service import (
    SignalStateResolutionResult,
    SignalStateResolutionService,
)


class SignalStateTransitionError(ValueError):
    """Invalid persisted signal-state transition input."""


@dataclass(frozen=True)
class SignalStateTransitionResult:
    resolution: SignalStateResolutionResult
    signal: Signal
    persisted: bool


class SignalStateTransitionService:
    """
    Persist pre-confirmation signal state transitions.

    Responsibilities
    ---------------
    - Delegate decision logic to SignalStateResolutionService.
    - Persist only when the resolver requests a transition.
    - Use expected_state for stale-write protection.
    - Stamp confirmed_at for CONFIRMED.
    - Stamp terminal_at / terminal_reason for terminal resolution states.
    - Persist net_flow_at_confirmation only when transitioning to CONFIRMED.

    This service does NOT perform Hard Gate calculations and does NOT
    perform operational transitions such as CONFIRMED -> ACTIVE.
    """

    def __init__(
        self,
        *,
        signal_repository: SignalRepository,
        resolution_service: SignalStateResolutionService | None = None,
    ) -> None:
        self._signal_repository = signal_repository
        self._resolution_service = (
            resolution_service
            if resolution_service is not None
            else SignalStateResolutionService()
        )

    def resolve_and_persist(
        self,
        *,
        signal: Signal,
        hard_gate_result: HardGateResult,
        invalidated: bool,
        resolution_window_closed: bool,
        resolved_at: datetime,
        net_flow_at_confirmation: float | None = None,
    ) -> SignalStateTransitionResult:
        self._validate(
            signal=signal,
            resolved_at=resolved_at,
            net_flow_at_confirmation=net_flow_at_confirmation,
        )

        resolution = self._resolution_service.resolve(
            current_state=signal.state,
            hard_gate_result=hard_gate_result,
            invalidated=invalidated,
            resolution_window_closed=resolution_window_closed,
        )

        if not resolution.should_transition:
            return SignalStateTransitionResult(
                resolution=resolution,
                signal=signal,
                persisted=False,
            )

        target = resolution.target_state

        confirmed_at = (
            resolved_at
            if target is SignalState.CONFIRMED
            else None
        )

        terminal_at = (
            resolved_at
            if target in TERMINAL_SIGNAL_STATES
            else None
        )

        terminal_reason = (
            resolution.reason
            if target in TERMINAL_SIGNAL_STATES
            else None
        )

        confirmation_flow = (
            net_flow_at_confirmation
            if target is SignalState.CONFIRMED
            else None
        )

        updated = self._signal_repository.update_state(
            signal_id=signal.id,
            new_state=target,
            expected_state=signal.state,
            confirmed_at=confirmed_at,
            terminal_at=terminal_at,
            terminal_reason=terminal_reason,
            net_flow_at_confirmation=confirmation_flow,
        )

        return SignalStateTransitionResult(
            resolution=resolution,
            signal=updated,
            persisted=True,
        )

    @staticmethod
    def _validate(
        *,
        signal: Signal,
        resolved_at: datetime,
        net_flow_at_confirmation: float | None,
    ) -> None:
        if signal.id is None or signal.id < 1:
            raise SignalStateTransitionError(
                "signal must be persisted and have id >= 1."
            )

        if resolved_at.tzinfo is None:
            raise SignalStateTransitionError(
                "resolved_at must be timezone-aware."
            )

        if (
            net_flow_at_confirmation is not None
            and not isinstance(
                net_flow_at_confirmation,
                (int, float),
            )
        ):
            raise SignalStateTransitionError(
                "net_flow_at_confirmation must be numeric or None."
            )
