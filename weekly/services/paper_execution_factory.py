from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from weekly.db.position_repository import PositionRepository
from weekly.db.trade_repository import TradeRepository
from weekly.providers.weekly_provider_factory import WeeklyProviders
from weekly.services.paper_execution_coordinator import (
    PaperExecutionCoordinator,
)
from weekly.services.paper_execution_fill_service import (
    PaperExecutionFillService,
)
from weekly.services.paper_execution_lifecycle_service import (
    PaperExecutionLifecycleService,
)
from weekly.services.paper_execution_preparation_service import (
    PaperExecutionPreparationService,
)
from weekly.services.paper_execution_recovery_service import (
    PaperExecutionRecoveryService,
)
from weekly.services.paper_execution_signal_selector import (
    PaperExecutionSignalSelector,
)
from weekly.services.paper_order_submission_service import (
    PaperOrderSubmissionService,
)
from weekly.services.paper_order_sync_service import (
    PaperOrderSyncService,
)
from weekly.services.signal_alert_service import (
    SignalAlert,
    SignalAlertService,
)
from weekly.services.signal_operational_transition_service import (
    SignalOperationalTransitionService,
)
from weekly.services.weekly_runtime_factory import (
    WeeklyRuntimeServices,
)


@dataclass(frozen=True)
class PaperExecutionServices:
    position_repository: PositionRepository
    trade_repository: TradeRepository

    signal_selector: PaperExecutionSignalSelector
    preparation_service: PaperExecutionPreparationService

    order_submission_service: PaperOrderSubmissionService
    order_sync_service: PaperOrderSyncService

    fill_service: PaperExecutionFillService
    lifecycle_service: PaperExecutionLifecycleService
    recovery_service: PaperExecutionRecoveryService
    coordinator: PaperExecutionCoordinator

    operational_transition_service: (
        SignalOperationalTransitionService
    )
    signal_alert_service: SignalAlertService


def build_paper_execution_services(
    *,
    runtime_services: WeeklyRuntimeServices,
    providers: WeeklyProviders,
    signal_alert_sender: Callable[[SignalAlert], None],
) -> PaperExecutionServices:
    """
    Build PAPER-only execution infrastructure.

    Construction does not submit orders and does not
    transition any Signal state.

    PaperOrderSubmissionService itself enforces that
    the supplied Alpaca TradingClient is a PAPER client.
    """

    position_repository = PositionRepository()
    trade_repository = TradeRepository()

    signal_selector = PaperExecutionSignalSelector()

    preparation_service = (
        PaperExecutionPreparationService(
            signal_repository=(
                runtime_services.signal_repository
            ),
            signal_feature_repository=(
                runtime_services.feature_repository
            ),
            position_repository=position_repository,
            trade_repository=trade_repository,
            options_provider=getattr(providers, "options", None),
        )
    )

    order_submission_service = (
        PaperOrderSubmissionService(
            trading_client=providers.trading_client,
            trade_repository=trade_repository,
        )
    )

    order_sync_service = PaperOrderSyncService(
        trading_client=providers.trading_client,
        trade_repository=trade_repository,
    )

    fill_service = PaperExecutionFillService(
        trade_repository=trade_repository,
        position_repository=position_repository,
    )

    lifecycle_service = (
        PaperExecutionLifecycleService(
            order_sync_service=order_sync_service,
            fill_service=fill_service,
        )
    )

    recovery_service = (
        PaperExecutionRecoveryService(
            trade_repository=trade_repository,
            lifecycle_service=lifecycle_service,
            fill_service=fill_service,
        )
    )

    coordinator = PaperExecutionCoordinator(
        signal_selector=signal_selector,
        recovery_service=recovery_service,
        position_repository=position_repository,
        trade_repository=trade_repository,
    )

    operational_transition_service = (
        SignalOperationalTransitionService(
            signal_repository=(
                runtime_services.signal_repository
            )
        )
    )

    signal_alert_service = SignalAlertService(
        signal_repository=(
            runtime_services.signal_repository
        ),
        feature_repository=(
            runtime_services.feature_repository
        ),
        transition_service=(
            operational_transition_service
        ),
        sender=signal_alert_sender,
    )

    return PaperExecutionServices(
        position_repository=position_repository,
        trade_repository=trade_repository,
        signal_selector=signal_selector,
        preparation_service=preparation_service,
        order_submission_service=(
            order_submission_service
        ),
        order_sync_service=order_sync_service,
        fill_service=fill_service,
        lifecycle_service=lifecycle_service,
        recovery_service=recovery_service,
        coordinator=coordinator,
        operational_transition_service=(
            operational_transition_service
        ),
        signal_alert_service=signal_alert_service,
    )
