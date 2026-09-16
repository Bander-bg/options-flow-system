from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

from alpaca.common.exceptions import APIError
from alpaca.data.enums import OptionsFeed
from alpaca.trading.enums import AssetStatus

from weekly.domain.enums import OptionRight
from weekly.providers.alpaca_options_provider import (
    AlpacaOptionsProvider,
    AlpacaOptionsProviderError,
)


TARGET_EXPIRY = date(2026, 9, 18)


def make_contract(
    *,
    symbol: str,
    right: str,
    strike: float,
):
    return SimpleNamespace(
        symbol=symbol,
        underlying_symbol="AAPL",
        root_symbol="AAPL",
        expiration_date=TARGET_EXPIRY,
        type=right,
        status="active",
        tradable=True,
        size=100,
        strike_price=strike,
    )


def make_snapshot(
    *,
    bid: float,
    ask: float,
    delta: float,
    iv: float,
):
    quote = SimpleNamespace(
        bid_price=bid,
        ask_price=ask,
        timestamp=datetime(
            2026,
            9,
            13,
            15,
            30,
            tzinfo=timezone.utc,
        ),
    )

    greeks = SimpleNamespace(
        delta=delta,
        gamma=0.04,
        theta=-0.12,
        vega=0.18,
    )

    return SimpleNamespace(
        latest_quote=quote,
        greeks=greeks,
        implied_volatility=iv,
    )


def make_api_error(
    *,
    status_code: int,
    message: str,
):
    http_error = SimpleNamespace(
        response=SimpleNamespace(
            status_code=status_code,
        )
    )

    return APIError(
        json.dumps(
            {
                "code": status_code,
                "message": message,
            }
        ),
        http_error,
    )


class FakeTradingClient:
    def __init__(self):
        self.requests = []

    def get_option_contracts(
        self,
        request,
    ):
        self.requests.append(request)

        if request.page_token is None:
            return SimpleNamespace(
                option_contracts=[
                    make_contract(
                        symbol="AAPL260918C00200000",
                        right="call",
                        strike=200.0,
                    )
                ],
                next_page_token="PAGE_2",
            )

        if request.page_token == "PAGE_2":
            return SimpleNamespace(
                option_contracts=[
                    make_contract(
                        symbol="AAPL260918P00195000",
                        right="put",
                        strike=195.0,
                    )
                ],
                next_page_token=None,
            )

        raise AssertionError(
            "Unexpected page token."
        )


class FakeFallbackOptionDataClient:
    def __init__(self):
        self.feeds = []

    def get_option_chain(
        self,
        request,
    ):
        self.feeds.append(
            request.feed
        )

        assert (
            request.underlying_symbol
            == "AAPL"
        )

        assert (
            request.expiration_date
            == TARGET_EXPIRY
        )

        if (
            request.feed
            is OptionsFeed.OPRA
        ):
            raise make_api_error(
                status_code=403,
                message=(
                    "subscription not permitted"
                ),
            )

        return {
            "AAPL260918C00200000":
                make_snapshot(
                    bid=4.80,
                    ask=5.00,
                    delta=0.52,
                    iv=0.31,
                ),
            "AAPL260918P00195000":
                make_snapshot(
                    bid=3.90,
                    ask=4.10,
                    delta=-0.46,
                    iv=0.34,
                ),
        }


class FakeServerErrorOptionDataClient:
    def __init__(self):
        self.feeds = []

    def get_option_chain(
        self,
        request,
    ):
        self.feeds.append(
            request.feed
        )

        raise make_api_error(
            status_code=500,
            message="server error",
        )


class FakeMissingSnapshotClient:
    def __init__(self):
        self.feeds = []

    def get_option_chain(
        self,
        request,
    ):
        self.feeds.append(
            request.feed
        )

        return {
            "AAPL260918C00200000":
                make_snapshot(
                    bid=4.80,
                    ask=5.00,
                    delta=0.52,
                    iv=0.31,
                )
        }


