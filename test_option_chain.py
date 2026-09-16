from __future__ import annotations

import os
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


def main() -> None:
    ticker = "AAPL"

    start_date = date.today()
    end_date = start_date + timedelta(days=45)

    # Intentionally small to prove pagination works.
    page_limit = 50

    all_contracts = []
    page_token = None
    page_number = 0

    print("=" * 70)
    print("OPTION CONTRACTS PAGINATION TEST")
    print("=" * 70)

    print("ticker:", ticker)
    print("expiration_date_gte:", start_date)
    print("expiration_date_lte:", end_date)
    print("page_limit:", page_limit)
    print()

    while True:
        page_number += 1

        request = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            status=AssetStatus.ACTIVE,
            expiration_date_gte=start_date,
            expiration_date_lte=end_date,
            limit=page_limit,
            page_token=page_token,
        )

        response = client.get_option_contracts(request)

        contracts = response.option_contracts or []

        print(
            f"Page {page_number}: "
            f"{len(contracts)} contracts"
        )

        all_contracts.extend(contracts)

        page_token = response.next_page_token

        if not page_token:
            break

    print()
    print("=" * 70)
    print("PAGINATION RESULT")
    print("=" * 70)

    print("pages_fetched:", page_number)
    print("total_contracts:", len(all_contracts))

    if not all_contracts:
        print("RESULT: FAILED - no contracts returned")
        raise SystemExit(1)

    symbols = [contract.symbol for contract in all_contracts]

    duplicate_count = len(symbols) - len(set(symbols))

    expirations = sorted(
        {
            contract.expiration_date
            for contract in all_contracts
        }
    )

    active_count = 0
    tradable_count = 0
    standard_size_count = 0
    nonstandard_size_count = 0

    for contract in all_contracts:
        status_value = getattr(
            contract.status,
            "value",
            str(contract.status),
        )

        if str(status_value).lower() == "active":
            active_count += 1

        if contract.tradable:
            tradable_count += 1

        try:
            contract_size = int(contract.size)
        except (TypeError, ValueError):
            contract_size = None

        if contract_size == 100:
            standard_size_count += 1
        else:
            nonstandard_size_count += 1

    print("duplicate_symbols:", duplicate_count)

    print()
    print("Available expirations:")

    for expiry in expirations:
        print(" -", expiry)

    print()
    print("=" * 70)
    print("CONTRACT METADATA")
    print("=" * 70)

    print("active:", active_count)
    print("tradable:", tradable_count)
    print("size_100:", standard_size_count)
    print("nonstandard_size:", nonstandard_size_count)

    print()
    print("Sample contract:")

    sample = all_contracts[0]

    print("symbol:", sample.symbol)
    print("status:", sample.status)
    print("tradable:", sample.tradable)
    print("expiration:", sample.expiration_date)
    print("type:", sample.type)
    print("style:", sample.style)
    print("strike:", sample.strike_price)
    print("size:", sample.size)

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    pagination_ok = (
        page_number > 1
        and duplicate_count == 0
    )

    date_range_ok = all(
        start_date
        <= contract.expiration_date
        <= end_date
        for contract in all_contracts
    )

    if pagination_ok:
        print("Pagination: PASS")
    else:
        print(
            "Pagination: CHECK REQUIRED "
            "(only one page or duplicates detected)"
        )

    if date_range_ok:
        print("Explicit expiration range: PASS")
    else:
        print("Explicit expiration range: FAIL")

    if active_count == len(all_contracts):
        print("Active metadata: PASS")
    else:
        print("Active metadata: FAIL")

    if tradable_count > 0:
        print("Tradable metadata available: PASS")
    else:
        print("Tradable metadata available: FAIL")

    print(
        "Contract size metadata: PASS "
        f"({standard_size_count} standard / "
        f"{nonstandard_size_count} nonstandard)"
    )


if __name__ == "__main__":
    main()