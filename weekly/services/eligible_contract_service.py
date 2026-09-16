from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from config import load_weekly_config
from weekly.domain.enums import Direction, GateStatus, OptionRight


class EligibleContractError(ValueError):
    """Invalid eligible-contract evaluation input."""


@dataclass(frozen=True)
class ContractSelectorSettings:
    delta_min: float
    delta_max: float
    max_spread_pct: float
    max_quote_age_seconds: int
    standard_contract_size: int
    require_standard_contract: bool
    require_tradable_contract: bool
    max_budget: float
    target_abs_delta: float

    def __post_init__(self) -> None:
        if not (0 <= self.delta_min <= self.delta_max <= 1):
            raise EligibleContractError(
                "delta range must satisfy 0 <= min <= max <= 1."
            )
        if not (0 < self.max_spread_pct <= 1):
            raise EligibleContractError(
                "max_spread_pct must be in (0, 1]."
            )
        if self.max_quote_age_seconds <= 0:
            raise EligibleContractError(
                "max_quote_age_seconds must be positive."
            )
        if self.standard_contract_size <= 0:
            raise EligibleContractError(
                "standard_contract_size must be positive."
            )
        if self.max_budget <= 0:
            raise EligibleContractError(
                "max_budget must be positive."
            )
        if not (0 <= self.target_abs_delta <= 1):
            raise EligibleContractError(
                "target_abs_delta must be between 0 and 1."
            )

    @classmethod
    def from_config(cls) -> "ContractSelectorSettings":
        config = load_weekly_config(
            require_runtime_ready=True
        )
        section = config["contract_selector"]

        return cls(
            delta_min=float(section["delta_min"]),
            delta_max=float(section["delta_max"]),
            max_spread_pct=float(section["max_spread_pct"]),
            max_quote_age_seconds=int(
                section["max_option_quote_age_seconds"]
            ),
            standard_contract_size=int(
                section["standard_contract_size"]
            ),
            require_standard_contract=bool(
                section["require_standard_contract"]
            ),
            require_tradable_contract=bool(
                section["require_tradable_contract"]
            ),
            max_budget=float(section["max_budget"]),
            target_abs_delta=float(
                section["shadow_target_abs_delta"]
            ),
        )


@dataclass(frozen=True)
class OptionContractCandidate:
    symbol: str
    underlying_symbol: str
    root_symbol: str
    expiry: date
    right: OptionRight
    strike: float

    active: bool
    tradable: bool
    size: int | None

    bid: float | None
    ask: float | None
    quote_at: datetime | None

    delta: float | None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    iv: float | None = None


@dataclass(frozen=True)
class SelectedContract:
    symbol: str
    right: OptionRight
    strike: float
    bid: float
    ask: float
    mark: float
    delta: float
    gamma: float | None
    theta: float | None
    vega: float | None
    iv: float | None
    spread_pct: float
    quote_age_seconds: float
    contract_cost: float


@dataclass(frozen=True)
class EligibleContractResult:
    status: GateStatus
    selected: SelectedContract | None
    expected_right: OptionRight
    target_expiry: date
    underlying_price: float | None
    expected_move: float | None
    range_low: float | None
    range_high: float | None
    contracts_seen: int
    eligible_count: int
    reason: str


