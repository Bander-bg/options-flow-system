from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests


UTC = ZoneInfo("UTC")


class UnusualWhalesError(RuntimeError):
    pass


class IncompleteFlowSessionError(
    UnusualWhalesError
):
    pass


@dataclass(frozen=True)
class GreekExposureSnapshot:
    ticker: str
    trading_date: date
    call_gamma: float
    put_gamma: float
    total_gex: float
    provider: str = "UNUSUAL_WHALES"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class EarningsSnapshot:
    ticker: str
    next_earnings_date: date | None
    earnings_time: str | None
    provider: str = "UNUSUAL_WHALES"
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class FlowAlertsBatch:
    ticker: str

    alerts: list[dict]

    pages_fetched: int
    rows_fetched: int

    session_coverage_complete: bool

    session_start_reached: bool
    history_exhausted: bool

    newest_created_at: datetime | None
    oldest_created_at: datetime | None

    provider: str = "UNUSUAL_WHALES"
    feed: str = "UNKNOWN"

    source_timestamp: datetime | None = None
    fetched_at: datetime | None = None

    freshness_status: str = "UNKNOWN"


def _parse_timestamp(
    value: Any,
) -> datetime:
    if value is None:
        raise UnusualWhalesError(
            "Flow alert created_at is missing."
        )

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError as exc:
        raise UnusualWhalesError(
            f"Invalid created_at: {value!r}"
        ) from exc

    if parsed.tzinfo is None:
        raise UnusualWhalesError(
            "Flow alert created_at "
            "must be timezone-aware."
        )

    return parsed.astimezone(
        UTC
    )


