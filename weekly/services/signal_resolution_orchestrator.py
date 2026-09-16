from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.services.hard_gate_service import (
    HardGateResult,
    HardGateService,
)
from weekly.services.price_action_confirmation_service import (
    PriceActionConfirmationResult,
    PriceActionConfirmationService,
)
from weekly.services.signal_state_transition_service import (
    SignalStateTransitionResult,
    SignalStateTransitionService,
)


class SignalResolutionOrchestratorError(ValueError):
    """Invalid signal-resolution orchestration input."""


@dataclass(frozen=True)
class SignalResolutionOrchestrationResult:
    price_action_confirmation: PriceActionConfirmationResult
    hard_gate_result: HardGateResult
    transition: SignalStateTransitionResult


class SignalResolutionOrchestrator:
    """
    Orchestrate pre-confirmation weekly signal resolution.

    Responsibilities:
    1. Load the persisted Signal.
    2. Load all immutable SignalFeature snapshots.
    3. Resolve the Price Action confirmation window.
    4. Aggregate the five frozen Hard Gates.
    5. Resolve and persist the Signal state transition.

    This service does not calculate individual market features.
    """

    def __init__(
        self,
        *,
        signal_repository: SignalRepository,
        feature_repository: SignalFeatureRepository,
        price_action_confirmation_service: PriceActionConfirmationService | None = None,
        hard_gate_service: HardGateService | None = None,
        transition_service: SignalStateTransitionService | None = None,
    ) -> None:
        self.signal_repository = signal_repository
        self.feature_repository = feature_repository
        self.price_action_confirmation_service = (
            price_action_confirmation_service
            if price_action_confirmation_service is not None
            else PriceActionConfirmationService()
        )
        self.hard_gate_service = (
            hard_gate_service
            if hard_gate_service is not None
            else HardGateService()
        )
        self.transition_service = (
            transition_service
            if transition_service is not None
            else SignalStateTransitionService(
                signal_repository=signal_repository
            )
        )

    def resolve_and_persist(
        self,
        *,
        signal_id: int,
        as_of: datetime,
        invalidated: bool,
        net_flow_at_confirmation: float | None = None,
    ) -> SignalResolutionOrchestrationResult:
        self._validate_inputs(
            signal_id=signal_id,
            as_of=as_of,
            invalidated=invalidated,
        )

        signal = self.signal_repository.get_by_id(signal_id)

        if signal is None:
            raise SignalResolutionOrchestratorError(
                "Signal not found."
            )

        if signal.candidate_at is None:
            raise SignalResolutionOrchestratorError(
                "Signal candidate_at is required."
            )

        if signal.confirmation_deadline_at is None:
            raise SignalResolutionOrchestratorError(
                "Signal confirmation_deadline_at is required."
            )

        features = self.feature_repository.get_all_for_signal(
            signal_id
        )

        latest = (
            features[-1]
            if features
            else None
        )

        price_action_confirmation = (
            self.price_action_confirmation_service.resolve(
                candidate_at=signal.candidate_at,
                confirmation_deadline_at=(
                    signal.confirmation_deadline_at
                ),
                as_of=as_of,
                features=features,
            )
        )

        hard_gate_result = self.hard_gate_service.evaluate(
            vwap_status=(
                latest.vwap_status
                if latest is not None
                else None
            ),
            efficiency_ratio_status=(
                latest.efficiency_ratio_status
                if latest is not None
                else None
            ),
            price_action_confirmation=(
                price_action_confirmation
            ),
            eligible_contract_status=(
                latest.eligible_contract_status
                if latest is not None
                else None
            ),
            earnings_event_risk_status=(
                latest.earnings_event_risk_status
                if latest is not None
                else None
            ),
        )

        resolution_window_closed = (
            as_of >= signal.confirmation_deadline_at
        )

        transition = self.transition_service.resolve_and_persist(
            signal=signal,
            hard_gate_result=hard_gate_result,
            invalidated=invalidated,
            resolution_window_closed=resolution_window_closed,
            resolved_at=as_of,
            net_flow_at_confirmation=net_flow_at_confirmation,
        )

        return SignalResolutionOrchestrationResult(
            price_action_confirmation=price_action_confirmation,
            hard_gate_result=hard_gate_result,
            transition=transition,
        )

    @staticmethod
    def _validate_inputs(
        *,
        signal_id: int,
        as_of: datetime,
        invalidated: bool,
    ) -> None:
        if signal_id < 1:
            raise SignalResolutionOrchestratorError(
                "signal_id must be >= 1."
            )

        if as_of.tzinfo is None:
            raise SignalResolutionOrchestratorError(
                "as_of must be timezone-aware."
            )

        if not isinstance(invalidated, bool):
            raise SignalResolutionOrchestratorError(
                "invalidated must be bool."
            )