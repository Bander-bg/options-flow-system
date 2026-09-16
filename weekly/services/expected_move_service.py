from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Any

from weekly.domain.enums import GateStatus


class ExpectedMoveError(ValueError):
    """Invalid expected-move evaluation input."""


@dataclass(frozen=True)
class ExpectedMoveResult:
    status: GateStatus
    expected_move: float | None
    expected_move_perc: float | None
    source: str | None
    target_expiry: date
    trading_date: date
    dte_calendar_days: int | None
    atm_iv: float | None
    reason: str


class ExpectedMoveService:
    """
    Pure weekly expected-move resolver.

    Source priority:
    1) Unusual Whales volatility term-structure row whose expiry exactly
       matches target_expiry and has valid positive implied_move,
       volatility, and implied_move_perc values.
    2) ATM-IV fallback supplied by the data/provider layer.

    The canonical stored expected_move_perc is always a decimal fraction:
        expected_move / underlying_price

    This service performs no API calls and no database writes.
    """

    PRIMARY_SOURCE = "UW_TERM_STRUCTURE"
    FALLBACK_SOURCE = "ATM_IV_FALLBACK"

    def evaluate(
        self,
        *,
        trading_date: date,
        target_expiry: date,
        underlying_price: float | None,
        term_structure_rows: Iterable[Mapping[str, Any]] | None,
        atm_iv: float | None,
    ) -> ExpectedMoveResult:
        self._validate_dates(
            trading_date=trading_date,
            target_expiry=target_expiry,
      )

        if not self._is_positive_finite(underlying_price):
            return ExpectedMoveResult(
                status=GateStatus.UNKNOWN,
                expected_move=None,
                expected_move_perc=None,
                source=None,
                target_expiry=target_expiry,
                trading_date=trading_date,
                dte_calendar_days=None,
                atm_iv=self._optional_positive_finite(atm_iv),
                reason="UNDERLYING_PRICE_UNAVAILABLE",
            )

        price = float(underlying_price)
        dte_days = (target_expiry - trading_date).days

        exact_row = self._find_exact_expiry_row(
            term_structure_rows,
            target_expiry,
        )

        if exact_row is not None:
            implied_move = self._positive_finite_or_none(
                exact_row.get("implied_move")
            )
            volatility = self._positive_finite_or_none(
                exact_row.get("volatility")
            )
            implied_move_perc_raw = self._positive_finite_or_none(
                exact_row.get("implied_move_perc")
            )

            if (
                implied_move is not None
                and volatility is not None
                and implied_move_perc_raw is not None
            ):
                return ExpectedMoveResult(
                    status=GateStatus.PASS,
                    expected_move=implied_move,
                    expected_move_perc=implied_move / price,
                    source=self.PRIMARY_SOURCE,
                    target_expiry=target_expiry,
                    trading_date=trading_date,
                    dte_calendar_days=dte_days,
                    atm_iv=None,
                    reason="UW_EXACT_EXPIRY_EXPECTED_MOVE",
                )

        fallback_iv = self._optional_positive_finite(atm_iv)

        if fallback_iv is None:
            return ExpectedMoveResult(
                status=GateStatus.UNKNOWN,
                expected_move=None,
                expected_move_perc=None,
                source=None,
                target_expiry=target_expiry,
                trading_date=trading_date,
                dte_calendar_days=dte_days,
                atm_iv=None,
                reason="EXPECTED_MOVE_SOURCES_UNAVAILABLE",
            )

        expected_move = (
            price
            * fallback_iv
            * math.sqrt(dte_days / 365.0)
        )

        if not self._is_positive_finite(expected_move):
            return ExpectedMoveResult(
                status=GateStatus.UNKNOWN,
                expected_move=None,
                expected_move_perc=None,
                source=None,
                target_expiry=target_expiry,
                trading_date=trading_date,
                dte_calendar_days=dte_days,
                atm_iv=fallback_iv,
                reason="ATM_IV_FALLBACK_INVALID",
            )

        return ExpectedMoveResult(
            status=GateStatus.PASS,
            expected_move=float(expected_move),
            expected_move_perc=float(expected_move / price),
            source=self.FALLBACK_SOURCE,
            target_expiry=target_expiry,
            trading_date=trading_date,
            dte_calendar_days=dte_days,
            atm_iv=fallback_iv,
            reason="ATM_IV_FALLBACK_EXPECTED_MOVE",
        )

    @staticmethod
    def _find_exact_expiry_row(
        rows: Iterable[Mapping[str, Any]] | None,
        target_expiry: date,
    ) -> Mapping[str, Any] | None:
        if rows is None:
            return None

        target_text = target_expiry.isoformat()

        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if row.get("expiry") == target_text:
                return row

        return None

    @staticmethod
    def _validate_dates(
        *,
        trading_date: date,
        target_expiry: date,
    ) -> None:
        if not isinstance(trading_date, date):
            raise ExpectedMoveError(
                "trading_date must be date."
            )

        if not isinstance(target_expiry, date):
            raise ExpectedMoveError(
                "target_expiry must be date."
            )

        if target_expiry <= trading_date:
            raise ExpectedMoveError(
                "target_expiry must be after trading_date."
            )

    @staticmethod
    def _is_positive_finite(
        value: object,
    ) -> bool:
        if value is None or isinstance(value, bool):
            return False

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False

        return math.isfinite(numeric) and numeric > 0

    @classmethod
    def _positive_finite_or_none(
        cls,
        value: object,
    ) -> float | None:
        if not cls._is_positive_finite(value):
            return None
        return float(value)

    @classmethod
    def _optional_positive_finite(
        cls,
        value: object,
    ) -> float | None:
        if value is None:
            return None
        return cls._positive_finite_or_none(value)
