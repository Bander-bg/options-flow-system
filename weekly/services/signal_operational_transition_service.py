from __future__ import annotations

from dataclasses import dataclass

from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import SignalState
from weekly.domain.models import Signal


@dataclass(frozen=True)
class SignalOperationalTransitionResult:
    signal: Signal
    persisted: bool
    reason: str


class SignalOperationalTransitionService:
    """
    Persist post-confirmation operational transitions.

    Current weekly_v1 scope:
        CONFIRMED -> ACTIVE

    This service does NOT:
    - submit broker orders
    - choose execution policy
    - choose quantity
    - create positions or trades
    """

    def __init__(
        self,
        *,
        signal_repository: SignalRepository,
    ) -> None:
        self.signal_repository = signal_repository

    def activate(
        self,
        *,
        signal_id: int,
    ) -> SignalOperationalTransitionResult:
        if signal_id < 1:
            raise ValueError(
                "signal_id must be >= 1"
            )

        signal = self.signal_repository.get_by_id(
            signal_id
        )

        if signal is None:
            raise RuntimeError(
                "Signal not found."
            )

        if signal.state is SignalState.ACTIVE:
            return SignalOperationalTransitionResult(
                signal=signal,
                persisted=False,
                reason="ALREADY_ACTIVE",
            )

        if signal.state is not SignalState.CONFIRMED:
            raise RuntimeError(
                "Only CONFIRMED signals may "
                "transition to ACTIVE."
            )

        updated = self.signal_repository.update_state(
            signal_id=signal.id,
            new_state=SignalState.ACTIVE,
            expected_state=SignalState.CONFIRMED,
        )

        return SignalOperationalTransitionResult(
            signal=updated,
            persisted=True,
            reason="CONFIRMED_TO_ACTIVE",
        )
