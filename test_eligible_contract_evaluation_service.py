from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import weekly.db.database as dbmod
from weekly.db.signal_feature_repository import SignalFeatureRepository
from weekly.db.signal_repository import SignalRepository
from weekly.domain.enums import Direction, GateStatus, OptionRight, SignalState
from weekly.domain.models import Signal, SignalFeature
from weekly.services.eligible_contract_evaluation_service import EligibleContractEvaluationService
from weekly.services.eligible_contract_service import (
    ContractSelectorSettings,
    EligibleContractService,
    OptionContractCandidate,
)


def h(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def settings() -> ContractSelectorSettings:
    return ContractSelectorSettings(
        delta_min=0.35,
        delta_max=0.65,
        max_spread_pct=0.12,
        max_quote_age_seconds=60,
        standard_contract_size=100,
        require_standard_contract=True,
        require_tradable_contract=True,
        max_budget=5000.0,
        target_abs_delta=0.50,
    )


def main() -> None:
    prod = dbmod.get_database_path().resolve()
    if not prod.exists():
        raise RuntimeError(f"Production database not found: {prod}")
    before = h(prod)

    with tempfile.TemporaryDirectory(prefix="weekly_eligible_contract_eval_test_") as td:
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
            trading_date = date(2099, 1, 5)
            expiry = date(2099, 1, 9)
            as_of = datetime(2099, 1, 5, 15, 0, tzinfo=timezone.utc)

            seq = sr.next_candidate_sequence(
                strategy_version="weekly_v1",
                ticker="AAPL",
                trading_date_et=trading_date,
                target_expiry=expiry,
                direction=Direction.BULLISH,
            )
            sig = sr.create(Signal(
                strategy_version="weekly_v1",
                config_hash="eligible-contract-eval-temp-test",
                ticker="AAPL",
                trading_date_et=trading_date,
                target_expiry=expiry,
                direction=Direction.BULLISH,
                candidate_sequence=seq,
                state=SignalState.CANDIDATE,
                candidate_at=datetime(2099, 1, 5, 14, 35, tzinfo=timezone.utc),
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
                captured_at=datetime(2099, 1, 5, 14, 50, tzinfo=timezone.utc),
                flow_net=650000.0,
                flow_threshold=500000.0,
                weekly_vwap=198.0,
                underlying_price=200.0,
                vwap_status=GateStatus.PASS,
                efficiency_ratio=0.55,
                efficiency_ratio_status=GateStatus.PASS,
                expected_move=10.0,
                expected_move_perc=0.05,
                structure_status=GateStatus.PASS,
                impulse_status=GateStatus.FAIL,
                participation_status=GateStatus.PASS,
                price_action_pass_count=2,
                price_action_status=GateStatus.PASS,
                atr_1h=3.25,
                atr_15m=2.25,
            ))

            contracts = (
                OptionContractCandidate(
                    symbol="AAPL990109C00200000",
                    underlying_symbol="AAPL",
                    root_symbol="AAPL",
                    expiry=expiry,
                    right=OptionRight.CALL,
                    strike=200.0,
                    active=True,
                    tradable=True,
                    size=100,
                    bid=9.50,
                    ask=10.00,
                    quote_at=as_of - timedelta(seconds=20),
                    delta=0.50,
                    gamma=0.05,
                    theta=-0.12,
                    vega=0.20,
                    iv=0.40,
                ),
                OptionContractCandidate(
                    symbol="AAPL990109C00201000",
                    underlying_symbol="AAPL",
                    root_symbol="AAPL",
                    expiry=expiry,
                    right=OptionRight.CALL,
                    strike=201.0,
                    active=True,
                    tradable=True,
                    size=100,
                    bid=9.70,
                    ask=9.90,
                    quote_at=as_of - timedelta(seconds=20),
                    delta=0.48,
                    gamma=0.04,
                    theta=-0.11,
                    vega=0.19,
                    iv=0.39,
                ),
            )

            svc = EligibleContractEvaluationService(
                eligible_contract_service=EligibleContractService(settings=settings()),
                feature_repository=fr,
            )
            ev = svc.evaluate_and_persist(
                signal_id=sig.id,
                direction=Direction.BULLISH,
                target_expiry=expiry,
                as_of=as_of,
                contracts=contracts,
                captured_at=datetime(2099, 1, 5, 15, 1, tzinfo=timezone.utc),
            )
            f = ev.feature

            assert ev.result.status is GateStatus.PASS
            assert ev.result.selected is not None
            assert ev.result.selected.symbol == "AAPL990109C00200000"
            assert f.id is not None and f.id != prior.id
            assert f.evaluation_sequence == 2
            assert f.eligible_contract_status is GateStatus.PASS
            assert f.selected_contract_symbol == "AAPL990109C00200000"
            assert f.selected_contract_right is OptionRight.CALL
            assert f.selected_contract_strike == 200.0
            assert f.selected_contract_bid == 9.50
            assert f.selected_contract_ask == 10.00
            assert abs(f.selected_contract_mark - 9.75) < 1e-12
            assert f.selected_contract_delta == 0.50
            assert f.selected_contract_gamma == 0.05
            assert f.selected_contract_theta == -0.12
            assert f.selected_contract_vega == 0.20
            assert f.selected_contract_iv == 0.40
            assert f.selected_contract_spread_pct is not None
            assert f.selected_contract_quote_age_seconds == 20.0
            assert f.underlying_price == 200.0
            assert f.expected_move == 10.0
            assert f.expected_move_perc == 0.05
            assert f.flow_net == 650000.0
            assert f.flow_threshold == 500000.0
            assert f.weekly_vwap == 198.0
            assert f.vwap_status is GateStatus.PASS
            assert f.efficiency_ratio == 0.55
            assert f.efficiency_ratio_status is GateStatus.PASS
            assert f.structure_status is GateStatus.PASS
            assert f.impulse_status is GateStatus.FAIL
            assert f.participation_status is GateStatus.PASS
            assert f.price_action_pass_count == 2
            assert f.price_action_status is GateStatus.PASS
            assert f.atr_1h == 3.25
            assert f.atr_15m == 2.25

            latest = fr.get_latest_for_signal(sig.id)
            assert latest is not None and latest.id == f.id
            assert latest.selected_contract_symbol == "AAPL990109C00200000"
            assert latest.eligible_contract_status is GateStatus.PASS

            reloaded = sr.get_by_id(sig.id)
            assert reloaded is not None and reloaded.state is SignalState.CANDIDATE
        finally:
            dbmod.get_database_path = old

    assert before == h(prod)
    print("1. temporary database copy: PASS")
    print("2. eligible contract Hard Gate PASS persisted: PASS")
    print("3. selected contract + Greeks/quote evidence persisted: PASS")
    print("4. ranking selected closest |Delta| 0.50 contract: PASS")
    print("5. evaluation_sequence incremented: PASS")
    print("6. Expected Move + underlying preserved: PASS")
    print("7. unrelated Flow/Regime/PA/ATR fields preserved: PASS")
    print("8. latest SignalFeature reload: PASS")
    print("9. Signal state unchanged: PASS")
    print("10. production database unchanged: PASS")
    print()
    print("=" * 70)
    print("ELIGIBLE CONTRACT EVALUATION SERVICE: PASS 10/10")
    print("=" * 70)


if __name__ == "__main__":
    main()