class EligibleContractService:
    """
    Pure weekly eligible-contract Hard Gate.

    No API calls and no database writes are performed here.

    Frozen rules:
    - exact target expiry
    - CALL for bullish, PUT for bearish
    - active and, when configured, tradable
    - conservative standard-contract screen
    - abs(delta) within configured range
    - valid fresh bid/ask
    - spread within configured maximum
    - ask-price contract cost within max budget
    - strike inside underlying +/- exact-expiry expected move

    Ranking among eligible contracts:
    1) abs(delta) closest to configured target
    2) narrower spread
    3) stable symbol ordering
    """

    def __init__(
        self,
        settings: ContractSelectorSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            if settings is not None
            else ContractSelectorSettings.from_config()
        )

    def evaluate(
        self,
        *,
        direction: Direction,
        target_expiry: date,
        underlying_price: float | None,
        expected_move: float | None,
        as_of: datetime,
        contracts: Iterable[OptionContractCandidate] | None,
    ) -> EligibleContractResult:
        self._validate_inputs(
            direction=direction,
            target_expiry=target_expiry,
            underlying_price=underlying_price,
            expected_move=expected_move,
            as_of=as_of,
        )

        expected_right = (
            OptionRight.CALL
            if direction is Direction.BULLISH
            else OptionRight.PUT
        )

        if (
            underlying_price is None
            or expected_move is None
            or not self._is_positive_finite(underlying_price)
            or not self._is_positive_finite(expected_move)
        ):
            return EligibleContractResult(
                status=GateStatus.UNKNOWN,
                selected=None,
                expected_right=expected_right,
                target_expiry=target_expiry,
                underlying_price=underlying_price,
                expected_move=expected_move,
                range_low=None,
                range_high=None,
                contracts_seen=0,
                eligible_count=0,
                reason="EXPECTED_MOVE_OR_UNDERLYING_UNAVAILABLE",
            )

        range_low = underlying_price - expected_move
        range_high = underlying_price + expected_move

        if contracts is None:
            return EligibleContractResult(
                status=GateStatus.UNKNOWN,
                selected=None,
                expected_right=expected_right,
                target_expiry=target_expiry,
                underlying_price=underlying_price,
                expected_move=expected_move,
                range_low=range_low,
                range_high=range_high,
                contracts_seen=0,
                eligible_count=0,
                reason="CONTRACT_DATA_UNAVAILABLE",
            )

        contract_list = tuple(contracts)
        eligible: list[SelectedContract] = []

        for candidate in contract_list:
            selected = self._screen_candidate(
                candidate=candidate,
                expected_right=expected_right,
                target_expiry=target_expiry,
                range_low=range_low,
                range_high=range_high,
                as_of=as_of,
            )
            if selected is not None:
                eligible.append(selected)

        if not eligible:
            return EligibleContractResult(
                status=GateStatus.FAIL,
                selected=None,
                expected_right=expected_right,
                target_expiry=target_expiry,
                underlying_price=underlying_price,
                expected_move=expected_move,
                range_low=range_low,
                range_high=range_high,
                contracts_seen=len(contract_list),
                eligible_count=0,
                reason="NO_ELIGIBLE_CONTRACT",
            )

        chosen = min(
            eligible,
            key=lambda item: (
                abs(abs(item.delta) - self.settings.target_abs_delta),
                item.spread_pct,
                item.symbol,
            ),
       )

        return EligibleContractResult(
            status=GateStatus.PASS,
            selected=chosen,
            expected_right=expected_right,
            target_expiry=target_expiry,
            underlying_price=underlying_price,
            expected_move=expected_move,
            range_low=range_low,
            range_high=range_high,
            contracts_seen=len(contract_list),
            eligible_count=len(eligible),
            reason="ELIGIBLE_CONTRACT_FOUND",
        )

    def _screen_candidate(
        self,
        *,
        candidate: OptionContractCandidate,
        expected_right: OptionRight,
        target_expiry: date,
        range_low: float,
        range_high: float,
        as_of: datetime,
    ) -> SelectedContract | None:
        if not candidate.symbol.strip():
            return None

        if candidate.expiry != target_expiry:
            return None

        if candidate.right is not expected_right:
            return None

        if not candidate.active:
            return None

        if (
            self.settings.require_tradable_contract
            and not candidate.tradable
        ):
            return None

        if self.settings.require_standard_contract:
            if not self._passes_standard_screen(candidate):
                return None

        if not self._is_positive_finite(candidate.strike):
            return None

        if not (range_low <= candidate.strike <= range_high):
            return None

        if (
            candidate.delta is None
            or not math.isfinite(float(candidate.delta))
        ):
            return None

        abs_delta = abs(float(candidate.delta))
        if not (
            self.settings.delta_min
            <= abs_delta
            <= self.settings.delta_max
        ):
            return None

        if (
            candidate.bid is None
            or candidate.ask is None
            or not self._is_positive_finite(candidate.bid)
            or not self._is_positive_finite(candidate.ask)
            or candidate.ask < candidate.bid
        ):
            return None

        mark = (
            float(candidate.bid)
            + float(candidate.ask)
        ) / 2.0

        if not self._is_positive_finite(mark):
            return None

        spread_pct = (
            float(candidate.ask)
            - float(candidate.bid)
        ) / mark

        if spread_pct > self.settings.max_spread_pct:
            return None

        if (
            candidate.quote_at is None
            or candidate.quote_at.tzinfo is None
        ):
            return None

        quote_age = (
            as_of - candidate.quote_at
        ).total_seconds()

        if quote_age < 0:
            return None

        if quote_age > self.settings.max_quote_age_seconds:
            return None

        contract_cost = (
            float(candidate.ask)
            * self.settings.standard_contract_size
        )

        if contract_cost > self.settings.max_budget:
            return None

        return SelectedContract(
            symbol=candidate.symbol,
            right=candidate.right,
            strike=float(candidate.strike),
            bid=float(candidate.bid),
            ask=float(candidate.ask),
            mark=float(mark),
            delta=float(candidate.delta),
            gamma=self._optional_finite(candidate.gamma),
            theta=self._optional_finite(candidate.theta),
            vega=self._optional_finite(candidate.vega),
            iv=self._optional_finite(candidate.iv),
            spread_pct=float(spread_pct),
            quote_age_seconds=float(quote_age),
            contract_cost=float(contract_cost),
        )

    def _passes_standard_screen(
        self,
        candidate: OptionContractCandidate,
    ) -> bool:
        root = candidate.root_symbol.strip().upper()
        underlying = (
            candidate.underlying_symbol.strip().upper()
        )

        if not root or not underlying:
            return False

        if re.search(r"\d+$", root):
            return False

        if root != underlying:
            return False

        return (
            candidate.size
            == self.settings.standard_contract_size
        )

    @staticmethod
    def _is_positive_finite(
        value: float | int,
    ) -> bool:
        if isinstance(value, bool):
            return False

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False

        return math.isfinite(numeric) and numeric > 0

    @staticmethod
    def _optional_finite(
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        numeric = float(value)

        return (
            numeric
            if math.isfinite(numeric)
            else None
        )

    @staticmethod
    def _validate_inputs(
        *,
        direction: Direction,
        target_expiry: date,
        underlying_price: float | None,
        expected_move: float | None,
        as_of: datetime,
    ) -> None:
        if not isinstance(direction, Direction):
            raise EligibleContractError(
                "direction must be Direction."
            )

        if not isinstance(target_expiry, date):
            raise EligibleContractError(
                "target_expiry must be date."
            )

        if (
            not isinstance(as_of, datetime)
            or as_of.tzinfo is None
        ):
            raise EligibleContractError(
                "as_of must be a timezone-aware datetime."
            )

        for name, value in (
            ("underlying_price", underlying_price),
            ("expected_move", expected_move),
        ):
            if value is not None and isinstance(value, bool):
                raise EligibleContractError(
                    f"{name} must be numeric or None."
                )

            if value is not None:
                try:
                    float(value)
                except (TypeError, ValueError) as exc:
                    raise EligibleContractError(
                        f"{name} must be numeric or None."
                    ) from exc
