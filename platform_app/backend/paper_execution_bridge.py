from __future__ import annotations

from datetime import datetime, timezone

from weekly.db.position_repository import PositionRepository
from weekly.db.trade_repository import TradeRepository
from weekly.providers.weekly_provider_factory import (
    build_weekly_providers,
)
from weekly.services.paper_execution_preparation_service import (
    PaperExecutionPreparationService,
)
from weekly.services.weekly_runtime_factory import (
    build_weekly_runtime_services,
)


def _build_preparation_service(*, include_options_provider: bool):
    runtime = build_weekly_runtime_services()

    options_provider = None

    if include_options_provider:
        providers = build_weekly_providers()
        options_provider = providers.options

    return PaperExecutionPreparationService(
        signal_repository=runtime.signal_repository,
        signal_feature_repository=runtime.feature_repository,
        position_repository=PositionRepository(),
        trade_repository=TradeRepository(),
        options_provider=options_provider,
    )


def prepare_entry(*, signal_id: int, quantity: int):
    service = _build_preparation_service(
        include_options_provider=False
    )

    return service.prepare(
        signal_id=signal_id,
        quantity=quantity,
        requested_at=datetime.now(timezone.utc),
    )


def prepare_exit(*, position_id: int):
    service = _build_preparation_service(
        include_options_provider=True
    )

    return service.prepare_close(
        position_id=position_id,
        requested_at=datetime.now(timezone.utc),
    )
