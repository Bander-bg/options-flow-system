
from weekly.domain.enums import GateStatus
from weekly.services.hard_gate_service import HardGateService, HardGateError
from weekly.services.price_action_confirmation_service import PriceActionConfirmationResult

def pa(status, is_final, reason, seen=0, p=0, f=0, u=0):
    return PriceActionConfirmationResult(
        status=status,
        is_final=is_final,
        reason=reason,
        evaluations_seen=seen,
        pass_evaluations=p,
        fail_evaluations=f,
        unknown_evaluations=u,
    )

def main():
    svc = HardGateService()

    all_pass = svc.evaluate(
        vwap_status=GateStatus.PASS,
        efficiency_ratio_status=GateStatus.PASS,
        price_action_confirmation=pa(
            GateStatus.PASS, True, "PRICE_ACTION_CONFIRMED",
            seen=1, p=1,
        ),
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
    )
    assert all_pass.status is GateStatus.PASS
    assert all_pass.ready_for_confirmation is True
    assert not all_pass.failed_gates
    assert not all_pass.unknown_gates

    fail_dominates = svc.evaluate(
        vwap_status=GateStatus.FAIL,
        efficiency_ratio_status=GateStatus.UNKNOWN,
        price_action_confirmation=pa(
            GateStatus.UNKNOWN, False, "CONFIRMATION_WINDOW_OPEN"
        ),
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
    )
    assert fail_dominates.status is GateStatus.FAIL
    assert "VWAP" in fail_dominates.failed_gates
    assert "EFFICIENCY_RATIO" in fail_dominates.unknown_gates
    assert "PRICE_ACTION" in fail_dominates.unknown_gates

    unknown = svc.evaluate(
        vwap_status=GateStatus.PASS,
        efficiency_ratio_status=GateStatus.UNKNOWN,
        price_action_confirmation=pa(
            GateStatus.PASS, True, "PRICE_ACTION_CONFIRMED",
            seen=1, p=1,
        ),
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
    )
    assert unknown.status is GateStatus.UNKNOWN
    assert unknown.has_hard_unknown is True

    window_open = svc.evaluate(
        vwap_status=GateStatus.PASS,
        efficiency_ratio_status=GateStatus.PASS,
        price_action_confirmation=pa(
            GateStatus.UNKNOWN, False, "CONFIRMATION_WINDOW_OPEN",
            seen=1, f=1,
        ),
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
    )
    assert window_open.status is GateStatus.UNKNOWN
    assert window_open.price_action_is_final is False
    assert window_open.reason == "HARD_GATE_UNKNOWN_PRICE_ACTION_WINDOW_OPEN"

    final_pa_fail = svc.evaluate(
        vwap_status=GateStatus.PASS,
        efficiency_ratio_status=GateStatus.PASS,
        price_action_confirmation=pa(
            GateStatus.FAIL, True, "CONFIRMATION_WINDOW_EXPIRED_NO_PASS",
            seen=2, f=2,
        ),
        eligible_contract_status=GateStatus.PASS,
        earnings_event_risk_status=GateStatus.PASS,
     )
    assert final_pa_fail.status is GateStatus.FAIL
    assert "PRICE_ACTION" in final_pa_fail.failed_gates

    missing = svc.evaluate(
        vwap_status=None,
        efficiency_ratio_status=GateStatus.PASS,
        price_action_confirmation=pa(
            GateStatus.PASS, True, "PRICE_ACTION_CONFIRMED",
            seen=1, p=1,
        ),
        eligible_contract_status=None,
        earnings_event_risk_status=GateStatus.PASS,
     )
    assert missing.status is GateStatus.UNKNOWN
    assert "VWAP" in missing.unknown_gates
    assert "ELIGIBLE_CONTRACT" in missing.unknown_gates

    raised = False
    try:
        svc.evaluate(
            vwap_status=GateStatus.PASS,
            efficiency_ratio_status=GateStatus.PASS,
            price_action_confirmation=pa(
                GateStatus.FAIL, False, "INVALID_NON_FINAL_FAIL",
                seen=1, f=1,
            ),
            eligible_contract_status=GateStatus.PASS,
            earnings_event_risk_status=GateStatus.PASS,
        )
    except HardGateError:
        raised = True
    assert raised

    print("1. all Hard Gates PASS: PASS")
    print("2. Hard FAIL dominates UNKNOWN: PASS")
    print("3. unresolved Hard Gate -> UNKNOWN: PASS")
    print("4. Price Action window-open FAIL is not final rejection: PASS")
    print("5. final Price Action FAIL is Hard FAIL: PASS")
    print("6. missing Hard Gate data -> UNKNOWN: PASS")
    print("7. invalid non-final PASS/FAIL rejected: PASS")
    print()
    print("=" * 70)
    print("HARD GATE SERVICE: PASS 7/7")
    print("=" * 70)

if __name__ == "__main__":
    main()
