from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from weekly.domain.enums import Direction


ET = ZoneInfo("America/New_York")


class FlowDataError(RuntimeError):
    """
    Raised when essential UW flow fields are missing
    or malformed.

    We do not silently convert bad source data into
    a valid trading signal.
    """


@dataclass(frozen=True)
class FlowCalculation:
    ticker: str
    trading_date_et: date
    target_expiry: date

    flow_dedup_level: str
    trade_overlap_detected: bool

    raw_alert_count: int
    clean_alert_count: int
    deduped_alert_count: int

    call_ask_premium: float
    put_ask_premium: float

    call_bid_premium: float
    put_bid_premium: float

    net_flow: float

    bullish_premium: float
    bearish_premium: float
    directional_net: float

    sweep_alert_count: int
    opening_alert_count: int

    total_premium: float | None = None
    sweep_premium: float | None = None


def _parse_timestamp(
    value: Any,
) -> datetime:
    if value is None:
        raise FlowDataError(
            "Flow alert created_at is missing."
        )

    text = str(value).strip()

    try:
        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise FlowDataError(
            f"Invalid created_at: {value!r}"
        ) from exc

    if parsed.tzinfo is None:
        raise FlowDataError(
            "created_at must be timezone-aware."
        )

    return parsed


def _required_bool(
    alert: dict,
    field: str,
) -> bool:
    if field not in alert:
        raise FlowDataError(
            f"Required flow field missing: {field}"
        )

    value = alert[field]

    if not isinstance(
        value,
        bool,
    ):
        raise FlowDataError(
            f"{field} must be bool, "
            f"got {value!r}"
        )

    return value


def _required_text(
    alert: dict,
    field: str,
) -> str:
    value = alert.get(
        field
    )

    if value is None:
        raise FlowDataError(
            f"Required flow field missing: {field}"
        )

    text = str(value).strip()

    if not text:
        raise FlowDataError(
            f"Required flow field empty: {field}"
        )

    return text


def _required_nonnegative_float(
    alert: dict,
    field: str,
) -> float:
    if field not in alert:
        raise FlowDataError(
            f"Required flow field missing: {field}"
        )

    value = alert[field]

    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise FlowDataError(
            f"{field} is not numeric: {value!r}"
        ) from exc

    if number < 0:
        raise FlowDataError(
            f"{field} cannot be negative."
        )

    return number


def _extract_trade_ids(
    alert: dict,
) -> list[str]:
    value = alert.get(
        "trade_ids"
    )

    if not value:
        return []

    if not isinstance(
        value,
        list,
    ):
        raise FlowDataError(
            "trade_ids must be a list when present."
        )

    return [
        str(item)
        for item in value
        if item is not None
    ]


def _alert_composite_key(
    alert: dict,
) -> tuple[str, str, str]:
    return (
        _required_text(
            alert,
            "created_at",
        ),
        _required_text(
            alert,
            "option_chain",
        ),
        _required_text(
            alert,
            "alert_rule",
        ),
    )


def _detect_trade_overlap(
    alerts: list[dict],
) -> bool:
    seen: set[str] = set()

    for alert in alerts:
        for trade_id in _extract_trade_ids(
            alert
        ):
            if trade_id in seen:
                return True

            seen.add(
                trade_id
            )

    return False


