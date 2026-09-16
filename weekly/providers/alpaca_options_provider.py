from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.enums import OptionsFeed
from alpaca.data.historical.option import (
    OptionHistoricalDataClient,
)
from alpaca.data.requests import OptionChainRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import (
    GetOptionContractsRequest,
)

from config import load_weekly_config
from weekly.domain.enums import OptionRight
from weekly.services.eligible_contract_service import (
    OptionContractCandidate,
)


class AlpacaOptionsProviderError(RuntimeError):
    """Raised when Alpaca option data cannot be retrieved safely."""


@dataclass(frozen=True)
class OptionCandidatesResult:
    ticker: str
    target_expiry: date
    provider: str
    feed: str
    candidates: tuple[OptionContractCandidate, ...]

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError(
                "OptionCandidatesResult.ticker cannot be empty."
            )

        if self.provider != "ALPACA":
            raise ValueError(
                "OptionCandidatesResult.provider must be ALPACA."
            )

        if self.feed not in {
            OptionsFeed.OPRA.value,
            OptionsFeed.INDICATIVE.value,
        }:
            raise ValueError(
                "OptionCandidatesResult.feed must be "
                "opra or indicative."
            )


def _get_env_value(
    *names: str,
) -> str | None:
    for name in names:
        value = os.getenv(name)

        if value:
            stripped = value.strip()

            if stripped:
                return stripped

    return None


def _normalize_feed(
    value: str | OptionsFeed,
) -> OptionsFeed:
    if isinstance(value, OptionsFeed):
        feed = value

    else:
        normalized = str(value).strip().lower()

        try:
            feed = OptionsFeed(normalized)
        except ValueError as exc:
            raise ValueError(
                "Options feed must be "
                "'opra' or 'indicative'."
            ) from exc

    if feed not in {
        OptionsFeed.OPRA,
        OptionsFeed.INDICATIVE,
    }:
        raise ValueError(
            "Options feed must be "
            "'opra' or 'indicative'."
        )

    return feed


def _is_opra_entitlement_error(
    exc: APIError,
) -> bool:
    status_code = getattr(
        exc,
        "status_code",
        None,
    )

    if status_code == 403:
        return True

    text = str(exc).lower()

    entitlement_markers = (
        "403",
        "subscription",
        "not permitted",
        "not authorized",
        "forbidden",
    )

    return any(
        marker in text
        for marker in entitlement_markers
    )


