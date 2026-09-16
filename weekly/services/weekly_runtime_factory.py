from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import (
    load_weekly_config,
)

from weekly.db.flow_snapshot_repository import (
    FlowSnapshotRepository,
)
from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.db.signal_repository import (
    SignalRepository,
)

from weekly.services.atr_evaluation_service import (
    ATREvaluationService,
)
from weekly.services.atr_service import (
    ATRService,
    ATRSettings,
)
from weekly.services.candidate_service import (
    CandidateService,
)
from weekly.services.earnings_event_risk_evaluation_service import (
    EarningsEventRiskEvaluationService,
)
from weekly.services.earnings_event_risk_service import (
    EarningsEventRiskService,
)
from weekly.services.efficiency_ratio_service import (
    EfficiencyRatioService,
    EfficiencyRatioSettings,
)
from weekly.services.eligible_contract_evaluation_service import (
    EligibleContractEvaluationService,
)
from weekly.services.eligible_contract_service import (
    ContractSelectorSettings,
    EligibleContractService,
)
from weekly.services.expected_move_evaluation_service import (
    ExpectedMoveEvaluationService,
)
from weekly.services.expected_move_service import (
    ExpectedMoveService,
)
from weekly.services.hard_gate_service import (
    HardGateService,
)
from weekly.services.market_data_window_service import (
    MarketDataWindowService,
)
from weekly.services.atm_iv_resolver import (
    ATMIVResolver,
)
from weekly.services.market_regime_evaluation_service import (
    MarketRegimeEvaluationService,
)
from weekly.services.price_action_confirmation_service import (
    PriceActionConfirmationService,
)
from weekly.services.price_action_evaluation_service import (
    PriceActionEvaluationService,
)
from weekly.services.price_action_input_service import (
    PriceActionInputService,
)
from weekly.services.price_action_service import (
    PriceActionService,
)
from weekly.services.quality_evidence_evaluation_service import (
    QualityEvidenceEvaluationService,
)
from weekly.services.quality_evidence_service import (
    QualityEvidenceService,
    QualityEvidenceSettings,
)
from weekly.services.quality_scoring_evaluation_service import (
    QualityScoringEvaluationService,
)
from weekly.services.rearm_service import (
    ReArmService,
)
from weekly.services.rearm_price_action_trigger_service import (
    ReArmPriceActionTriggerService,
)
from weekly.services.quality_scoring_service import (
    QualityScoringService,
    QualityScoringSettings,
)
from weekly.services.signal_invalidation_service import (
    SignalInvalidationService,
)
from weekly.services.signal_resolution_orchestrator import (
    SignalResolutionOrchestrator,
)
from weekly.services.signal_state_transition_service import (
    SignalStateTransitionService,
)
from weekly.services.weekly_vwap_service import (
    WeeklyVWAPService,
)


@dataclass(frozen=True)
class WeeklyRuntimeServices:
    config: dict[str, Any]
    config_hash: str

    signal_repository: SignalRepository
    feature_repository: SignalFeatureRepository
    flow_snapshot_repository: FlowSnapshotRepository

    candidate_service: CandidateService
    rearm_service: ReArmService
    rearm_price_action_trigger_service: ReArmPriceActionTriggerService
    signal_invalidation_service: SignalInvalidationService

    atr_service: ATRService
    atr_evaluation_service: ATREvaluationService

    weekly_vwap_service: WeeklyVWAPService
    efficiency_ratio_service: EfficiencyRatioService
    market_regime_evaluation_service: (
        MarketRegimeEvaluationService
    )

    price_action_service: PriceActionService
    price_action_input_service: PriceActionInputService
    price_action_evaluation_service: (
        PriceActionEvaluationService
    )
    price_action_confirmation_service: (
        PriceActionConfirmationService
    )

    market_data_window_service: MarketDataWindowService
    atm_iv_resolver: ATMIVResolver

    expected_move_service: ExpectedMoveService
    expected_move_evaluation_service: (
        ExpectedMoveEvaluationService
    )

    eligible_contract_service: EligibleContractService
    eligible_contract_evaluation_service: (
        EligibleContractEvaluationService
    )

    earnings_event_risk_service: EarningsEventRiskService
    earnings_event_risk_evaluation_service: (
        EarningsEventRiskEvaluationService
    )

    quality_evidence_service: QualityEvidenceService
    quality_evidence_evaluation_service: (
        QualityEvidenceEvaluationService
    )

    quality_scoring_service: QualityScoringService
    quality_scoring_evaluation_service: (
        QualityScoringEvaluationService
    )

    hard_gate_service: HardGateService
    transition_service: SignalStateTransitionService
    resolution_orchestrator: SignalResolutionOrchestrator


