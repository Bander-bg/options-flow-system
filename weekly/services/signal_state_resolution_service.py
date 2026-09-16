from __future__ import annotations

from dataclasses import dataclass

from weekly.domain.enums import (
    GateStatus,
    LOCKED_RESOLUTION_STATES,
    TERMINAL_SIGNAL_STATES,
    SignalState,
)
from weekly.services.hard_gate_service import HardGateResult


class SignalStateResolutionError(ValueError):
    """Invalid signal-state resolution input."""


@dataclass(frozen=True)
class SignalStateResolutionResult:
    current_state: SignalState
    target_state: SignalState
    should_transition: bool
    reason: str
    is_terminal: bool


class SignalStateResolutionService:
    """
    Resolve the weekly_v1 pre-confirmation signal state.

    Resolution precedence
    ---------------------
    1. Existing locked resolution states are immutable here.
    2. INVALIDATED dominates all Hard Gate outcomes.
    3. Final Hard FAIL -> REJECTED.
    4. Hard UNKNOWN while the resolution window is open
       -> DATA_BLOCKED.
    5. Hard UNKNOWN after the resolution window closes
       -> DATA_UNRESOLVED.
    6. All Hard Gates PASS -> CONFIRMED.

    This service is pure logic. It does NOT write to the database.
    """

    _RESOLVABLE_STATES = frozenset(
        {
            SignalState.CANDIDATE,
            SignalState.DATA_BLOCKED,
        }
    )

    def resolve(
        self,
        *,
        current_state: SignalState,
        hard_gate_result: HardGateResult,
        invalidated: bool,
        resolution_window_closed: bool,
    ) -> SignalStateResolutionResult:

        self._validate(
            current_state=current_state,
            hard_gate_result=hard_gate_result,
            invalidated=invalidated,
            resolution_window_closed=resolution_window_closed,
        )

        # Once resolution is locked, this service must not rewrite it.
        if current_state in LOCKED_RESOLUTION_STATES:
            return self._result(
                current_state=current_state,
                target_state=current_state,
                reason="RESOLUTION_LOCKED",
            )

        if current_state not in self._RESOLVABLE_STATES:
            raise SignalStateResolutionError(
                f"State {current_state.value} is not resolvable "
                "by SignalStateResolutionService."
            )

        # Highest precedence before confirmation.
        if invalidated:
            return self._result(
                current_state=current_state,
                target_state=SignalState.INVALIDATED,
                reason="SIGNAL_INVALIDATED",
            )

        if hard_gate_result.status is GateStatus.FAIL: 
            return self._result(
                current_state=current_state,
                target_state=SignalState.REJECTED,
                reason="HARD_GATE_FAIL",
            )

        if hard_gate_result.status is GateStatus.UNKNOWN:
            if resolution_window_closed:
                return self._result(
                    current_state=current_state,
                    target_state=SignalState.DATA_UNRESOLVED,
                    reason="RESOLUTION_WINDOW_CLOSED_WITH_UNKNOWN_DATA",
                )

            return self._result(
                current_state=current_state,
                target_state=SignalState.DATA_BLOCKED,
                reason="HARD_GATE_UNKNOWN",
            )

        if hard_gate_result.status is GateStatus.PASS:
            return self._result(
                current_state=current_state,
                target_state=SignalState.CONFIRMED,
                reason="ALL_HARD_GATES_PASS",
            )

        raise SignalStateResolutionError(
            "Unsupported Hard Gate aggregate status."
        )

    @staticmethod
    def _result(
        *,
        current_state: SignalState,
        target_state: SignalState,
        reason: str,
    ) -> SignalStateResolutionResult:
        return SignalStateResolutionResult(
            current_state=current_state,
            target_state=target_state,
            should_transition=(
                target_state is not current_state
            ),
            reason=reason,
            is_terminal=(
                target_state in TERMINAL_SIGNAL_STATES
            ),
        )

    @staticmethod
    def _validate(
        *,
        current_state: SignalState,
        hard_gate_result: HardGateResult,
        invalidated: bool,
        resolution_window_closed: bool,
    ) -> None:
        if not isinstance(current_state, SignalState):
            raise SignalStateResolutionError(
                "current_state must be SignalState."
            )

        if not isinstance(hard_gate_result, HardGateResult):
            raise SignalStateResolutionError(
                "hard_gate_result must be HardGateResult."
            )

        if not isinstance(invalidated, bool):
            raise SignalStateResolutionError(
                "invalidated must be bool."
            )

        if not isinstance(resolution_window_closed, bool):
            raise SignalStateResolutionError(
                "resolution_window_closed must be bool."
            )

        if (
            resolution_window_closed
            and hard_gate_result.status is GateStatus.UNKNOWN
            and hard_gate_result.price_action_status is GateStatus.UNKNOWN
            and not hard_gate_result.price_action_is_final
        ):
            raise SignalStateResolutionError(
                "A closed resolution window cannot contain a "
                "non-final Price Action confirmation result."
            )
