from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from weekly.providers.alpaca_options_provider import (
    OptionContractCandidate,
)


@dataclass(frozen=True)
class ATMIVResult:
    atm_iv: float | None
    atm_strike: float | None
    contracts_used: int
    reason: str


class ATMIVResolver:
    """
    Resolve fallback ATM IV from target-expiry
    option contracts.

    Rules:
    1. Find the strike closest to underlying price.
    2. Use valid positive finite IV values at that strike.
    3. If Call + Put IV exist, average them.
    4. If only one valid IV exists, use it.
    5. If none exist, return None.
    """

    def resolve(
        self,
        *,
        underlying_price: float | None,
        contracts: Iterable[
            OptionContractCandidate
        ] | None,
    ) -> ATMIVResult:

        if not self._positive_finite(
            underlying_price
        ):
            return ATMIVResult(
                atm_iv=None,
                atm_strike=None,
                contracts_used=0,
                reason=(
                    "UNDERLYING_PRICE_UNAVAILABLE"
                ),
            )

        if contracts is None:
            return ATMIVResult(
                atm_iv=None,
                atm_strike=None,
                contracts_used=0,
                reason="OPTION_CHAIN_UNAVAILABLE",
            )

        contracts = tuple(contracts)

        if not contracts:
            return ATMIVResult(
                atm_iv=None,
                atm_strike=None,
                contracts_used=0,
                reason="OPTION_CHAIN_EMPTY",
            )

        valid_strikes = [
            float(contract.strike)
            for contract in contracts
            if self._positive_finite(
                contract.strike
            )
        ]

        if not valid_strikes:
            return ATMIVResult(
                atm_iv=None,
                atm_strike=None,
                contracts_used=0,
                reason="NO_VALID_STRIKES",
            )

        price = float(underlying_price)

        atm_strike = min(
            valid_strikes,
            key=lambda strike: (
                abs(strike - price),
                strike,
            ),
        )

        iv_values = [
            float(contract.iv)
            for contract in contracts
            if (
                float(contract.strike)
                == atm_strike
                and self._positive_finite(
                    contract.iv
                )
            )
        ]

        if not iv_values:
            return ATMIVResult(
                atm_iv=None,
                atm_strike=atm_strike,
                contracts_used=0,
                reason="ATM_IV_UNAVAILABLE",
            )

        atm_iv = (
            sum(iv_values)
            / len(iv_values)
        )

        return ATMIVResult(
            atm_iv=float(atm_iv),
            atm_strike=atm_strike,
            contracts_used=len(iv_values),
            reason="ATM_IV_RESOLVED",
        )

    @staticmethod
    def _positive_finite(
        value,
    ) -> bool:
        if value is None:
            return False

        try:
            numeric = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return False

        return (
            math.isfinite(numeric)
            and numeric > 0
        )