def build_weekly_runtime_services() -> WeeklyRuntimeServices:
    config = load_weekly_config(
        require_runtime_ready=True
    )

    config_hash = str(config["_meta"]["config_hash"])

    signal_repository = SignalRepository()
    feature_repository = SignalFeatureRepository()
    flow_snapshot_repository = (
        FlowSnapshotRepository()
    )

    candidate_service = CandidateService(
        repository=signal_repository
    )

    rearm_service = ReArmService()

    signal_invalidation_service = (
        SignalInvalidationService()
    )

    atr_service = ATRService(
        ATRSettings.from_config()
    )

    atr_evaluation_service = (
        ATREvaluationService(
            atr_service=atr_service,
            feature_repository=(
                feature_repository
            ),
        )
    )

    weekly_vwap_service = WeeklyVWAPService()

    efficiency_ratio_service = (
        EfficiencyRatioService(
            EfficiencyRatioSettings.from_config()
        )
    )

    market_regime_evaluation_service = (
        MarketRegimeEvaluationService(
            weekly_vwap_service=(
                weekly_vwap_service
            ),
            efficiency_ratio_service=(
                efficiency_ratio_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    price_action_service = (
        PriceActionService.from_weekly_config(
            config
        )
    )

    rearm_price_action_trigger_service = (
        ReArmPriceActionTriggerService(
            price_action_service=price_action_service
        )
    )

    price_action_input_service = (
        PriceActionInputService(
            participation_lookback_sessions=(
                price_action_service
                .settings
                .participation_rvol_lookback_sessions
            )
        )
    )

    price_action_evaluation_service = (
        PriceActionEvaluationService(
            price_action_service=(
                price_action_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    price_action_confirmation_service = (
        PriceActionConfirmationService()
    )

    market_data_window_service = (
        MarketDataWindowService()
    )

    atm_iv_resolver = ATMIVResolver()

    expected_move_service = (
        ExpectedMoveService()
    )

    expected_move_evaluation_service = (
        ExpectedMoveEvaluationService(
            expected_move_service=(
                expected_move_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    eligible_contract_service = (
        EligibleContractService(
            settings=(
                ContractSelectorSettings
                .from_config()
            )
        )
    )

    eligible_contract_evaluation_service = (
        EligibleContractEvaluationService(
            eligible_contract_service=(
                eligible_contract_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    earnings_event_risk_service = (
        EarningsEventRiskService()
    )

    earnings_event_risk_evaluation_service = (
        EarningsEventRiskEvaluationService(
            earnings_event_risk_service=(
                earnings_event_risk_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    quality_evidence_service = (
        QualityEvidenceService(
            settings=(
                QualityEvidenceSettings
                .from_config()
            )
        )
    )

    quality_evidence_evaluation_service = (
        QualityEvidenceEvaluationService(
            quality_evidence_service=(
                quality_evidence_service
            ),
            signal_repository=(
                signal_repository
            ),
            flow_snapshot_repository=(
                flow_snapshot_repository
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    quality_scoring_service = (
        QualityScoringService(
            settings=(
                QualityScoringSettings
                .from_config()
            )
        )
    )

    quality_scoring_evaluation_service = (
        QualityScoringEvaluationService(
            quality_scoring_service=(
                quality_scoring_service
            ),
            feature_repository=(
                feature_repository
            ),
        )
    )

    hard_gate_service = HardGateService()

    transition_service = (
        SignalStateTransitionService(
            signal_repository=(
                signal_repository
            )
        )
    )

    resolution_orchestrator = (
        SignalResolutionOrchestrator(
            signal_repository=(
                signal_repository
            ),
            feature_repository=(
                feature_repository
            ),
            price_action_confirmation_service=(
                price_action_confirmation_service
            ),
            hard_gate_service=(
                hard_gate_service
            ),
            transition_service=(
                transition_service
            ),
        )
    )

    return WeeklyRuntimeServices(
        config=config,
        config_hash=config_hash,

        signal_repository=signal_repository,
        feature_repository=feature_repository,
        flow_snapshot_repository=(
            flow_snapshot_repository
        ),

        candidate_service=candidate_service,
        rearm_service=rearm_service,
        rearm_price_action_trigger_service=rearm_price_action_trigger_service,
        signal_invalidation_service=(
            signal_invalidation_service
        ),

        atr_service=atr_service,
        atr_evaluation_service=(
            atr_evaluation_service
        ),

        weekly_vwap_service=(
            weekly_vwap_service
        ),
        efficiency_ratio_service=(
            efficiency_ratio_service
        ),
        market_regime_evaluation_service=(
            market_regime_evaluation_service
        ),

        price_action_service=(
            price_action_service
        ),
        price_action_input_service=(
            price_action_input_service
        ),
        price_action_evaluation_service=(
            price_action_evaluation_service
        ),
        price_action_confirmation_service=(
            price_action_confirmation_service
        ),

        market_data_window_service=(
            market_data_window_service
        ),
        atm_iv_resolver=atm_iv_resolver,

        expected_move_service=(
            expected_move_service
        ),
        expected_move_evaluation_service=(
            expected_move_evaluation_service
        ),

        eligible_contract_service=(
            eligible_contract_service
        ),
        eligible_contract_evaluation_service=(
            eligible_contract_evaluation_service
        ),

        earnings_event_risk_service=(
            earnings_event_risk_service
        ),
        earnings_event_risk_evaluation_service=(
            earnings_event_risk_evaluation_service
        ),

        quality_evidence_service=(
            quality_evidence_service
        ),
        quality_evidence_evaluation_service=(
            quality_evidence_evaluation_service
        ),

        quality_scoring_service=(
            quality_scoring_service
        ),
        quality_scoring_evaluation_service=(
            quality_scoring_evaluation_service
        ),

        hard_gate_service=(
            hard_gate_service
        ),
        transition_service=(
            transition_service
        ),
        resolution_orchestrator=(
            resolution_orchestrator
        ),
    )