def main():
    # --------------------------------------------------
    # 1) Exact-expiry metadata + pagination
    # --------------------------------------------------

    trading_client = FakeTradingClient()
    option_client = (
        FakeFallbackOptionDataClient()
    )

    provider = AlpacaOptionsProvider(
        preferred_feed="opra",
        trading_client=trading_client,
        option_data_client=option_client,
    )

    result = (
        provider.get_contract_candidates(
            ticker="aapl",
            target_expiry=TARGET_EXPIRY,
        )
    )

    assert len(
        trading_client.requests
    ) == 2

    first_request = (
        trading_client.requests[0]
    )

    second_request = (
        trading_client.requests[1]
    )

    assert (
        first_request.underlying_symbols
        == ["AAPL"]
    )

    assert (
        first_request.status
        is AssetStatus.ACTIVE
    )

    assert (
        first_request.expiration_date_gte
        == TARGET_EXPIRY
    )

    assert (
        first_request.expiration_date_lte
        == TARGET_EXPIRY
    )

    assert (
        first_request.page_token
        is None
    )

    assert (
        second_request.page_token
        == "PAGE_2"
    )

    # --------------------------------------------------
    # 2) OPRA -> INDICATIVE only on entitlement 403
    # --------------------------------------------------

    assert option_client.feeds == [
        OptionsFeed.OPRA,
        OptionsFeed.INDICATIVE,
    ]

    assert result.feed == "indicative"
    assert result.provider == "ALPACA"

    # --------------------------------------------------
    # 3) Candidate mapping
    # --------------------------------------------------

    assert result.ticker == "AAPL"
    assert (
        result.target_expiry
        == TARGET_EXPIRY
    )

    assert len(
        result.candidates
    ) == 2

    call_candidate = (
        result.candidates[0]
    )

    put_candidate = (
        result.candidates[1]
    )

    assert (
        call_candidate.symbol
        == "AAPL260918C00200000"
    )

    assert (
        call_candidate.right
        is OptionRight.CALL
    )

    assert (
        call_candidate.expiry
        == TARGET_EXPIRY
    )

    assert (
        call_candidate.strike
        == 200.0
    )

    assert (
        call_candidate.active
        is True
    )

    assert (
        call_candidate.tradable
        is True
    )

    assert (
        call_candidate.size
        == 100
    )

    assert (
        call_candidate.bid
        == 4.80
    )

    assert (
        call_candidate.ask
        == 5.00
    )

    assert (
        call_candidate.delta
        == 0.52
    )

    assert (
        call_candidate.gamma
        == 0.04
    )

    assert (
        call_candidate.theta
        == -0.12
    )

    assert (
        call_candidate.vega
        == 0.18
    )

    assert (
        call_candidate.iv
        == 0.31
    )

    assert (
        call_candidate.quote_at
        is not None
    )

    assert (
        call_candidate.quote_at.tzinfo
        is not None
    )

    assert (
        put_candidate.right
        is OptionRight.PUT
    )

    assert (
        put_candidate.delta
        == -0.46
    )

    # --------------------------------------------------
    # 4) Missing snapshot stays UNKNOWN-like
    # --------------------------------------------------

    missing_provider = (
        AlpacaOptionsProvider(
            preferred_feed="indicative",
            trading_client=FakeTradingClient(),
            option_data_client=(
                FakeMissingSnapshotClient()
            ),
        )
    )

    missing_result = (
        missing_provider
        .get_contract_candidates(
            ticker="AAPL",
            target_expiry=TARGET_EXPIRY,
        )
    )

    missing_put = next(
        item
        for item
        in missing_result.candidates
        if item.right
        is OptionRight.PUT
    )

    assert missing_put.bid is None
    assert missing_put.ask is None
    assert (
        missing_put.quote_at
        is None
    )
    assert missing_put.delta is None
    assert missing_put.iv is None

    # --------------------------------------------------
    # 5) Non-entitlement error must NOT fallback
    # --------------------------------------------------

    server_error_client = (
        FakeServerErrorOptionDataClient()
    )

    server_error_provider = (
        AlpacaOptionsProvider(
            preferred_feed="opra",
            trading_client=(
                FakeTradingClient()
            ),
            option_data_client=(
                server_error_client
            ),
        )
    )

    try:
        server_error_provider.get_contract_candidates(
            ticker="AAPL",
            target_expiry=TARGET_EXPIRY,
        )
    except AlpacaOptionsProviderError:
        pass
    else:
        raise AssertionError(
            "500 error must raise "
            "AlpacaOptionsProviderError."
        )

    assert server_error_client.feeds == [
        OptionsFeed.OPRA
    ]

    # --------------------------------------------------
    # 6) Listed expiries from actual contract metadata
    # --------------------------------------------------

    expiry_provider = AlpacaOptionsProvider(
        preferred_feed="opra",
        trading_client=FakeTradingClient(),
        option_data_client=FakeFallbackOptionDataClient(),
    )

    listed_expiries = expiry_provider.get_listed_expiries(
        ticker="aapl",
        start_date=date(2026, 9, 13),
        end_date=date(2026, 9, 30),
    )

    assert listed_expiries == (
        TARGET_EXPIRY,
    )

    # --------------------------------------------------
    # 6) Listed expiries from actual contract metadata
    # --------------------------------------------------

    expiry_provider = AlpacaOptionsProvider(
        preferred_feed="opra",
        trading_client=FakeTradingClient(),
        option_data_client=FakeFallbackOptionDataClient(),
    )

    listed_expiries = expiry_provider.get_listed_expiries(
        ticker="aapl",
        start_date=date(2026, 9, 13),
        end_date=date(2026, 9, 30),
    )

    assert listed_expiries == (
        TARGET_EXPIRY,
    )

    print(
        "1. exact-expiry metadata request: PASS"
    )
    print(
        "2. contract pagination: PASS"
    )
    print(
        "3. ticker normalization: PASS"
    )
    print(
        "4. OPRA -> INDICATIVE 403 fallback: PASS"
    )
    print(
        "5. actual feed provenance: PASS"
    )
    print(
        "6. CALL/PUT contract mapping: PASS"
    )
    print(
        "7. quote + Greeks + IV mapping: PASS"
    )
    print(
        "8. missing snapshot preserves None evidence: PASS"
    )
    print(
        "9. non-403 error does not fallback: PASS"
    )
    print(
        "10. listed expiries extraction: PASS"
    )

    print()
    print("=" * 70)
    print(
        "ALPACA OPTIONS PROVIDER: PASS 10/10"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
