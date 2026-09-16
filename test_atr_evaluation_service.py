from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import weekly.db.database as dbmod
from weekly.db.signal_feature_repository import (
    SignalFeatureRepository,
)
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import (
    Direction,
    GateStatus,
    SignalState,
)
from weekly.domain.models import Signal, SignalFeature
from weekly.services.atr_evaluation_service import (
    ATREvaluationService,
)
from weekly.services.atr_service import (
    ATRService,
    ATRSettings,
)

ET = ZoneInfo("America/New_York")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def session(day):
    return SimpleNamespace(
        date=day,
        open=datetime(
            day.year,
            day.month,
            day.day,
            9,
            30,
            tzinfo=ET,
        ),
        close=datetime(
            day.year,
            day.month,
            day.day,
            16,
            0,
            tzinfo=ET,
        ),
    )


def minute_bar(start_at, price):
    return SimpleNamespace(
        start_at=start_at,
        end_at=start_at + timedelta(minutes=1),
        open=price,
        high=price + 0.5,
        low=price - 0.5,
        close=price,
        volume=100.0,
    )


def minute_series(sessions, drift=0.01):
    bars = []
    price = 100.0

    for current_session in sessions:
        current = current_session.open

        while current < current_session.close:
            bars.append(
                minute_bar(
                    current,
                    price,
                )
            )
            price += drift
            current += timedelta(minutes=1)

    return bars


def main():
    prod = dbmod.get_database_path().resolve()

    if not prod.exists():
        raise RuntimeError(
            f"Production database not found: {prod}"
        )

    before = sha256_file(prod)

    with tempfile.TemporaryDirectory(
        prefix="weekly_atr_eval_test_"
    ) as td:
        temp_db = Path(td) / "weekly_trading_test.db"

        src = sqlite3.connect(
            f"{prod.as_uri()}?mode=ro",
            uri=True,
        )
        dst = sqlite3.connect(temp_db)

        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        original_get_database_path = (
            dbmod.get_database_path
        )
        dbmod.get_database_path = lambda: temp_db

        try:
            signal_repository = SignalRepository()
            feature_repository = (
                SignalFeatureRepository()
            )

            trading_date = date(2099, 1, 7)
            target_expiry = date(2099, 1, 9)

            candidate_sequence = (
                signal_repository
                .next_candidate_sequence(
                    strategy_version="weekly_v1",
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=target_expiry,
                    direction=Direction.BULLISH,
                )
            )

            signal = signal_repository.create(
                Signal(
                    strategy_version="weekly_v1",
                    config_hash="atr-eval-temp-test",
                    ticker="AAPL",
                    trading_date_et=trading_date,
                    target_expiry=target_expiry,
                    direction=Direction.BULLISH,
                    candidate_sequence=(
                        candidate_sequence
                    ),
                    state=SignalState.CANDIDATE,
                    candidate_at=datetime(
                        2099,
                        1,
                        7,
                        10,
                        0,
                        tzinfo=ET,
                    ),
                    net_flow_at_candidate=(
                        800_000.0
                    ),
                    flow_dedup_level=(
                        "alert_uuid"
                    ),
                    scenario_return_enabled=False,
                )
            )

            previous = feature_repository.create(
                SignalFeature(
                    signal_id=signal.id,
                    evaluation_sequence=1,
                    captured_at=datetime(
                        2099,
                        1,
                        7,
                        12,
                        0,
                        tzinfo=ET,
                    ),
                    underlying_price=204.0,
                    weekly_vwap=200.0,
                    vwap_status=GateStatus.PASS,
                    efficiency_ratio=0.55,
                    efficiency_ratio_status=(
                        GateStatus.PASS
                    ),
                )
            )

            sessions = [
                session(date(2099, 1, 5)),
                session(date(2099, 1, 6)),
                session(date(2099, 1, 7)),
            ]

            minute_bars = minute_series(
                sessions
            )

            as_of = datetime(
                2099,
                1,
                7,
                13,
                7,
                tzinfo=ET,
            )

            service = ATREvaluationService(
                atr_service=ATRService(
                    ATRSettings(
                        atr_1h_period=14,
                        atr_15m_period=14,
                    )
                ),
                feature_repository=(
                    feature_repository
                ),
            )

            evaluation = (
                service.evaluate_and_persist(
                    signal_id=signal.id,
                    as_of=as_of,
                    trading_date_et=(
                        trading_date
                    ),
                    calendar=sessions,
                    minute_bars=minute_bars,
                    captured_at=as_of,
                )
            )

            result = evaluation.result
            feature = evaluation.feature

            assert result.atr_1h is not None
            assert result.atr_15m is not None
            assert (
                result.atr_1h_reason
                == "ATR_AVAILABLE"
            )
            assert (
                result.atr_15m_reason
                == "ATR_AVAILABLE"
            )

            assert feature.id is not None
            assert feature.id != previous.id
            assert (
                feature.evaluation_sequence
                == 2
            )

            assert (
                feature.atr_1h
                == result.atr_1h
            )
            assert (
                feature.atr_15m
                == result.atr_15m
            )

            assert (
                feature.underlying_price
                == 204.0
            )
            assert (
                feature.weekly_vwap
                == 200.0
            )
            assert (
                feature.vwap_status
                is GateStatus.PASS
            )
            assert (
                feature.efficiency_ratio
                == 0.55
            )
            assert (
                feature.efficiency_ratio_status
                is GateStatus.PASS
            )

            latest = (
                feature_repository
                .get_latest_for_signal(
                    signal.id
                )
            )

            assert latest is not None
            assert latest.id == feature.id
            assert (
                latest.atr_1h
                == result.atr_1h
            )
            assert (
                latest.atr_15m
                == result.atr_15m
            )

            reloaded_signal = (
                signal_repository.get_by_id(
                    signal.id
                )
            )

            assert reloaded_signal is not None
            assert (
                reloaded_signal.state
                is SignalState.CANDIDATE
            )

        finally:
            dbmod.get_database_path = (
                original_get_database_path
            )

    assert before == sha256_file(prod)

    print("1. temporary database copy: PASS")
    print("2. ATR 1H calculated: PASS")
    print("3. ATR 15m calculated: PASS")
    print("4. immutable SignalFeature snapshot persisted: PASS")
    print("5. unrelated feature evidence preserved: PASS")
    print("6. latest SignalFeature reload: PASS")
    print("7. Signal state unchanged: PASS")
    print("8. production database unchanged: PASS")

    print()
    print("=" * 70)
    print("ATR EVALUATION SERVICE: PASS 8/8")
    print("=" * 70)


if __name__ == "__main__":
    main()
