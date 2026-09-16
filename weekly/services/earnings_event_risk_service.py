from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from weekly.domain.enums import GateStatus


class EarningsEventRiskError(ValueError):
    """Invalid earnings-event risk input."""


@dataclass(frozen=True)
class EarningsEventRiskResult:
    status: GateStatus
    trading_date_et: date
    target_expiry: date
    next_earnings_date: date | None
    earnings_time_raw: str | None
    earnings_time_normalized: str | None
    reason: str


class EarningsEventRiskService:
    """
    Evaluate the frozen weekly_v1 earnings/event Hard Gate.

    Rules
    -----
    - Missing next upcoming earnings -> UNKNOWN.
    - Stale/past "next" earnings date -> UNKNOWN.
    - Earnings before target expiry -> FAIL.
    - Earnings after target expiry -> PASS.
    - Earnings on target expiry:
        * BMO / premarket -> FAIL.
        * AMC / postmarket -> PASS.
        * unknown/unsupported timing -> UNKNOWN.

    The authoritative upstream field is expected to be
    UW Stock Screener -> next_earnings_date + er_time.

    This service is pure logic:
    it performs no API calls and no database writes.
    """

    _BMO_ALIASES = frozenset(
        {
            "bmo",
            "before market open",
            "before_market_open",
            "before-market-open",
            "premarket",
            "pre-market",
            "pre market",
        }
    )

    _AMC_ALIASES = frozenset(
        {
            "amc",
            "after market close",
            "after_market_close",
            "after-market-close",
            "postmarket",
            "post-market",
            "post market",
        }
    )

    def evaluate(
        self,
        *,
        trading_date_et: date,
        target_expiry: date,
        next_earnings_date: date | None,
        earnings_time: str | None,
    ) -> EarningsEventRiskResult:
        self._validate_dates(
            trading_date_et=trading_date_et,
            target_expiry=target_expiry,
            next_earnings_date=next_earnings_date,
        )

        normalized_time = self._normalize_time(
            earnings_time
        )

        if next_earnings_date is None:
            return self._result(
                status=GateStatus.UNKNOWN,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=None,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="NEXT_EARNINGS_UNAVAILABLE",
            )

        if next_earnings_date < trading_date_et:
            return self._result(
                status=GateStatus.UNKNOWN,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=next_earnings_date,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="NEXT_EARNINGS_DATE_STALE",
            )

        if next_earnings_date < target_expiry:
            return self._result(
                status=GateStatus.FAIL,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=next_earnings_date,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="EARNINGS_BEFORE_TARGET_EXPIRY",
            )

        if next_earnings_date > target_expiry:
            return self._result(
                status=GateStatus.PASS,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=next_earnings_date,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="EARNINGS_AFTER_TARGET_EXPIRY",
            )

        # Same calendar date as target expiry.
        if normalized_time == "BMO":
            return self._result(
                status=GateStatus.FAIL,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=next_earnings_date,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="EARNINGS_ON_EXPIRY_BMO",
            )

        if normalized_time == "AMC":
            return self._result(
                status=GateStatus.PASS,
                trading_date_et=trading_date_et,
                target_expiry=target_expiry,
                next_earnings_date=next_earnings_date,
                earnings_time_raw=earnings_time,
                earnings_time_normalized=normalized_time,
                reason="EARNINGS_ON_EXPIRY_AMC",
            )

        return self._result(
            status=GateStatus.UNKNOWN,
            trading_date_et=trading_date_et,
            target_expiry=target_expiry,
            next_earnings_date=next_earnings_date,
            earnings_time_raw=earnings_time,
            earnings_time_normalized=normalized_time,
            reason="EARNINGS_ON_EXPIRY_TIME_UNKNOWN",
        )

    @classmethod
    def _normalize_time(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        text = " ".join(
            str(value).strip().lower().split()
        )

        if not text:
            return None

        if text in cls._BMO_ALIASES:
            return "BMO"

        if text in cls._AMC_ALIASES:
            return "AMC"

        return None

    @staticmethod
    def _validate_dates(
        *,
        trading_date_et: date,
        target_expiry: date,
        next_earnings_date: date | None,
    ) -> None:
        if not isinstance(trading_date_et, date):
            raise EarningsEventRiskError(
                "trading_date_et must be date."
            )

        if not isinstance(target_expiry, date):
            raise EarningsEventRiskError(
                "target_expiry must be date."
            )

        if (
            next_earnings_date is not None
            and not isinstance(next_earnings_date, date)
        ):
            raise EarningsEventRiskError(
                "next_earnings_date must be date or None."
            )

        if target_expiry < trading_date_et:
            raise EarningsEventRiskError(
                "target_expiry cannot be before trading_date_et."
            )

    @staticmethod
    def _result(
        *,
        status: GateStatus,
        trading_date_et: date,
        target_expiry: date,
        next_earnings_date: date | None,
        earnings_time_raw: str | None,
        earnings_time_normalized: str | None,
        reason: str,
    ) -> EarningsEventRiskResult:
        return EarningsEventRiskResult(
            status=status,
            trading_date_et=trading_date_et,
            target_expiry=target_expiry,
            next_earnings_date=next_earnings_date,
            earnings_time_raw=earnings_time_raw,
            earnings_time_normalized=earnings_time_normalized,
            reason=reason,
        )
