from __future__ import annotations

import os
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv


load_dotenv()


UW_API_KEY = os.getenv("UW_API_KEY")

if not UW_API_KEY:
    raise RuntimeError(
        "UW_API_KEY was not found in .env"
    )


HEADERS = {
    "Authorization": f"Bearer {UW_API_KEY}",
    "Accept": "application/json",
}


TICKERS = [
    "AAPL",
    "TSLA",
    "NVDA",
    "GOOGL",
    "META",
]


LIMIT_PER_TICKER = 100


def fetch_alerts(ticker: str) -> list[dict]:
    url = (
        "https://api.unusualwhales.com"
        f"/api/stock/{ticker}/flow-alerts"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        params={"limit": LIMIT_PER_TICKER},
        timeout=30,
    )

    print(
        f"{ticker}: HTTP {response.status_code}"
    )

    if response.status_code != 200:
        print(response.text[:500])
        return []

    payload = response.json()

    data = payload.get("data", [])

    if not isinstance(data, list):
        print(
            f"{ticker}: unexpected data format: "
            f"{type(data).__name__}"
        )
        return []

    return data


def main() -> None:
    print("=" * 75)
    print("UNUSUAL WHALES FLOW ALERT FIELD / DEDUP TEST")
    print("=" * 75)
    print()

    all_alerts: list[tuple[str, dict]] = []

    field_counter = Counter()

    id_present = 0
    trade_ids_present = 0
    nonempty_trade_ids = 0

    for ticker in TICKERS:
        alerts = fetch_alerts(ticker)

        print(
            f"{ticker}: alerts_returned = {len(alerts)}"
        )

        for alert in alerts:
            all_alerts.append(
                (ticker, alert)
            )

            field_counter.update(
                alert.keys()
            )

            if "id" in alert:
                id_present += 1

            if "trade_ids" in alert:
                trade_ids_present += 1

                trade_ids = alert.get(
                    "trade_ids"
                )

                if (
                    isinstance(trade_ids, list)
                    and len(trade_ids) > 0
                ):
                    nonempty_trade_ids += 1

        print()

    total_alerts = len(all_alerts)

    print("=" * 75)
    print("FIELD AVAILABILITY")
    print("=" * 75)

    print("total_alerts:", total_alerts)

    print(
        "alerts_with_id:",
        id_present,
    )

    print(
        "alerts_with_trade_ids_field:",
        trade_ids_present,
    )

    print(
        "alerts_with_nonempty_trade_ids:",
        nonempty_trade_ids,
    )

    print()
    print("Fields observed in REST responses:")

    for field in sorted(field_counter):
        print(
            f" - {field}: "
            f"{field_counter[field]}/{total_alerts}"
        )

    # --------------------------------------------------
    # Alert UUID uniqueness
    # --------------------------------------------------

    ids = []

    for _, alert in all_alerts:
        alert_id = alert.get("id")

        if alert_id:
            ids.append(str(alert_id))

    duplicate_alert_ids = (
        len(ids) - len(set(ids))
    )

    print()
    print("=" * 75)
    print("ALERT UUID TEST")
    print("=" * 75)

    print(
        "nonempty_alert_ids:",
        len(ids),
    )

    print(
        "duplicate_alert_ids:",
        duplicate_alert_ids,
    )

    # --------------------------------------------------
    # Trade ID overlap across DIFFERENT alerts
    # --------------------------------------------------

    trade_id_to_alerts = defaultdict(set)

    alert_identity = {}

    for index, (ticker, alert) in enumerate(
        all_alerts
    ):
        alert_id = alert.get("id")

        if alert_id:
            identity = f"id:{alert_id}"
        else:
            identity = (
                f"index:{index}:"
                f"{ticker}:"
                f"{alert.get('option_chain')}:"
                f"{alert.get('created_at')}:"
                f"{alert.get('alert_rule')}"
            )

        alert_identity[identity] = {
            "ticker": ticker,
            "option_chain": alert.get(
                "option_chain"
            ),
            "created_at": alert.get(
                "created_at"
            ),
            "alert_rule": alert.get(
                "alert_rule"
            ),
        }

        trade_ids = alert.get(
            "trade_ids"
        )

        if not isinstance(
            trade_ids,
            list,
        ):
            continue

        for trade_id in trade_ids:
            if trade_id:
                trade_id_to_alerts[
                    str(trade_id)
                ].add(identity)

    overlapping_trade_ids = {
        trade_id: identities
        for trade_id, identities
        in trade_id_to_alerts.items()
        if len(identities) > 1
    }

    print()
    print("=" * 75)
    print("CROSS-ALERT TRADE-ID OVERLAP TEST")
    print("=" * 75)

    print(
        "unique_trade_ids_seen:",
        len(trade_id_to_alerts),
    )

    print(
        "trade_ids_present_in_multiple_alerts:",
        len(overlapping_trade_ids),
    )

    if overlapping_trade_ids:
        print()
        print(
            "Examples of overlapping trade_ids:"
        )

        for number, (
            trade_id,
            identities,
        ) in enumerate(
            overlapping_trade_ids.items(),
            start=1,
        ):
            print()
            print(
                f"Overlap #{number}"
            )
            print(
                "trade_id:",
                trade_id,
            )

            for identity in sorted(
                identities
            ):
                print(
                    " alert:",
                    identity,
                    alert_identity.get(
                        identity
                    ),
                )

            if number >= 10:
                break

    # --------------------------------------------------
    # Show one real REST alert's complete field names
    # --------------------------------------------------

    print()
    print("=" * 75)
    print("FIRST ALERT FIELD SAMPLE")
    print("=" * 75)

    if all_alerts:
        ticker, sample = all_alerts[0]

        print(
            "ticker:",
            ticker,
        )

        for key in sorted(sample):
            value = sample[key]

            # Avoid huge output from long arrays.
            if (
                isinstance(value, list)
                and len(value) > 10
            ):
                print(
                    f"{key}: "
                    f"<list with {len(value)} items>"
                )
            else:
                print(
                    f"{key}: {value}"
                )

    else:
        print(
            "No alerts returned."
        )

    # --------------------------------------------------
    # Final deduction
    # --------------------------------------------------

    print()
    print("=" * 75)
    print("PRELIMINARY DEDUP RESULT")
    print("=" * 75)

    if total_alerts == 0:
        print(
            "flow_dedup_level = UNRESOLVED"
        )

    elif (
        trade_ids_present > 0
        and nonempty_trade_ids > 0
    ):
        print(
            "trade_ids are available in REST."
        )
        print(
            "Next step: test whether individual "
            "OptionTrade details can be retrieved."
        )

        if overlapping_trade_ids:
            print(
                "Cross-alert trade overlap: DETECTED"
            )
        else:
            print(
                "Cross-alert trade overlap: "
                "NOT DETECTED IN THIS SAMPLE"
            )

        print(
            "flow_dedup_level is not final yet."
        )

    elif id_present == total_alerts:
        print(
            "REST provides alert UUIDs but "
            "not usable trade_ids."
        )
        print(
            'preliminary flow_dedup_level = "alert_uuid"'
        )

    else:
        print(
            "Neither usable trade_ids nor "
            "consistent alert UUIDs are available."
        )
        print(
            'preliminary flow_dedup_level = '
            '"alert_composite"'
        )


if __name__ == "__main__":
    main()