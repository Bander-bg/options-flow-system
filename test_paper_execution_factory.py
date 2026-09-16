from __future__ import annotations

from types import SimpleNamespace

from weekly.services.paper_execution_coordinator import (
    PaperExecutionCoordinator,
)
from weekly.services.paper_execution_factory import (
    build_paper_execution_services,
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
    SignalAlertService,
)
from weekly.services.signal_operational_transition_service import (
    SignalOperationalTransitionService,
)


def main() -> None:
    signal_repository = object()
    feature_repository = object()

    runtime_services = SimpleNamespace(
        signal_repository=signal_repository,
        feature_repository=feature_repository,
    )

    trading_client = SimpleNamespace(
        _sandbox=True,
    )

    providers = SimpleNamespace(
        trading_client=trading_client,
    )

    sent_alerts = []

    services = build_paper_execution_services(
        runtime_services=runtime_services,
        providers=providers,
        signal_alert_sender=sent_alerts.append,
    )

    assert isinstance(
        services.signal_selector,
        PaperExecutionSignalSelector,
    )

    assert isinstance(
        services.preparation_service,
        PaperExecutionPreparationService,
    )

    assert isinstance(
        services.order_submission_service,
        PaperOrderSubmissionService,
    )

    assert isinstance(
        services.order_sync_service,
        PaperOrderSyncService,
    )

    assert isinstance(
        services.fill_service,
        PaperExecutionFillService,
    )

    assert isinstance(
        services.lifecycle_service,
        PaperExecutionLifecycleService,
    )

    assert isinstance(
        services.recovery_service,
        PaperExecutionRecoveryService,
    )

    assert isinstance(
        services.operational_transition_service,
        SignalOperationalTransitionService,
    )

    assert isinstance(
        services.coordinator,
        PaperExecutionCoordinator,
    )

    assert isinstance(
        services.signal_alert_service,
        SignalAlertService,
    )

    assert (
        services.coordinator.signal_selector
        is services.signal_selector
    )

    assert (
        services.coordinator.recovery_service
        is services.recovery_service
    )

    assert (
        services.coordinator.position_repository
        is services.position_repository
    )

    assert (
        services.coordinator.trade_repository
        is services.trade_repository
    )

    assert (
        services.preparation_service.signal_repository
        is signal_repository
    )

    assert (
        services.preparation_service.signal_feature_repository
        is feature_repository
    )

    assert (
        services.preparation_service.position_repository
        is services.position_repository
    )

    assert (
        services.preparation_service.trade_repository
        is services.trade_repository
    )

    assert (
        services.order_submission_service.trade_repository
        is services.trade_repository
    )

    assert (
        services.order_sync_service.trade_repository
        is services.trade_repository
    )

    assert (
        services.fill_service.trade_repository
        is services.trade_repository
    )

    assert (
        services.fill_service.position_repository
        is services.position_repository
    )

    assert (
        services.operational_transition_service.signal_repository
        is signal_repository
    )

    assert (
        services.signal_alert_service.signal_repository
        is signal_repository
    )

    assert (
        services.signal_alert_service.feature_repository
        is feature_repository
    )

    assert (
        services.signal_alert_service.transition_service
        is services.operational_transition_service
    )

    assert (
        services.signal_alert_service.sender
        == sent_alerts.append
    )

    print(
        "PAPER EXECUTION FACTORY: PASS"
    )


if __name__ == "__main__":
    main()
