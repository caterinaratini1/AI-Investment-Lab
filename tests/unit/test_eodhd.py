import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from ai_investment_lab.data_providers import (
    EodhdClient,
    ProviderAuthenticationError,
    ProviderPayloadError,
    ProviderRequestError,
)


def client_for(payload: object, *, status_code: int = 200) -> EodhdClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_token"] == "secret"
        assert request.url.params["fmt"] == "json"
        return httpx.Response(status_code, json=payload, request=request)

    return EodhdClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://provider.test/api",
    )


def test_search_normalizes_provider_symbols_and_optional_fields() -> None:
    provider = client_for(
        [
            {
                "Code": "IWDA",
                "Exchange": "AS",
                "Name": "iShares Core MSCI World",
                "Type": "ETF",
                "Country": "Netherlands",
                "Currency": "EUR",
                "ISIN": "IE00B4L5Y983",
                "isPrimary": True,
            },
            {
                "Code": "TEST",
                "Exchange": "US",
                "Name": "Test",
                "Type": "Common Stock",
            },
        ]
    )

    matches = provider.search("IWDA", exchange="AS", instrument_type="etf", limit=2)

    assert matches[0].provider_symbol == "IWDA.AS"
    assert matches[0].isin == "IE00B4L5Y983"
    assert matches[1].currency is None
    assert matches[1].is_primary is None


@pytest.mark.parametrize(
    ("query", "limit", "message"),
    [(" ", 20, "cannot be empty"), ("IWDA", 0, "between 1 and 500")],
)
def test_search_rejects_invalid_input(query: str, limit: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        client_for([]).search(query, limit=limit)


def test_historical_prices_preserve_exact_values_and_checksum() -> None:
    provider = client_for(
        [
            {
                "date": "2026-09-09",
                "open": 100.125,
                "high": 103.5,
                "low": 99.75,
                "close": 102.25,
                "adjusted_close": 101.875,
                "volume": 12345,
            },
            {
                "date": "2026-09-10",
                "open": 102.25,
                "high": 104,
                "low": 101,
                "close": 103,
                "adjusted_close": 102.5,
                "volume": 23456,
            },
        ]
    )

    bars = provider.historical_prices(
        "IWDA.AS",
        date_from=date(2026, 9, 9),
        date_to=date(2026, 9, 10),
    )

    assert bars[0].open == Decimal("100.125")
    assert bars[0].raw_payload["close"] == "102.25"
    assert len(bars[0].source_checksum) == 64
    assert bars[1].observation_date == date(2026, 9, 10)


def test_exchange_calendar_distinguishes_open_closed_and_early_close() -> None:
    calendar_year = datetime.now(UTC).year
    provider = client_for(
        {
            "data": {
                "Timezone": "Europe/Amsterdam",
                "TradingHours": {
                    "Open": "09:00:00",
                    "Close": "17:40:00",
                    "WorkingDays": "Mon, Tue, Wed, Thu, Fri",
                },
                "ExchangeHolidays": {
                    f"{calendar_year}-01-01": {"Holiday": "New Year", "Type": "Official"},
                    f"{calendar_year}-12-24": {
                        "Holiday": "Christmas Eve",
                        "Type": "EarlyClose",
                        "EarlyClose": "14:00:00",
                    },
                },
            }
        }
    )

    calendar = provider.exchange_calendar("AS", year=calendar_year)

    first_day = date(calendar_year, 1, 1)
    monday = first_day + timedelta(days=(-first_day.weekday()) % 7)
    assert calendar.session(monday).status == "OPEN"
    assert calendar.session(monday + timedelta(days=5)).holiday_name == "Weekend"
    assert calendar.session(date(calendar_year, 1, 1)).status == "CLOSED"
    early = calendar.session(date(calendar_year, 12, 24))
    assert early.status == "EARLY_CLOSE"
    assert early.close_time is not None and early.close_time.hour == 14


def test_exchange_calendar_uses_bounded_v1_payload_for_historical_year() -> None:
    historical_year = datetime.now(UTC).year - 1

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/exchange-details/AS"
        assert request.url.params["from"] == f"{historical_year}-01-01"
        assert request.url.params["to"] == f"{historical_year}-12-31"
        return httpx.Response(
            200,
            json={
                "Timezone": "Europe/Amsterdam",
                "TradingHours": {
                    "Close": "17:40:00",
                    "WorkingDays": "Mon,Tue,Wed,Thu,Fri",
                },
                "ExchangeHolidays": {
                    "0": {
                        "Date": f"{historical_year}-01-01",
                        "Holiday": "New Year",
                        "Type": "official",
                    }
                },
            },
            request=request,
        )

    provider = EodhdClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://provider.test/api",
    )

    calendar = provider.exchange_calendar("AS", year=historical_year)

    assert calendar.session(date(historical_year, 1, 1)).status == "CLOSED"


