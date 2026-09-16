from __future__ import annotations


class OutcomeReturnService:
    """
    Pure weekly_v1 outcome-return calculations.

    Frozen semantics:
    - underlying raw return:
      (observed - baseline) / baseline
    - directional underlying return:
      signal_sign * raw return
    - executable option return:
      baseline Ask -> observed Bid
    - mark return remains separate
    - expiry settlement uses intrinsic value

    This service does NOT:
    - define outcome baselines
    - schedule checkpoints
    - fetch market data
    - persist Outcome rows
    - transition Signal state
    """

    @staticmethod
    def underlying_raw_return(
        *,
        baseline_price: float,
        observed_price: float,
    ) -> float:
        if baseline_price <= 0:
            raise ValueError(
                "baseline_price must be > 0"
            )

        return (
            observed_price - baseline_price
        ) / baseline_price

    @classmethod
    def underlying_directional_return(
        cls,
        *,
        baseline_price: float,
        observed_price: float,
        signal_sign: int,
    ) -> float:
        if signal_sign not in (-1, 1):
            raise ValueError(
                "signal_sign must be +1 or -1"
            )

        raw = cls.underlying_raw_return(
            baseline_price=baseline_price,
            observed_price=observed_price,
        )

        return signal_sign * raw

    @staticmethod
    def option_executable_return(
        *,
        baseline_option_ask: float,
        observed_option_bid: float,
    ) -> float:
        if baseline_option_ask <= 0:
            raise ValueError(
                "baseline_option_ask must be > 0"
            )

        if observed_option_bid < 0:
            raise ValueError(
                "observed_option_bid must be >= 0"
            )

        return (
            observed_option_bid
            - baseline_option_ask
        ) / baseline_option_ask

    @staticmethod
    def option_mark_return(
        *,
        baseline_mark: float,
        observed_mark: float,
    ) -> float:
        if baseline_mark <= 0:
            raise ValueError(
                "baseline_mark must be > 0"
            )

        return (
            observed_mark - baseline_mark
        ) / baseline_mark

    @staticmethod
    def intrinsic_value(
        *,
        option_right: str,
        underlying_price: float,
        strike: float,
    ) -> float:
        right = option_right.lower()

        if right == "call":
            return max(
                0.0,
                underlying_price - strike,
            )

        if right == "put":
            return max(
                0.0,
                strike - underlying_price,
            )

        raise ValueError(
            "option_right must be call or put"
        )

    @classmethod
    def expiry_executable_return(
        cls,
        *,
        baseline_option_ask: float,
        option_right: str,
        underlying_price_at_expiry: float,
        strike: float,
    ) -> tuple[float, float]:
        settlement_value = cls.intrinsic_value(
            option_right=option_right,
            underlying_price=underlying_price_at_expiry,
            strike=strike,
        )

        executable_return = (
            cls.option_executable_return(
                baseline_option_ask=(
                    baseline_option_ask
                ),
                observed_option_bid=(
                    settlement_value
                ),
            )
        )

        return (
            settlement_value,
            executable_return,
        )
