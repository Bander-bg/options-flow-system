from __future__ import annotations

from dataclasses import dataclass

from weekly.domain.enums import GateStatus
from weekly.services.price_action_confirmation_service import (
    PriceActionConfirmationResult,
)


class HardGateError(ValueError):
    """Invalid Hard Gate aggregation input."""


@dataclass(frozen=True)
class HardGateResult:
    """
    Aggregate result for the frozen weekly_v1 Hard Gates.

    status:
        PASS    -> every Hard Gate passed.
        FAIL    -> at least one Hard Gate failed.
        UNKNOWN -> no FAIL exists, but one or more gates
                   are unresolved / missing.

    This result does NOT mutate Signal state.
    """

    status: GateStatus

    vwap_status: GateStatus
    efficiency_ratio_status: GateStatus
    price_action_status: GateStatus
    eligible_contract_status: GateStatus
    earnings_event_risk_status: GateStatus

    failed_gates: tuple[str, ...]
    unknown_gates: tuple[str, ...]

    price_action_is_final: bool
    price_action_reason: str

    reason: str

    @property
    def ready_for_confirmation(self) -> bool:
        return self.status is GateStatus.PASS

    @property
    def has_hard_fail(self) -> bool:
        return self.status is GateStatus.FAIL

    @property
    def has_hard_unknown(self) -> bool:
        return self.status is GateStatus.UNKNOWN


class HardGateService:
    """
    Aggregate the frozen weekly_v1 Hard Gates.

    Hard Gates:
    1. Weekly VWAP alignment
    2. Efficiency Ratio
    3. Price Action confirmation window
    4. Eligible option contract exists
    5. Earnings / event risk veto

    Important:
    - Price Action must be supplied as a resolved
      PriceActionConfirmationResult, NOT a raw
      SignalFeature.price_action_status.
    - A temporary Price Action FAIL inside the open
      confirmation window is therefore never treated
      as a Hard FAIL here.
    - Any Hard FAIL dominates UNKNOWN.
    - If no FAIL exists but any gate is UNKNOWN,
      aggregate status is UNKNOWN.
    - Only all PASS produces aggregate PASS.
    - Signal state transitions are intentionally handled
      by a separate state-resolution service.
    """

    VWAP = "VWAP"
    EFFICIENCY_RATIO = "EFFICIENCY_RATIO"
    PRICE_ACTION = "PRICE_ACTION"
    ELIGIBLE_CONTRACT = "ELIGIBLE_CONTRACT"
    EARNINGS_EVENT_RISK = "EARNINGS_EVENT_RISK"

    def evaluate(
        self,
        *,
        vwap_status: GateStatus | None,
        efficiency_ratio_status: GateStatus | None,
        price_action_confirmation: PriceActionConfirmationResult,
        eligible_contract_status: GateStatus | None,
        earnings_event_risk_status: GateStatus | None,
    ) -> HardGateResult:

        self._validate_price_action_confirmation(
            price_action_confirmation
        )

        normalized_vwap = self._normalize(
            vwap_status
        )

        normalized_er = self._normalize(
            efficiency_ratio_status
        )

        normalized_contract = self._normalize(
            eligible_contract_status
        )

        normalized_earnings = self._normalize(
            earnings_event_risk_status
        )

        normalized_price_action = (
            price_action_confirmation.status
        )

        gates = (
            (
                self.VWAP,
                normalized_vwap,
            ),
            (
                self.EFFICIENCY_RATIO,
                normalized_er,
            ),
            (
                self.PRICE_ACTION,
                normalized_price_action,
            ),
            (
                self.ELIGIBLE_CONTRACT,
                normalized_contract,
            ),
            (
                self.EARNINGS_EVENT_RISK,
                normalized_earnings,
            ),
         )

        failed_gates = tuple(
            name
            for name, status in gates
            if status is GateStatus.FAIL
         )

        unknown_gates = tuple(
            name
            for name, status in gates
            if status is GateStatus.UNKNOWN
        )

        if failed_gates:
            status = GateStatus.FAIL
            reason = "HARD_GATE_FAIL"

        elif unknown_gates:
            status = GateStatus.UNKNOWN

            if (
                self.PRICE_ACTION
                in unknown_gates
                and not (
                    price_action_confirmation
                    .is_final
                )
            ):
                reason = (
                    "HARD_GATE_UNKNOWN_"
                    "PRICE_ACTION_WINDOW_OPEN"
                )

            else:
                reason = "HARD_GATE_UNKNOWN"

        else:
            status = GateStatus.PASS
            reason = "ALL_HARD_GATES_PASS"

        return HardGateResult(
            status=status,

            vwap_status=normalized_vwap,

            efficiency_ratio_status=(
                normalized_er
            ),

            price_action_status=(
                normalized_price_action
            ),

            eligible_contract_status=(
                normalized_contract
            ),
            earnings_event_risk_status=(
                normalized_earnings
            ),

            failed_gates=failed_gates,

            unknown_gates=unknown_gates,

            price_action_is_final=(
                price_action_confirmation
                .is_final
            ),

            price_action_reason=(
                price_action_confirmation
                .reason
            ),

            reason=reason,
        )

    @staticmethod
    def _normalize(
        status: GateStatus | None,
    ) -> GateStatus:
        """
        Missing Hard Gate data is UNKNOWN,
        never an implicit PASS.
        """

        if status is None:
            return GateStatus.UNKNOWN

        if not isinstance(
            status,
            GateStatus,
         ):
            raise HardGateError(
                "Hard Gate status must be "
                "GateStatus or None."
            )

        return status

    @staticmethod
    def _validate_price_action_confirmation(
        result: PriceActionConfirmationResult,
    ) -> None:
        if not isinstance(
            result,
            PriceActionConfirmationResult,
        ):
            raise HardGateError(
                "price_action_confirmation must be "
                "PriceActionConfirmationResult."
            )

        if (
            result.status
            in (
                GateStatus.PASS,
                GateStatus.FAIL,
            )
            and not result.is_final
        ):
            raise HardGateError(
                "Price Action PASS/FAIL must be final. "
                "Non-final confirmation-window state "
                "must be UNKNOWN."
            )

        if result.evaluations_seen < 0:
            raise HardGateError(
                "evaluations_seen cannot be negative."
            )

        if result.pass_evaluations < 0:
            raise HardGateError(
                "pass_evaluations cannot be negative."
            )

        if result.fail_evaluations < 0:
            raise HardGateError(
                "fail_evaluations cannot be negative."
            )

        if result.unknown_evaluations < 0:
            raise HardGateError(
                "unknown_evaluations cannot be negative."
            )

        total_counted = (
            result.pass_evaluations
            + result.fail_evaluations
            + result.unknown_evaluations
        )

        if total_counted != result.evaluations_seen:
            raise HardGateError(
                "Price Action evaluation counters "
                "must sum to evaluations_seen."
            )