@pytest.mark.parametrize("status_code", [401, 403])
def test_authentication_failures_are_safe(status_code: int) -> None:
    with pytest.raises(ProviderAuthenticationError, match="rejected"):
        client_for({}, status_code=status_code).search("IWDA")


def test_provider_http_network_and_json_failures_are_normalized() -> None:
    with pytest.raises(ProviderRequestError, match="HTTP 429"):
        client_for({}, status_code=429).search("IWDA")

    def disconnect(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-bearing transport text", request=request)

    provider = EodhdClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(disconnect)),
    )
    with pytest.raises(ProviderRequestError, match="EODHD request failed") as caught:
        provider.search("IWDA")
    assert "secret-bearing" not in str(caught.value)

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json", request=request)

    provider = EodhdClient(
        "secret",
        client=httpx.Client(transport=httpx.MockTransport(malformed)),
    )
    with pytest.raises(ProviderPayloadError, match="invalid JSON"):
        provider.search("IWDA")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "must be a list"),
        ([{"date": "2026-09-10"}], "incomplete or invalid"),
        (
            [
                {
                    "date": "2026-09-10",
                    "open": 1,
                    "high": 1,
                    "low": 2,
                    "close": 1,
                    "adjusted_close": 1,
                    "volume": 1,
                }
            ],
            "low cannot exceed high",
        ),
    ],
)
def test_invalid_price_payloads_are_rejected(payload: object, message: str) -> None:
    with pytest.raises(ProviderPayloadError, match=message):
        client_for(payload).historical_prices(
            "IWDA.AS",
            date_from=date(2026, 9, 10),
            date_to=date(2026, 9, 10),
        )


def test_client_and_range_require_valid_configuration() -> None:
    with pytest.raises(ProviderAuthenticationError, match="required"):
        EodhdClient(" ")
    with pytest.raises(ValueError, match="must not be after"):
        client_for([]).historical_prices(
            "IWDA.AS",
            date_from=date(2026, 9, 11),
            date_to=date(2026, 9, 10),
        )


def test_search_and_calendar_require_expected_shapes() -> None:
    calendar_year = datetime.now(UTC).year
    with pytest.raises(ProviderPayloadError, match="search item"):
        client_for(["bad"]).search("IWDA")
    with pytest.raises(ProviderPayloadError, match="missing Code"):
        client_for([{"Exchange": "AS", "Name": "x", "Type": "ETF"}]).search("IWDA")
    with pytest.raises(ProviderPayloadError, match="missing data"):
        client_for({}).exchange_calendar("AS", year=calendar_year)
    with pytest.raises(ProviderPayloadError, match="working days are invalid"):
        client_for(
            {
                "data": {
                    "Timezone": "UTC",
                    "TradingHours": {"WorkingDays": "Noday", "Close": "17:00"},
                    "ExchangeHolidays": {},
                }
            }
        ).exchange_calendar("AS", year=calendar_year)

    with pytest.raises(ProviderPayloadError, match="does not cover requested year"):
        client_for(
            {
                "data": {
                    "Timezone": "UTC",
                    "TradingHours": {"WorkingDays": "Mon,Fri", "Close": "17:00"},
                    "ExchangeHolidays": {
                        f"{calendar_year - 1}-01-01": {
                            "Holiday": "Wrong year",
                            "Type": "Official",
                        }
                    },
                }
            }
        ).exchange_calendar("AS", year=calendar_year)


def test_fixture_is_json_serializable() -> None:
    assert json.loads(json.dumps({"date": "2026-09-10"}))["date"] == "2026-09-10"
