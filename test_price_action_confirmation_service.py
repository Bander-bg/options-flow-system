from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from weekly.domain.enums import GateStatus

from weekly.domain.models import SignalFeature

from weekly.services.price_action_confirmation_service import (
    PriceActionConfirmationService,
)


ET = ZoneInfo("America/New_York")


def feature(
    *,
    sequence: int,
    bar_at: datetime,
    status: GateStatus,
    feature_id: int,
) -> SignalFeature:
    return SignalFeature(
        signal_id=1,
        evaluation_sequence=sequence,
        captured_at=bar_at,
        price_action_bar_at=bar_at,
        price_action_status=status,
        price_action_pass_count=(
            2
            if status == GateStatus.PASS
            else 1
            if status == GateStatus.FAIL
            else 0
        ),
        id=feature_id,
    )


def main() -> None:
    service = PriceActionConfirmationService()

    candidate_at = datetime(
        2026,
        9,
        11,
        12,
        0,
        tzinfo=ET,
    )

    deadline = (
        candidate_at
        + timedelta(minutes=30)
    )

    bar_1 = (
        candidate_at
        + timedelta(minutes=15)
    )

    bar_2 = (
        candidate_at
        + timedelta(minutes=30)
    )

    # ==================================================
    # 1. EARLY PASS CONFIRMS IMMEDIATELY
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=bar_1,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.PASS,
                feature_id=101,
            ),
        ],
    )

    assert result.status == GateStatus.PASS
    assert result.is_final is True

    assert (
        result.reason
        == "PRICE_ACTION_CONFIRMED"
    )

    assert result.evaluations_seen == 1
    assert result.pass_evaluations == 1

    assert (
        result.matched_feature_id
        == 101
    )

    assert (
        result.matched_evaluation_sequence
        == 1
    )

    assert result.matched_bar_at == bar_1

    print(
        "1. early PASS confirms immediately: PASS"
    )

    # ==================================================
    # 2. FAIL WHILE WINDOW OPEN IS NOT FINAL
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=bar_1,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.FAIL,
                feature_id=201,
            ),
        ],
    )

    assert result.status == GateStatus.UNKNOWN
    assert result.is_final is False

    assert (
        result.reason
        == "CONFIRMATION_WINDOW_OPEN"
    )

    assert result.fail_evaluations == 1

    print(
        "2. FAIL during open window is not final: PASS"
    )

    # ==================================================
    # 3. SECOND BAR PASS CONFIRMS
    #
    # First bar FAIL.
    # Second bar PASS.
    # Overall final PASS.
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=bar_2,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.FAIL,
                feature_id=301,
            ),
            feature(
                sequence=2,
                bar_at=bar_2,
                status=GateStatus.PASS,
                feature_id=302,
            ),
        ],
    )

    assert result.status == GateStatus.PASS
    assert result.is_final is True

    assert result.evaluations_seen == 2
    assert result.fail_evaluations == 1
    assert result.pass_evaluations == 1

    assert (
        result.matched_feature_id
        == 302
    )

    assert (
        result.matched_bar_at
        == bar_2
    )

    print(
        "3. later PASS confirms after earlier FAIL: PASS"
    )

    # ==================================================
    # 4. WINDOW EXPIRES WITH ONLY FAILS
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=deadline,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.FAIL,
                feature_id=401,
            ),
            feature(
                sequence=2,
                bar_at=bar_2,
                status=GateStatus.FAIL,
                feature_id=402,
            ),
        ],
    )

    assert result.status == GateStatus.FAIL
    assert result.is_final is True

    assert (
        result.reason
        == "CONFIRMATION_WINDOW_EXPIRED_NO_PASS"
    )

    assert result.evaluations_seen == 2
    assert result.fail_evaluations == 2
    assert result.unknown_evaluations == 0

    print(
        "4. deadline with only FAILs: PASS"
    )

    # ==================================================
    # 5. WINDOW EXPIRES WITH UNKNOWN DATA
    #
    # UNKNOWN must not be converted into FAIL.
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=deadline,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.FAIL,
                feature_id=501,
            ),
            feature(
                sequence=2,
                bar_at=bar_2,
                status=GateStatus.UNKNOWN,
                feature_id=502,
            ),
        ],
    )

    assert result.status == GateStatus.UNKNOWN
    assert result.is_final is True

    assert (
        result.reason
        == "PRICE_ACTION_DATA_UNRESOLVED"
    )

    assert result.fail_evaluations == 1
    assert result.unknown_evaluations == 1

    print(
        "5. deadline UNKNOWN stays unresolved: PASS"
    )

    # ==================================================
    # 6. WINDOW EXPIRES WITH NO EVALUATIONS
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=deadline,
        features=[],
    )

    assert result.status == GateStatus.UNKNOWN
    assert result.is_final is True

    assert (
        result.reason
        == "NO_PRICE_ACTION_EVALUATIONS"
    )

    assert result.evaluations_seen == 0

    print(
        "6. no evaluations at deadline: PASS"
    )

    # ==================================================
    # 7. IMMUTABLE SNAPSHOT DEDUP
    #
    # Same bar exists twice because a later snapshot
    # carried the same PA result forward.
    #
    # It must count as ONE bar only.
    # Highest evaluation_sequence wins.
    # ==================================================

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=bar_1,
        features=[
            feature(
                sequence=1,
                bar_at=bar_1,
                status=GateStatus.FAIL,
                feature_id=701,
            ),
            feature(
                sequence=2,
                bar_at=bar_1,
                status=GateStatus.PASS,
                feature_id=702,
            ),
        ],
    )

    assert result.status == GateStatus.PASS
    assert result.is_final is True

    assert result.evaluations_seen == 1
    assert result.pass_evaluations == 1
    assert result.fail_evaluations == 0

    assert (
        result.matched_feature_id
        == 702
    )

    assert (
        result.matched_evaluation_sequence
        == 2
    )

    print(
        "7. duplicate snapshot dedup: PASS"
    )

    # ==================================================
    # 8. OUT-OF-WINDOW EVALUATIONS ARE IGNORED
    # ==================================================

    before_candidate = candidate_at

    after_deadline = (
        deadline
        + timedelta(minutes=15)
    )

    result = service.resolve(
        candidate_at=candidate_at,
        confirmation_deadline_at=deadline,
        as_of=deadline,
        features=[
            feature(
                sequence=1,
                bar_at=before_candidate,
                status=GateStatus.PASS,
                feature_id=801,
            ),
            feature(
                sequence=2,
                bar_at=after_deadline,
                status=GateStatus.PASS,
                feature_id=802,
            ),
        ],
    )

    assert result.status == GateStatus.UNKNOWN
    assert result.is_final is True

    assert (
        result.reason
        == "NO_PRICE_ACTION_EVALUATIONS"
    )

    assert result.evaluations_seen == 0

    print(
        "8. out-of-window evaluations ignored: PASS"
    )

    print()
    print("=" * 70)
    print(
        "PRICE ACTION CONFIRMATION SERVICE: PASS 8/8"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()