def _deduplicate_alerts(
    alerts: list[dict],
) -> tuple[
    list[dict],
    str,
    bool,
]:
    """
    Current weekly_v1 priority:

    1) trade_ids + individual OptionTrade details
       -> true trade-level dedup
       (handled by a future provider path only when
       those details are actually available).

    2) trade_ids exist but individual trade details
       unavailable -> overlap diagnostic only.

    3) unique alert UUID available for all rows
       -> alert_uuid.

    4) otherwise:
       created_at + option_chain + alert_rule
       -> alert_composite.

    Current tested UW REST account falls into #4.
    """

    if not alerts:
        return (
            [],
            "alert_composite",
            False,
        )

    trade_ids_present = any(
        bool(
            _extract_trade_ids(
                alert
            )
        )
        for alert in alerts
    )

    trade_overlap_detected = (
        _detect_trade_overlap(
            alerts
        )
        if trade_ids_present
        else False
    )

    all_have_uuid = all(
        bool(
            str(
                alert.get(
                    "id",
                    "",
                )
            ).strip()
        )
        for alert in alerts
    )

    # trade_ids without individual OptionTrade
    # premium/direction details cannot be used to
    # mathematically subtract overlapping trades.
    if trade_ids_present:
        flow_dedup_level = (
            "trade_overlap_flagged"
        )

    elif all_have_uuid:
        flow_dedup_level = (
            "alert_uuid"
        )

    else:
        flow_dedup_level = (
            "alert_composite"
        )

    seen_keys = set()
    deduped = []

    for alert in alerts:

        if all_have_uuid:
            key = (
                "uuid",
                _required_text(
                    alert,
                    "id",
                ),
            )

        else:
            key = (
                "composite",
                *_alert_composite_key(
                    alert
                ),
            )

        if key in seen_keys:
            continue

        seen_keys.add(
            key
        )

        deduped.append(
            alert
        )

    return (
        deduped,
        flow_dedup_level,
        trade_overlap_detected,
    )


def clean_flow_alerts(
    *,
    alerts: list[dict],
    trading_date_et: date,
    target_expiry: date,
    session_open_et: datetime,
    session_close_et: datetime,
) -> tuple[
    list[dict],
    list[dict],
    str,
    bool,
]:
    """
    Build the weekly_v1 Clean Universe.

    Returns:
    - clean alerts before dedup
    - deduped alerts
    - dedup level
    - trade overlap flag
    """

    if (
        session_open_et.tzinfo is None
        or session_close_et.tzinfo is None
    ):
        raise ValueError(
            "Session open/close must be "
            "timezone-aware."
        )

    open_et = session_open_et.astimezone(
        ET
    )

    close_et = session_close_et.astimezone(
        ET
    )

    if (
        open_et.date() != trading_date_et
        or close_et.date() != trading_date_et
    ):
        raise ValueError(
            "Session open/close do not match "
            "trading_date_et."
        )

    target_text = target_expiry.isoformat()

    clean = []

    for alert in alerts:

        created_at = _parse_timestamp(
            alert.get(
                "created_at"
            )
        )

        created_at_et = (
            created_at.astimezone(
                ET
            )
        )

        expiry = _required_text(
            alert,
            "expiry",
        )

        has_multileg = _required_bool(
            alert,
            "has_multileg",
        )

        has_singleleg = _required_bool(
            alert,
            "has_singleleg",
        )

        _required_text(
            alert,
            "option_chain",
        )

        _required_text(
            alert,
            "alert_rule",
        )

        option_type = _required_text(
            alert,
            "type",
        ).lower()

        if option_type not in (
            "call",
            "put",
        ):
            raise FlowDataError(
                f"Unsupported option type: "
                f"{option_type!r}"
            )

        _required_nonnegative_float(
            alert,
            "total_ask_side_prem",
        )

        _required_nonnegative_float(
            alert,
            "total_bid_side_prem",
        )

        if expiry != target_text:
            continue

        if (
            created_at_et.date()
            != trading_date_et
        ):
            continue

        if not (
            open_et
            <= created_at_et
            <= close_et
        ):
            continue

        if has_multileg:
            continue

        if not has_singleleg:
            continue

        clean.append(
            alert
        )

    deduped, dedup_level, overlap = (
        _deduplicate_alerts(
            clean
        )
    )

    return (
        clean,
        deduped,
        dedup_level,
        overlap,
    )


