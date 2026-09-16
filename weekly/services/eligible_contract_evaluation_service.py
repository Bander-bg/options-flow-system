from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Iterable

from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.domain.enums import Direction
from weekly.domain.models import SignalFeature
from weekly.services.eligible_contract_service import (
    EligibleContractResult,
    EligibleContractService,
    OptionContractCandidate,
)


class EligibleContractEvaluationError(ValueError):
    """Invalid eligible-contract evaluation/persistence input."""


@dataclass(frozen=True)
class EligibleContractEvaluation:
    result: EligibleContractResult
    feature: SignalFeature


class EligibleContractEvaluationService:
    """
    Evaluate the eligible-contract Hard Gate and persist
    one immutable SignalFeature snapshot.

    Existing feature data is preserved.
    Signal state is never changed here.
    """

    def __init__(
        self,
        *,
        eligible_contract_service: EligibleContractService,
        feature_repository: SignalFeatureRepository,
    ) -> None:
        self.eligible_contract_service = eligible_contract_service
        self.feature_repository = feature_repository

    def evaluate_and_persist(
        self,
        *,
        signal_id: int,
        direction: Direction,
        target_expiry: date,
        as_of: datetime,
        contracts: Iterable[OptionContractCandidate] | None,
        captured_at: datetime,
    ) -> EligibleContractEvaluation:
        self._validate_inputs(
            signal_id=signal_id,
            as_of=as_of,
            captured_at=captured_at,
        )

        previous = self.feature_repository.get_latest_for_signal(signal_id)

        underlying_price = (
            previous.underlying_price
            if previous is not None
            else None
        )
        expected_move = (
            previous.expected_move
            if previous is not None
            else None
        )

        result = self.eligible_contract_service.evaluate(
            direction=direction,
            target_expiry=target_expiry,
            underlying_price=underlying_price,
            expected_move=expected_move,
            as_of=as_of,
            contracts=contracts,
        )

        next_sequence = self.feature_repository.next_evaluation_sequence(
            signal_id
        )

        selected = result.selected

        updates = dict(
            evaluation_sequence=next_sequence,
            captured_at=captured_at,
            eligible_contract_status=result.status,
            selected_contract_symbol=(
                selected.symbol if selected is not None else None
            ),
            selected_contract_right=(
                selected.right if selected is not None else None
            ),
            selected_contract_strike=(
                selected.strike if selected is not None else None
            ),
            selected_contract_bid=(
                selected.bid if selected is not None else None
            ),
            selected_contract_ask=(
                selected.ask if selected is not None else None
            ),
            selected_contract_mark=(
                selected.mark if selected is not None else None
            ),
            selected_contract_delta=(
                selected.delta if selected is not None else None
            ),
            selected_contract_gamma=(
                selected.gamma if selected is not None else None
            ),
            selected_contract_theta=(
                selected.theta if selected is not None else None
            ),
            selected_contract_vega=(
                selected.vega if selected is not None else None
            ),
            selected_contract_iv=(
                selected.iv if selected is not None else None
            ),
            selected_contract_spread_pct=(
                selected.spread_pct if selected is not None else None
            ),
            selected_contract_quote_age_seconds=(
                selected.quote_age_seconds
                if selected is not None
                else None
            ),
        )

        if previous is None:
            feature = SignalFeature(
                signal_id=signal_id,
                **updates,
            )
        else:
            feature = replace(
                previous,
                id=None,
                **updates,
            )

        created = self.feature_repository.create(feature)

        return EligibleContractEvaluation(
            result=result,
            feature=created,
        )

    @staticmethod
    def _validate_inputs(
        *,
        signal_id: int,
        as_of: datetime,
        captured_at: datetime,
    ) -> None:
        if signal_id < 1:
            raise EligibleContractEvaluationError(
                "signal_id must be >= 1."
            )

        if as_of.tzinfo is None:
            raise EligibleContractEvaluationError(
                "as_of must be timezone-aware."
            )

        if captured_at.tzinfo is None:
            raise EligibleContractEvaluationError(
                "captured_at must be timezone-aware."
            )

        if captured_at < as_of:
            raise EligibleContractEvaluationError(
                "captured_at must be >= as_of."
            )
