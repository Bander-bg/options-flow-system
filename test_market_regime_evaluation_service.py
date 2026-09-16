from __future__ import annotations

import hashlib, sqlite3, tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import weekly.db.database as dbmod
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, SignalState
from weekly.domain.models import Signal, SignalFeature
from weekly.providers.alpaca_stock_provider import StockMinuteBar
from weekly.services.efficiency_ratio_service import EfficiencyRatioService, EfficiencyRatioSettings
from weekly.services.market_regime_evaluation_service import MarketRegimeEvaluationService
from weekly.services.weekly_vwap_service import WeeklyVWAPService

ET = ZoneInfo("America/New_York")

@dataclass(frozen=True)
class S:
    date: date
    open: datetime
    close: datetime

def h(p: Path) -> str:
    x = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            x.update(c)
    return x.hexdigest()

def session(d: date) -> S:
    return S(
        d,
        datetime(d.year,d.month,d.day,9,30,tzinfo=ET),
        datetime(d.year,d.month,d.day,16,0,tzinfo=ET),
    )

def bars(d: date) -> list[StockMinuteBar]:
    start = datetime(d.year,d.month,d.day,9,30,tzinfo=ET)
    starts = [99.0,100.0,102.0,104.0]
    ends = [100.0,102.0,104.0,106.0]
    out = []
    for hour in range(4):
        for minute in range(60):
            frac = minute / 59
            px = starts[hour] + (ends[hour] - starts[hour]) * frac
            t = start + timedelta(hours=hour, minutes=minute)
            out.append(StockMinuteBar(
                start_at=t,
                end_at=t + timedelta(minutes=1),
                open=px,
                high=px + 0.1,
                low=px - 0.1,
                close=px,
                volume=100.0,
                vwap=px,
            ))
    return out

def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")
    before = h(prod)

    with tempfile.TemporaryDirectory(prefix="weekly_market_regime_test_") as td:
        temp_db = Path(td) / "weekly_trading_test.db"
        src = sqlite3.connect(f"{prod.as_uri()}?mode=ro", uri=True)
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        old = dbmod.get_database_path
        dbmod.get_database_path = lambda: temp_db
        try:
            sr = SignalRepository()
            fr = SignalFeatureRepository()
            d = date(2099,1,5)
            expiry = date(2099,1,9)
            seq = sr.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=d,
                target_expiry=expiry,
                direction=Direction.BULLISH,
            )
            sig = sr.create(Signal(
                strategy_version="weekly_v1",
                config_hash="market-regime-temp-test",
                ticker="AAPL",
                trading_date_et=d,
                target_expiry=expiry,
                direction=Direction.BULLISH,
                candidate_sequence=seq,
                state=SignalState.CANDIDATE,
                candidate_at=datetime(2099,1,5,14,35,tzinfo=timezone.utc),
                net_flow_at_candidate=650000.0,
                flow_dedup_level="alert_uuid",
                stock_data_provider="ALPACA",
                stock_data_feed="IEX",
                options_data_provider="ALPACA",
                options_data_feed="INDICATIVE",
                scenario_return_enabled=False,
            ))
            prior = fr.create(SignalFeature(
                signal_id=sig.id,
                evaluation_sequence=1,
                captured_at=datetime(2099,1,5,16,0,tzinfo=timezone.utc),
                flow_net=650000.0,
                flow_threshold=500000.0,
                structure_status=GateStatus.PASS,
                impulse_status=GateStatus.FAIL,
                participation_status=GateStatus.PASS,
                price_action_pass_count=2,
                price_action_status=GateStatus.PASS,
                atr_15m=2.25,
            ))

            svc = MarketRegimeEvaluationService(
                weekly_vwap_service=WeeklyVWAPService(),
                efficiency_ratio_service=EfficiencyRatioService(
                    settings=EfficiencyRatioSettings(minimum_er=0.30, min_er_bars=4)
                ),
                feature_repository=fr,
            )
            ev = svc.evaluate_and_persist(
                signal_id=sig.id,
                direction=Direction.BULLISH,
                as_of=datetime(2099,1,5,13,30,tzinfo=ET),
                trading_date_et=d,
                calendar=[session(d)],
                minute_bars=bars(d),
                captured_at=datetime(2099,1,5,18,31,tzinfo=timezone.utc),
            )
            f = ev.feature

            assert f.id is not None and f.id != prior.id
            assert f.evaluation_sequence == 2
            assert f.weekly_vwap is not None
            assert f.underlying_price == 106.0
            assert f.vwap_status is GateStatus.PASS
            assert abs(f.efficiency_ratio - 1.0) < 1e-12
            assert f.efficiency_ratio_status is GateStatus.PASS
            assert f.flow_net == 650000.0 and f.flow_threshold == 500000.0
            assert f.structure_status is GateStatus.PASS
            assert f.impulse_status is GateStatus.FAIL
            assert f.participation_status is GateStatus.PASS
            assert f.price_action_pass_count == 2
            assert f.price_action_status is GateStatus.PASS
            assert f.atr_15m == 2.25

            latest = fr.get_latest_for_signal(sig.id)
            assert latest is not None and latest.id == f.id
            assert latest.weekly_vwap == f.weekly_vwap
            assert latest.efficiency_ratio == f.efficiency_ratio
            reloaded = sr.get_by_id(sig.id)
            assert reloaded is not None and reloaded.state is SignalState.CANDIDATE
        finally:
            dbmod.get_database_path = old

    assert before == h(prod)

    print("1. temporary database copy: PASS")
    print("2. VWAP + ER persisted in one snapshot: PASS")
    print("3. evaluation_sequence incremented: PASS")
    print("4. existing Flow fields preserved: PASS")
    print("5. existing Price Action fields preserved: PASS")
    print("6. latest SignalFeature reload: PASS")
    print("7. Signal state unchanged: PASS")
    print("8. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("MARKET REGIME EVALUATION: PASS 8/8")
    print("=" * 70)

if __name__ == "__main__":
    main()

