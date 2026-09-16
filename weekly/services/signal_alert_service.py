from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import SignalState
from weekly.domain.models import Signal, SignalFeature
from weekly.services.signal_operational_transition_service import (
    SignalOperationalTransitionResult,
    SignalOperationalTransitionService,
)


@dataclass(frozen=True)
class SignalAlert:
    signal: Signal
    feature: SignalFeature


@dataclass(frozen=True)
class SignalAlertResult:
    alert: SignalAlert | None
    transition: SignalOperationalTransitionResult | None
    sent: bool
    reason: str


class SignalAlertService:
    """
    Deliver a structured CONFIRMED signal alert and only
    then transition the signal to ACTIVE.

    The delivery channel is intentionally injected.
    This service does NOT:
    - choose trade quantity
    - choose order type
    - submit broker orders
    - create positions or trades
    """

    def __init__(
        self,
        *,
        signal_repository: SignalRepository,
        feature_repository: SignalFeatureRepository,
        transition_service: SignalOperationalTransitionService,
        sender: Callable[[SignalAlert], None],
    ) -> None:
        self.signal_repository = signal_repository
        self.feature_repository = feature_repository
        self.transition_service = transition_service
        self.sender = sender

    def send_and_activate(
        self,
        *,
        signal_id: int,
    ) -> SignalAlertResult:
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
            return SignalAlertResult(
                alert=None,
                transition=None,
                sent=False,
                reason="ALREADY_ACTIVE",
            )

        if signal.state is not SignalState.CONFIRMED:
            raise RuntimeError(
                "Only CONFIRMED signals may be alerted."
            )

        feature = self.feature_repository.get_latest_for_signal(
            signal_id
        )

        if feature is None:
            raise RuntimeError(
                "Latest SignalFeature not found."
            )

        alert = SignalAlert(
            signal=signal,
            feature=feature,
        )

        self.sender(alert)

        transition = self.transition_service.activate(
            signal_id=signal_id,
        )

        return SignalAlertResult(
            alert=alert,
            transition=transition,
            sent=True,
            reason="ALERT_SENT_AND_ACTIVATED",
        )