class AlpacaOptionsProvider:
    """
    weekly_v1 Alpaca option provider.

    Responsibilities:
    - fetch exact-expiry active option contract metadata
    - handle contract pagination
    - fetch exact-expiry option snapshots
    - use configured preferred options feed
    - fall back OPRA -> INDICATIVE only on entitlement/403
    - combine metadata + quote + Greeks + IV
    - return OptionContractCandidate objects

    Explicitly not responsible for:
    - expected-move calculation
    - contract eligibility rules
    - ranking contracts
    - signal state transitions
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        preferred_feed: str | OptionsFeed | None = None,
        trading_client: TradingClient | None = None,
        option_data_client: OptionHistoricalDataClient | None = None,
    ) -> None:
        load_dotenv()

        if preferred_feed is None:
            config = load_weekly_config(
                require_runtime_ready=True
            )

            preferred_feed = config[
                "market"
            ][
                "option_data_feed_preferred"
            ]

        self.preferred_feed = _normalize_feed(
            preferred_feed
        )

        if (
            trading_client is not None
            and option_data_client is not None
        ):
            self.trading_client = trading_client
            self.option_data_client = option_data_client
            return

        resolved_api_key = (
            api_key
            or _get_env_value(
                "ALPACA_API_KEY",
                "ALPACA_KEY",
                "APCA_API_KEY_ID",
            )
        )

        resolved_secret_key = (
            secret_key
            or _get_env_value(
                "ALPACA_SECRET_KEY",
                "ALPACA_SECRET",
                "APCA_API_SECRET_KEY",
            )
        )

        if (
            not resolved_api_key
            or not resolved_secret_key
        ):
            raise AlpacaOptionsProviderError(
                "Alpaca API credentials were not found in .env."
            )

        self.trading_client = (
            trading_client
            if trading_client is not None
            else TradingClient(
                resolved_api_key,
                resolved_secret_key,
                paper=True,
            )
        )

        self.option_data_client = (
            option_data_client
            if option_data_client is not None
            else OptionHistoricalDataClient(
                resolved_api_key,
                resolved_secret_key,
            )
        )

    def get_contract_candidates(
        self,
        *,
        ticker: str,
        target_expiry: date,
    ) -> OptionCandidatesResult:

        normalized_ticker = (
            ticker.strip().upper()
        )

        if not normalized_ticker:
            raise ValueError(
                "ticker cannot be empty."
            )

        if not isinstance(
            target_expiry,
            date,
        ):
            raise ValueError(
                "target_expiry must be date."
            )

        contracts = self._fetch_contract_metadata(
            ticker=normalized_ticker,
            target_expiry=target_expiry,
        )

        feeds_to_try = [
            self.preferred_feed
        ]

        if (
            self.preferred_feed
            is OptionsFeed.OPRA
        ):
            feeds_to_try.append(
                OptionsFeed.INDICATIVE
            )

        last_error: Exception | None = None

        for index, feed in enumerate(
            feeds_to_try
        ):
            try:
                snapshots = (
                    self._fetch_option_chain(
                        ticker=normalized_ticker,
                        target_expiry=target_expiry,
                        feed=feed,
                    )
                )

                candidates = (
                    self._combine_contracts_and_snapshots(
                        contracts=contracts,
                        snapshots=snapshots,
                    )
                )

                return OptionCandidatesResult(
                    ticker=normalized_ticker,
                    target_expiry=target_expiry,
                    provider="ALPACA",
                    feed=feed.value,
                    candidates=candidates,
                )

            except APIError as exc:
                last_error = exc

                has_fallback = (
                    index
                    < len(feeds_to_try) - 1
                )

                should_fallback = (
                    feed is OptionsFeed.OPRA
                    and has_fallback
                    and _is_opra_entitlement_error(
                        exc
                    )
                )

                if should_fallback:
                    continue

                raise AlpacaOptionsProviderError(
                    "Alpaca option-chain request failed "
                    f"for {normalized_ticker} "
                    f"using feed={feed.value}: {exc}"
                ) from exc

            except AlpacaOptionsProviderError:
                raise

            except Exception as exc:
                last_error = exc

                raise AlpacaOptionsProviderError(
                    "Unexpected Alpaca options error "
                    f"for {normalized_ticker} "
                    f"using feed={feed.value}: {exc}"
                ) from exc

        raise AlpacaOptionsProviderError(
            "Alpaca option-chain request failed "
            f"for {normalized_ticker}: {last_error}"
        )

    def _fetch_contract_metadata(
        self,
        *,
        ticker: str,
        target_expiry: date,
    ) -> tuple:

        all_contracts = []
        page_token = None

        while True:
            request = GetOptionContractsRequest(
                underlying_symbols=[
                    ticker
                ],
                status=AssetStatus.ACTIVE,
                expiration_date_gte=(
                    target_expiry
                ),
                expiration_date_lte=(
                    target_expiry
                ),
                limit=1000,
                page_token=page_token,
            )

            response = (
                self.trading_client
                .get_option_contracts(
                    request
                )
            )

            page = (
                response.option_contracts
                or []
            )

            all_contracts.extend(
                page
            )

            page_token = getattr(
                response,
                "next_page_token",
                None,
            )

            if not page_token:
                break

        return tuple(
            all_contracts
        )

    def _fetch_option_chain(
        self,
        *,
        ticker: str,
        target_expiry: date,
        feed: OptionsFeed,
    ) -> dict:

        request = OptionChainRequest(
            underlying_symbol=ticker,
            feed=feed,
            expiration_date=target_expiry,
        )

        response = (
            self.option_data_client
            .get_option_chain(
                request
            )
        )

        if not isinstance(
            response,
            dict,
        ):
            try:
                return dict(response)
            except Exception as exc:
                raise AlpacaOptionsProviderError(
                    "Alpaca option-chain response "
                    "could not be converted to dict."
                ) from exc

        return response

    @staticmethod
    def _combine_contracts_and_snapshots(
        *,
        contracts: Iterable,
        snapshots: dict,
    ) -> tuple[OptionContractCandidate, ...]:

        candidates = []

        for contract in contracts:
            symbol = str(
                contract.symbol
            ).strip()

            if not symbol:
                raise AlpacaOptionsProviderError(
                    "Alpaca option contract "
                    "is missing symbol."
                )

            raw_type = getattr(
                contract.type,
                "value",
                contract.type,
            )

            try:
                right = OptionRight(
                    str(raw_type).lower()
                )
            except ValueError as exc:
                raise AlpacaOptionsProviderError(
                    "Unsupported Alpaca option "
                    f"type: {raw_type!r}"
                ) from exc

            raw_status = getattr(
                contract.status,
                "value",
                contract.status,
            )

            active = (
                str(raw_status)
                .strip()
                .lower()
                == "active"
            )

            try:
                size = (
                    int(contract.size)
                    if contract.size
                    is not None
                    else None
                )
            except (
                TypeError,
                ValueError,
            ):
                size = None

            snapshot = snapshots.get(
                symbol
            )

            latest_quote = (
                getattr(
                    snapshot,
                    "latest_quote",
                    None,
                )
                if snapshot is not None
                else None
            )

            greeks = (
                getattr(
                    snapshot,
                    "greeks",
                    None,
                )
                if snapshot is not None
                else None
            )

            bid = (
                float(
                    latest_quote.bid_price
                )
                if (
                    latest_quote is not None
                    and latest_quote.bid_price
                    is not None
                )
                else None
            )

            ask = (
                float(
                    latest_quote.ask_price
                )
                if (
                    latest_quote is not None
                    and latest_quote.ask_price
                    is not None
                )
                else None
            )

            quote_at = (
                latest_quote.timestamp
                if latest_quote
                is not None
                else None
            )

            if (
                quote_at is not None
                and quote_at.tzinfo is None
            ):
                raise AlpacaOptionsProviderError(
                    "Alpaca option quote timestamp "
                    "must be timezone-aware."
                )

            delta = (
                float(greeks.delta)
                if (
                    greeks is not None
                    and greeks.delta
                    is not None
                )
                else None
            )

            gamma = (
                float(greeks.gamma)
                if (
                    greeks is not None
                    and greeks.gamma
                    is not None
                )
                else None
            )

            theta = (
                float(greeks.theta)
                if (
                    greeks is not None
                    and greeks.theta
                    is not None
                )
                else None
            )

            vega = (
                float(greeks.vega)
                if (
                    greeks is not None
                    and greeks.vega
                    is not None
                )
                else None
            )

            raw_iv = (
                getattr(
                    snapshot,
                    "implied_volatility",
                    None,
                )
                if snapshot is not None
                else None
            )

            iv = (
                float(raw_iv)
                if raw_iv is not None
                else None
            )

            candidates.append(
                OptionContractCandidate(
                    symbol=symbol,
                    underlying_symbol=str(
                        contract.underlying_symbol
                    ).strip().upper(),
                    root_symbol=str(
                        contract.root_symbol
                    ).strip().upper(),
                    expiry=(
                        contract.expiration_date
                    ),
                    right=right,
                    strike=float(
                        contract.strike_price
                    ),
                    active=active,
                    tradable=bool(
                        contract.tradable
                    ),
                    size=size,
                    bid=bid,
                    ask=ask,
                    quote_at=quote_at,
                    delta=delta,
                    gamma=gamma,
                    theta=theta,
                    vega=vega,
                    iv=iv,
                )
            )

        candidates.sort(
            key=lambda item: item.symbol
        )

        return tuple(
            candidates
        )

    def get_listed_expiries(
        self,
        *,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> tuple[date, ...]:
        normalized_ticker = (
            ticker.strip().upper()
        )

        if not normalized_ticker:
            raise ValueError(
                "ticker cannot be empty."
            )

        if not isinstance(
            start_date,
            date,
        ):
            raise ValueError(
                "start_date must be date."
            )

        if not isinstance(
            end_date,
            date,
        ):
            raise ValueError(
                "end_date must be date."
            )

        if end_date < start_date:
            raise ValueError(
                "end_date must be >= start_date."
            )

        expiries: set[date] = set()
        page_token = None

        while True:
            request = GetOptionContractsRequest(
                underlying_symbols=[
                    normalized_ticker
                ],
                status=AssetStatus.ACTIVE,
                expiration_date_gte=(
                    start_date
                ),
                expiration_date_lte=(
                    end_date
                ),
                limit=1000,
                page_token=page_token,
            )

            try:
                response = (
                    self.trading_client
                    .get_option_contracts(
                        request
                    )
                )
            except APIError as exc:
                raise AlpacaOptionsProviderError(
                    "Alpaca listed-expiries "
                    "request failed for "
                    f"{normalized_ticker}: {exc}"
                ) from exc

            contracts = (
                response.option_contracts
                or []
            )

            for contract in contracts:
                expiry = getattr(
                    contract,
                    "expiration_date",
                    None,
                )

                if expiry is None:
                    continue

                if not isinstance(
                    expiry,
                    date,
                ):
                    raise AlpacaOptionsProviderError(
                        "Alpaca option contract "
                        "has invalid expiration_date."
                    )

                if (
                    start_date
                    <= expiry
                    <= end_date
                ):
                    expiries.add(
                        expiry
                    )

            page_token = getattr(
                response,
                "next_page_token",
                None,
            )

            if not page_token:
                break

        return tuple(
            sorted(expiries)
        )
