from __future__ import annotations

import os
import re
from datetime import date, timedelta

from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import GetOptionContractsRequest


load_dotenv()


def get_env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


API_KEY = get_env_value(
    "ALPACA_API_KEY",
    "ALPACA_KEY",
    "APCA_API_KEY_ID",
)

SECRET_KEY = get_env_value(
    "ALPACA_SECRET_KEY",
    "ALPACA_SECRET",
    "APCA_API_SECRET_KEY",
)


if not API_KEY or not SECRET_KEY:
    raise RuntimeError(
        "Alpaca API credentials were not found in .env"
    )


client = TradingClient(
    API_KEY,
    SECRET_KEY,
    paper=True,
)


TICKERS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "GOOGL",
    "META",
]


def root_has_numeric_suffix(root_symbol: str) -> bool:
    return bool(
        re.search(r"\d+$", root_symbol)
    )


def fetch_all_contracts(
    ticker: str,
):
    start_date = date.today()
    end_date = start_date + timedelta(days=45)

    contracts = []
    page_token = None

    while True:
        request = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            status=AssetStatus.ACTIVE,
            expiration_date_gte=start_date,
            expiration_date_lte=end_date,
            limit=1000,
            page_token=page_token,
        )

        response = client.get_option_contracts(request)

        page = response.option_contracts or []

        contracts.extend(page)

        page_token = response.next_page_token

        if not page_token:
            break

    return contracts


def classify_contract(contract):
    try:
        size = int(contract.size)
    except (TypeError, ValueError):
        size = None

    root = str(contract.root_symbol)
    underlying = str(contract.underlying_symbol)

    numeric_suffix = root_has_numeric_suffix(root)

    root_matches_underlying = (
        root.upper() == underlying.upper()
    )

    size_is_100 = (
        size == 100
    )

    if numeric_suffix:
        status = "NONSTANDARD_ROOT"

    elif not root_matches_underlying:
        status = "ROOT_MISMATCH"

    elif not size_is_100:
        status = "NONSTANDARD_SIZE"

    else:
        # Important:
        # This means it passes the fields Alpaca exposes.
        # It is NOT absolute proof of standard deliverable.
        status = "OSI_SCREEN_PASS"

    return {
        "status": status,
        "root": root,
        "underlying": underlying,
        "size": size,
        "numeric_suffix": numeric_suffix,
        "root_matches_underlying": root_matches_underlying,
    }


def main():
    print("=" * 75)
    print("STANDARD CONTRACT / ROOT SYMBOL DIAGNOSTIC")
    print("=" * 75)
    print()

    grand_total = 0
    grand_pass = 0
    grand_suspicious = 0

    suspicious_examples = []

    for ticker in TICKERS:

        print("-" * 75)
        print(f"Ticker: {ticker}")
        print("-" * 75)

        contracts = fetch_all_contracts(ticker)

        total = len(contracts)

        counts = {
            "OSI_SCREEN_PASS": 0,
            "NONSTANDARD_ROOT": 0,
            "ROOT_MISMATCH": 0,
            "NONSTANDARD_SIZE": 0,
        }

        roots = set()

        for contract in contracts:

            result = classify_contract(contract)

            counts[result["status"]] += 1

            roots.add(
                result["root"]
            )

            if result["status"] != "OSI_SCREEN_PASS":

                if len(suspicious_examples) < 20:
                    suspicious_examples.append(
                        {
                            "ticker": ticker,
                            "symbol": contract.symbol,
                            **result,
                        }
                    )

        passed = counts["OSI_SCREEN_PASS"]

        suspicious = total - passed

        grand_total += total
        grand_pass += passed
        grand_suspicious += suspicious

        print("contracts:", total)
        print("roots:", sorted(roots))
        print(
            "osi_screen_pass:",
            counts["OSI_SCREEN_PASS"],
        )
        print(
            "nonstandard_root:",
            counts["NONSTANDARD_ROOT"],
        )
        print(
            "root_mismatch:",
            counts["ROOT_MISMATCH"],
        )
        print(
            "nonstandard_size:",
            counts["NONSTANDARD_SIZE"],
        )

        print()

    print("=" * 75)
    print("GLOBAL RESULT")
    print("=" * 75)

    print(
        "total_contracts:",
        grand_total,
    )

    print(
        "osi_screen_pass:",
        grand_pass,
    )

    print(
        "suspicious_contracts:",
        grand_suspicious,
    )

    print()

    if suspicious_examples:

        print("Suspicious examples:")

        for item in suspicious_examples:
            print(
                item
            )

    else:
        print(
            "No suspicious adjusted-root/size "
            "contracts detected in this sample."
        )

    print()
    print("=" * 75)
    print("IMPORTANT INTERPRETATION")
    print("=" * 75)

    print(
        "OSI_SCREEN_PASS means:"
    )

    print(
        "- status=ACTIVE was requested"
    )

    print(
        "- root_symbol == underlying_symbol"
    )

    print(
        "- no numeric suffix in root_symbol"
    )

    print(
        "- contract size == 100"
    )

    print()

    print(
        "It does NOT prove the deliverable is standard "
        "with absolute certainty because Alpaca's "
        "OptionContract model does not expose the full "
        "deliverable terms."
    )


if __name__ == "__main__":
    main()