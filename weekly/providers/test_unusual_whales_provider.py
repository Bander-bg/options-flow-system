from datetime import date

import weekly.providers.unusual_whales_provider as uw
from weekly.providers.unusual_whales_provider import (
    UnusualWhalesError,
    UnusualWhalesProvider,
)


class FakeResponse:
    def __init__(self, data, status_code=200, text=""):
        self.status_code = status_code
        self.data = data
        self.text = text

    def json(self):
        return {"data": self.data}


def main():
    original_get = uw.requests.get
    provider = UnusualWhalesProvider(api_key="test-key")

    try:
        def exact_date(url, **kwargs):
            return FakeResponse([
                {
                    "date": "2099-01-04",
                    "call_gamma": "100",
                    "put_gamma": "-20",
                },
                {
                    "date": "2099-01-05",
                    "call_gamma": "40",
                    "put_gamma": "-70",
                },
            ])

        uw.requests.get = exact_date

        result = provider.fetch_greek_exposure(
            ticker="aapl",
            trading_date=date(2099, 1, 5),
        )

        assert result.ticker == "AAPL"
        assert result.call_gamma == 40.0
        assert result.put_gamma == -70.0
        assert result.total_gex == -30.0
        print("1. exact-date GEX and total_gex: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse([
            {
                "date": "2099-01-04",
                "call_gamma": "10",
                "put_gamma": "-5",
            }
        ])

        assert provider.fetch_greek_exposure(
            ticker="AAPL",
            trading_date=date(2099, 1, 5),
        ) is None
        print("2. missing exact date -> None: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse([
            {
                "date": "2099-01-05",
                "call_gamma": "40",
                "put_gamma": "-70",
            },
            {
                "date": "2099-01-05",
                "call_gamma": "50",
                "put_gamma": "-60",
            },
        ])

        try:
            provider.fetch_greek_exposure(
                ticker="AAPL",
                trading_date=date(2099, 1, 5),
            )
        except UnusualWhalesError:
            pass
        else:
            raise AssertionError("duplicate rows must fail")

        print("3. duplicate same-date rows rejected: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse(
            [],
            status_code=401,
            text="unrecognized_token",
        )

        try:
            provider.fetch_greek_exposure(
                ticker="AAPL",
                trading_date=date(2099, 1, 5),
            )
        except UnusualWhalesError:
            pass
        else:
            raise AssertionError("HTTP error must fail")

        print("4. HTTP error handling: PASS")

        earnings_requests = []

        def earnings_ok(url, **kwargs):
            earnings_requests.append(
                {
                    "url": url,
                    "params": kwargs.get("params"),
                }
            )
            return FakeResponse([
                {
                    "ticker": "TSLA",
                    "next_earnings_date": "2099-02-01",
                    "er_time": "BMO",
                },
                {
                    "ticker": "AAPL",
                    "next_earnings_date": "2099-01-20",
                    "er_time": "AMC",
                },
            ])

        uw.requests.get = earnings_ok

        earnings = provider.fetch_earnings_snapshot(
            ticker="aapl",
        )

        assert earnings is not None
        assert earnings.ticker == "AAPL"
        assert earnings.next_earnings_date == date(
            2099, 1, 20
        )
        assert earnings.earnings_time == "AMC"
        assert earnings.provider == "UNUSUAL_WHALES"
        assert earnings.fetched_at is not None
        assert earnings_requests[0]["params"] == {
            "ticker": "AAPL"
        }

        print("5. earnings exact ticker and parsing: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse([
            {
                "ticker": "TSLA",
                "next_earnings_date": "2099-02-01",
                "er_time": "BMO",
            }
        ])

        assert provider.fetch_earnings_snapshot(
            ticker="AAPL",
        ) is None

        print("6. missing earnings ticker -> None: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse([
            {
                "ticker": "AAPL",
                "next_earnings_date": "not-a-date",
                "er_time": "AMC",
            }
        ])

        try:
            provider.fetch_earnings_snapshot(
                ticker="AAPL",
            )
        except UnusualWhalesError:
            pass
        else:
            raise AssertionError(
                "invalid earnings date must fail"
            )

        print("7. invalid earnings date rejected: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse([
            {
                "ticker": "AAPL",
                "next_earnings_date": "2099-01-20",
                "er_time": "AMC",
            },
            {
                "ticker": "AAPL",
                "next_earnings_date": "2099-01-21",
                "er_time": "BMO",
            },
        ])

        try:
            provider.fetch_earnings_snapshot(
                ticker="AAPL",
            )
        except UnusualWhalesError:
            pass
        else:
            raise AssertionError(
                "duplicate earnings rows must fail"
            )

        print("8. duplicate earnings rows rejected: PASS")

        uw.requests.get = lambda url, **kwargs: FakeResponse(
            [],
            status_code=401,
            text="unrecognized_token",
        )

        try:
            provider.fetch_earnings_snapshot(
                ticker="AAPL",
            )
        except UnusualWhalesError:
            pass
        else:
            raise AssertionError(
                "earnings HTTP error must fail"
            )

        print("9. earnings HTTP error handling: PASS")

    finally:
        uw.requests.get = original_get

    print()
    print("=" * 70)
    print("UNUSUAL WHALES PROVIDER: PASS 9/9")
    print("=" * 70)


if __name__ == "__main__":
    main()