class UnusualWhalesProvider:

    FLOW_ALERTS_URL = (
        "https://api.unusualwhales.com"
        "/api/option-trades/flow-alerts"
    )

    GREEK_EXPOSURE_URL_TEMPLATE = (
        "https://api.unusualwhales.com"
        "/api/stock/{ticker}/greek-exposure"
    )

    STOCK_SCREENER_URL = (
        "https://api.unusualwhales.com"
        "/api/screener/stocks"
    )

    VOLATILITY_TERM_STRUCTURE_URL_TEMPLATE = (
        "https://api.unusualwhales.com"
        "/api/stock/{ticker}/volatility/term-structure"
    )

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.api_key = (
            api_key
            or os.getenv(
                "UW_API_KEY"
            )
        )

        if not self.api_key:
            raise UnusualWhalesError(
                "UW_API_KEY was not found."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be > 0"
            )

        self.timeout_seconds = (
            timeout_seconds
        )

        self.headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "Accept": "application/json",
        }

    def _request_flow_page(
        self,
        *,
        ticker: str,
        limit: int,
        older_than: str | None,
    ) -> list[dict]:

        params = {
            "ticker_symbol": ticker,
            "limit": limit,
        }

        if older_than is not None:
            params[
                "older_than"
            ] = older_than

        response = requests.get(
            self.FLOW_ALERTS_URL,
            headers=self.headers,
            params=params,
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise UnusualWhalesError(
                "UW flow-alert request failed. "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise UnusualWhalesError(
                "UW flow-alert response "
                "is not valid JSON."
            ) from exc

        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise UnusualWhalesError(
                "UW flow-alert response "
                "data is not a list."
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                raise UnusualWhalesError(
                    "UW flow-alert row "
                    "is not an object."
                )

            returned_ticker = row.get(
                "ticker"
            )

            if (
                returned_ticker is not None
                and str(
                    returned_ticker
                ).upper()
                != ticker.upper()
            ):
                raise UnusualWhalesError(
                    "UW returned an alert for "
                    "a different ticker."
                )

        return rows

    def fetch_session_to_date_flow_alerts(
        self,
        *,
        ticker: str,
        session_open_et: datetime,
        max_pages: int = 20,
        page_limit: int = 500,
        require_complete: bool = True,
    ) -> FlowAlertsBatch:
        """
        Fetch enough UW history to prove that all
        flow alerts for the current trading session
        are available.

        Coverage is complete when either:

        1) Pagination reaches an alert timestamp
           at or before the official session open.

        OR

        2) UW history is exhausted before that point,
           proving there are no earlier rows.

        If require_complete=True and completeness
        cannot be proven, Candidate generation
        must remain blocked.
        """

        if not ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        if session_open_et.tzinfo is None:
            raise ValueError(
                "session_open_et must be "
                "timezone-aware."
            )

        if max_pages < 1:
            raise ValueError(
                "max_pages must be >= 1"
            )

        if page_limit < 1:
            raise ValueError(
                "page_limit must be >= 1"
            )

        ticker = (
            ticker
            .upper()
            .strip()
        )

        session_open_utc = (
            session_open_et
            .astimezone(
                UTC
            )
        )

        all_rows: list[dict] = []

        older_than = None

        pages_fetched = 0

        session_start_reached = False
        history_exhausted = False

        seen_cursors: set[str] = set()

        newest_seen: datetime | None = None
        oldest_seen: datetime | None = None

        for _ in range(
            max_pages
        ):
            rows = (
                self._request_flow_page(
                    ticker=ticker,
                    limit=page_limit,
                    older_than=older_than,
                )
            )

            pages_fetched += 1

            if not rows:
                history_exhausted = True
                break

            timestamps = [
                _parse_timestamp(
                    row.get(
                        "created_at"
                    )
                )
                for row in rows
            ]

            for index in range(
                1,
                len(timestamps),
            ):
                if (
                    timestamps[index]
                    > timestamps[
                        index - 1
                    ]
                ):
                    raise UnusualWhalesError(
                        "UW flow-alert page "
                        "is not ordered "
                        "newest-to-oldest."
                    )

            page_newest = (
                timestamps[0]
            )

            page_oldest = (
                timestamps[-1]
            )

            if (
                newest_seen is None
                or page_newest
                > newest_seen
            ):
                newest_seen = (
                    page_newest
                )

            if (
                oldest_seen is None
                or page_oldest
                < oldest_seen
            ):
                oldest_seen = (
                    page_oldest
                )

            all_rows.extend(
                rows
            )

            if (
                page_oldest
                <= session_open_utc
            ):
                session_start_reached = True
                break

            if len(rows) < page_limit:
                history_exhausted = True
                break

            cursor = (
                page_oldest.isoformat()
            )

            if cursor in seen_cursors:
                raise UnusualWhalesError(
                    "UW pagination cursor "
                    "repeated."
                )

            seen_cursors.add(
                cursor
            )

            older_than = (
                cursor
            )

        session_coverage_complete = (
            session_start_reached
            or history_exhausted
        )

        fetched_at = datetime.now(
            UTC
        )

        batch = FlowAlertsBatch(
            ticker=ticker,

            alerts=all_rows,

            pages_fetched=pages_fetched,

            rows_fetched=len(
                all_rows
            ),

            session_coverage_complete=(
                session_coverage_complete
            ),

            session_start_reached=(
                session_start_reached
            ),

            history_exhausted=(
                history_exhausted
            ),

            newest_created_at=(
                newest_seen
            ),

            oldest_created_at=(
                oldest_seen
            ),

            provider="UNUSUAL_WHALES",

            feed="UNKNOWN",

            source_timestamp=(
                newest_seen
            ),

            fetched_at=(
                fetched_at
            ),

            freshness_status="UNKNOWN",
        )

        if (
            require_complete
            and not batch.session_coverage_complete
        ):
            raise IncompleteFlowSessionError(
                "UW Session-to-Date flow "
                "coverage could not be proven. "
                "Candidate generation must "
                "remain blocked."
            )

        return batch

    def fetch_greek_exposure(
        self,
        *,
        ticker: str,
        trading_date: date,
    ) -> GreekExposureSnapshot | None:

        if not ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        ticker = (
            ticker
            .upper()
            .strip()
        )

        url = (
            self.GREEK_EXPOSURE_URL_TEMPLATE
            .format(
                ticker=ticker
            )
        )

        response = requests.get(
            url,
            headers=self.headers,
            params={
                "date": trading_date.isoformat(),
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise UnusualWhalesError(
                "UW greek-exposure request failed. "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise UnusualWhalesError(
                "UW greek-exposure response "
                "is not valid JSON."
            ) from exc

        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise UnusualWhalesError(
                "UW greek-exposure response "
                "data is not a list."
            )

        matches = []

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                raise UnusualWhalesError(
                    "UW greek-exposure row "
                    "is not an object."
                )

            row_date_raw = row.get(
                "date"
            )

            if row_date_raw is None:
                raise UnusualWhalesError(
                    "UW greek-exposure row "
                    "is missing date."
                )

            try:
                row_date = date.fromisoformat(
                    str(row_date_raw)
                )

            except ValueError as exc:
                raise UnusualWhalesError(
                    "Invalid UW greek-exposure date: "
                    f"{row_date_raw!r}"
                ) from exc

            if row_date != trading_date:
                continue

            try:
                call_gamma = float(
                    row["call_gamma"]
                )
                put_gamma = float(
                    row["put_gamma"]
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                raise UnusualWhalesError(
                    "UW greek-exposure gamma "
                    "values are missing or invalid."
                ) from exc

            matches.append(
                GreekExposureSnapshot(
                    ticker=ticker,
                    trading_date=row_date,
                    call_gamma=call_gamma,
                    put_gamma=put_gamma,
                    total_gex=(
                        call_gamma
                        + put_gamma
                    ),
                    provider="UNUSUAL_WHALES",
                    fetched_at=datetime.now(
                        UTC
                    ),
                )
            )

        if not matches:
            return None

        if len(matches) != 1:
            raise UnusualWhalesError(
                "UW greek-exposure returned "
                "multiple rows for the same date."
            )

        return matches[0]

    def fetch_volatility_term_structure(
        self,
        *,
        ticker: str,
    ) -> list[dict]:

        if not ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        ticker = (
            ticker
            .upper()
            .strip()
        )

        url = (
            self.VOLATILITY_TERM_STRUCTURE_URL_TEMPLATE
            .format(ticker=ticker)
        )

        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise UnusualWhalesError(
                "UW volatility term-structure request failed. "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise UnusualWhalesError(
                "UW volatility term-structure response "
                "is not valid JSON."
            ) from exc

        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise UnusualWhalesError(
                "UW volatility term-structure response "
                "data is not a list."
            )

        normalized_rows = []

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                raise UnusualWhalesError(
                    "UW volatility term-structure row "
                    "is not an object."
                )

            normalized_rows.append(
                dict(row)
            )

        return normalized_rows

    def fetch_earnings_snapshot(
        self,
        *,
        ticker: str,
    ) -> EarningsSnapshot | None:

        if not ticker.strip():
            raise ValueError(
                "ticker cannot be empty"
            )

        ticker = (
            ticker
            .upper()
            .strip()
        )

        response = requests.get(
            self.STOCK_SCREENER_URL,
            headers=self.headers,
            params={
                "ticker": ticker,
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise UnusualWhalesError(
                "UW stock-screener request failed. "
                f"HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise UnusualWhalesError(
                "UW stock-screener response "
                "is not valid JSON."
            ) from exc

        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise UnusualWhalesError(
                "UW stock-screener response "
                "data is not a list."
            )

        matches = []

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                raise UnusualWhalesError(
                    "UW stock-screener row "
                    "is not an object."
                )

            row_ticker = str(
                row.get(
                    "ticker",
                    "",
                )
            ).upper().strip()

            if row_ticker != ticker:
                continue

            raw_date = row.get(
                "next_earnings_date"
            )

            if raw_date in (
                None,
                "",
            ):
                next_earnings_date = None

            else:
                try:
                    next_earnings_date = (
                        date.fromisoformat(
                            str(raw_date)[:10]
                        )
                    )

                except ValueError as exc:
                    raise UnusualWhalesError(
                        "Invalid UW "
                        "next_earnings_date: "
                        f"{raw_date!r}"
                    ) from exc

            raw_time = row.get(
                "er_time"
            )

            earnings_time = (
                None
                if raw_time in (
                    None,
                    "",
                )
                else str(raw_time).strip()
            )

            matches.append(
                EarningsSnapshot(
                    ticker=ticker,
                    next_earnings_date=(
                        next_earnings_date
                    ),
                    earnings_time=(
                        earnings_time
                    ),
                    provider="UNUSUAL_WHALES",
                    fetched_at=datetime.now(
                        UTC
                    ),
                )
            )

        if not matches:
            return None

        if len(matches) != 1:
            raise UnusualWhalesError(
                "UW stock-screener returned "
                "multiple rows for ticker."
            )

        return matches[0]