def calculate_flow(
    *,
    ticker: str,
    alerts: list[dict],
    trading_date_et: date,
    target_expiry: date,
    session_open_et: datetime,
    session_close_et: datetime,
) -> FlowCalculation:
    clean_alerts, deduped_alerts, dedup_level, overlap = (
    clean_flow_alerts(
            alerts=alerts,
            trading_date_et=trading_date_et,
            target_expiry=target_expiry,
            session_open_et=session_open_et,
            session_close_et=session_close_et,
        )
    )

    call_ask = 0.0
    put_ask = 0.0

    call_bid = 0.0
    put_bid = 0.0

    sweep_alert_count = 0
    opening_alert_count = 0

    total_premium = 0.0
    sweep_premium = 0.0
    premium_evidence_complete = True

    for alert in deduped_alerts:

        option_type = (
            _required_text(
                alert,
                "type",
            ).lower()
        )

        ask_premium = (
            _required_nonnegative_float(
                alert,
                "total_ask_side_prem",
            )
        )

        bid_premium = (
            _required_nonnegative_float(
                alert,
                "total_bid_side_prem",
            )
        )

        if option_type == "call":
            call_ask += (
                ask_premium
            )

            call_bid += (
                bid_premium
            )

        elif option_type == "put":
            put_ask += (
                ask_premium
            )

            put_bid += (
                bid_premium
            )

        alert_total_premium = None
        if "total_premium" in alert and alert.get("total_premium") is not None:
            alert_total_premium = _required_nonnegative_float(
                alert,
                "total_premium",
            )
            total_premium += alert_total_premium
        else:
            premium_evidence_complete = False

        if alert.get(
            "has_sweep"
        ) is True:
            sweep_alert_count += 1
            if alert_total_premium is not None:
                sweep_premium += alert_total_premium

        if alert.get(
            "all_opening_trades"
        ) is True:
            opening_alert_count += 1

    # PRIMARY weekly_v1 signal.
    net_flow = (
        call_ask
        - put_ask
    )

    # Quality-only Directional Flow Confirmation.
    bullish_premium = (
        call_ask
        + put_bid
    )

    bearish_premium = (
        put_ask
        + call_bid
    )

    directional_net = (
        bullish_premium
        - bearish_premium
    )

    return FlowCalculation(
        ticker=ticker,
        trading_date_et=trading_date_et,
        target_expiry=target_expiry,

        flow_dedup_level=dedup_level,
        trade_overlap_detected=overlap,

        raw_alert_count=len(
            alerts
        ),

        clean_alert_count=len(
    clean_alerts
),

deduped_alert_count=len(
    deduped_alerts
),

        call_ask_premium=call_ask,
        put_ask_premium=put_ask,

        call_bid_premium=call_bid,
        put_bid_premium=put_bid,

        net_flow=net_flow,

        bullish_premium=bullish_premium,
        bearish_premium=bearish_premium,
        directional_net=directional_net,

        sweep_alert_count=sweep_alert_count,
        opening_alert_count=opening_alert_count,
        total_premium=(
            total_premium if premium_evidence_complete else None
        ),
        sweep_premium=(
            sweep_premium if premium_evidence_complete else None
        ),
    )


def get_base_flow_direction(
    *,
    net_flow: float,
    threshold: float,
) -> Direction | None:
    """
    PRIMARY Candidate hypothesis only.

    Directional Net does NOT replace this rule.
    """

    if threshold <= 0:
        raise ValueError(
            "threshold must be > 0"
        )

    if net_flow >= threshold:
        return Direction.BULLISH

    if net_flow <= -threshold:
        return Direction.BEARISH

    return None


def directional_confirmation_matches(
    *,
    base_direction: Direction,
    directional_net: float,
) -> bool:
    """
    Quality-only confirmation.

    A mismatch must never invalidate the primary
    Candidate by itself.
    """

    if (
        base_direction
        is Direction.BULLISH
    ):
        return directional_net > 0

    return directional_net < 0