"""EODHD HTTP adapter normalized to exact-decimal provider contracts."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import quote

import httpx

from ai_investment_lab.data_providers.models import (
    ExchangeCalendar,
    ExchangeHoliday,
    InstrumentMatch,
    PriceBar,
    ProviderAuthenticationError,
    ProviderPayloadError,
    ProviderRequestError,
)

_WEEKDAYS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _canonical_record(record: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    encoded = json.dumps(record, default=str, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest(), cast(
        dict[str, object], json.loads(encoded)
    )


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ProviderPayloadError(f"EODHD field {field} is not numeric") from error
    if not result.is_finite():
        raise ProviderPayloadError(f"EODHD field {field} is not finite")
    return result


def _clock(value: object, field: str) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError as error:
        raise ProviderPayloadError(f"EODHD field {field} is not a valid time") from error


class EodhdClient:
    """Small synchronous adapter used by the API lookup and scheduled worker."""

    name = "EODHD"

    def __init__(
        self,
        api_token: str,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://eodhd.com/api",
    ) -> None:
        if not api_token.strip():
            raise ProviderAuthenticationError("AIL_EODHD_API_TOKEN is required")
        self._api_token = api_token
        self._client = client or httpx.Client(timeout=30.0)
        self._base_url = base_url.rstrip("/")

    def _get(
        self,
        path: str,
        params: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> Any:
        safe_params = dict(params or {})
        safe_params.update({"api_token": self._api_token, "fmt": "json"})
        try:
            response = self._client.get(f"{self._base_url}/{path.lstrip('/')}", params=safe_params)
        except httpx.HTTPError as error:
            raise ProviderRequestError("EODHD request failed") from error
        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError("EODHD rejected the configured API token")
        if response.status_code >= 400:
            raise ProviderRequestError(f"EODHD request failed with HTTP {response.status_code}")
        try:
            return json.loads(response.text, parse_float=Decimal, parse_int=Decimal)
        except json.JSONDecodeError as error:
            raise ProviderPayloadError("EODHD returned invalid JSON") from error

    def search(
        self,
        query: str,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[InstrumentMatch]:
        if not query.strip():
            raise ValueError("search query cannot be empty")
        if not 1 <= limit <= 500:
            raise ValueError("search limit must be between 1 and 500")
        params: dict[str, str | int | float | bool | None] = {"limit": limit}
        if exchange:
            params["exchange"] = exchange
        if instrument_type:
            params["type"] = instrument_type
        payload = self._get(f"search/{quote(query.strip(), safe='')}", params)
        if not isinstance(payload, list):
            raise ProviderPayloadError("EODHD search response must be a list")
        matches: list[InstrumentMatch] = []
        for raw in payload:
            if not isinstance(raw, dict):
                raise ProviderPayloadError("EODHD search item must be an object")
            try:
                matches.append(
                    InstrumentMatch(
                        code=str(raw["Code"]),
                        exchange_code=str(raw["Exchange"]),
                        name=str(raw["Name"]),
                        instrument_type=str(raw["Type"]),
                        country=str(raw["Country"]) if raw.get("Country") else None,
                        currency=str(raw["Currency"]) if raw.get("Currency") else None,
                        isin=str(raw["ISIN"]) if raw.get("ISIN") else None,
                        is_primary=(
                            bool(raw["isPrimary"]) if raw.get("isPrimary") is not None else None
                        ),
                    )
                )
            except KeyError as error:
                raise ProviderPayloadError(
                    f"EODHD search item is missing {error.args[0]}"
                ) from error
        return matches

    def historical_prices(
        self,
        provider_symbol: str,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[PriceBar]:
        if date_from > date_to:
            raise ValueError("date_from must not be after date_to")
        retrieved_at = datetime.now(UTC)
        payload = self._get(
            f"eod/{provider_symbol}",
            {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "period": "d",
                "order": "a",
            },
        )
        if not isinstance(payload, list):
            raise ProviderPayloadError("EODHD price response must be a list")
        bars: list[PriceBar] = []
        previous_date: date | None = None
        for raw in payload:
            if not isinstance(raw, dict):
                raise ProviderPayloadError("EODHD price item must be an object")
            try:
                observation_date = date.fromisoformat(str(raw["date"]))
                values = {
                    key: _decimal(raw[key], key)
                    for key in ("open", "high", "low", "close", "adjusted_close", "volume")
                }
            except (KeyError, ValueError) as error:
                raise ProviderPayloadError("EODHD price item is incomplete or invalid") from error
            if previous_date is not None and observation_date <= previous_date:
                raise ProviderPayloadError("EODHD price dates must be unique and ascending")
            if not date_from <= observation_date <= date_to:
                raise ProviderPayloadError("EODHD returned a price outside the requested range")
            if any(values[key] <= 0 for key in ("open", "high", "low", "close", "adjusted_close")):
                raise ProviderPayloadError("EODHD price fields must be positive")
            if values["volume"] < 0:
                raise ProviderPayloadError("EODHD volume cannot be negative")
            if values["low"] > values["high"]:
                raise ProviderPayloadError("EODHD low cannot exceed high")
            if any(
                not values["low"] <= values[field] <= values["high"] for field in ("open", "close")
            ):
                raise ProviderPayloadError("EODHD open and close must be within the daily range")
            checksum, raw_payload = _canonical_record(raw)
            bars.append(
                PriceBar(
                    observation_date=observation_date,
                    open=values["open"],
                    high=values["high"],
                    low=values["low"],
                    close=values["close"],
                    adjusted_close=values["adjusted_close"],
                    volume=values["volume"],
                    retrieved_at=retrieved_at,
                    source_checksum=checksum,
                    raw_payload=raw_payload,
                )
            )
            previous_date = observation_date
        return bars

    def exchange_calendar(self, exchange_code: str, *, year: int) -> ExchangeCalendar:
        retrieved_at = datetime.now(UTC)
        if year == retrieved_at.year:
            payload = self._get(f"v2/exchange-details/{exchange_code}")
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                raise ProviderPayloadError("EODHD exchange response is missing data")
            data = cast(dict[str, object], payload["data"])
        else:
            payload = self._get(
                f"exchange-details/{exchange_code}",
                {"from": f"{year}-01-01", "to": f"{year}-12-31"},
            )
            if not isinstance(payload, dict):
                raise ProviderPayloadError("EODHD historical exchange response must be an object")
            data = cast(dict[str, object], payload)
        trading = data.get("TradingHours")
        raw_holidays = data.get("ExchangeHolidays", {})
        if not isinstance(trading, dict) or not isinstance(raw_holidays, dict):
            raise ProviderPayloadError("EODHD exchange schedule is invalid")
        timezone = str(data.get("Timezone", ""))
        if not timezone:
            raise ProviderPayloadError("EODHD exchange timezone is missing")
        working = str(trading.get("WorkingDays", "")).replace(" ", "").split(",")
        try:
            weekdays = frozenset(_WEEKDAYS[item.lower()] for item in working if item)
        except KeyError as error:
            raise ProviderPayloadError("EODHD working days are invalid") from error
        if not weekdays:
            raise ProviderPayloadError("EODHD working days are missing")
        regular_close = _clock(trading.get("Close"), "TradingHours.Close")
        holidays: list[ExchangeHoliday] = []
        for raw_key, raw in raw_holidays.items():
            if not isinstance(raw, dict):
                raise ProviderPayloadError("EODHD holiday item must be an object")
            raw_date = raw.get("Date", raw_key)
            kind = str(raw.get("Type", "Official")).replace("-", "_").replace(" ", "_").upper()
            if kind == "EARLYCLOSE":
                kind = "EARLY_CLOSE"
            if kind not in {"OFFICIAL", "BANK", "EARLY_CLOSE"}:
                raise ProviderPayloadError(f"unsupported EODHD holiday type {kind}")
            holidays.append(
                ExchangeHoliday(
                    holiday_date=date.fromisoformat(str(raw_date)),
                    name=str(raw.get("Holiday", "Exchange holiday")),
                    kind=cast(Any, kind),
                    early_close=(
                        _clock(raw["EarlyClose"], "ExchangeHolidays.EarlyClose")
                        if raw.get("EarlyClose")
                        else None
                    ),
                )
            )
        if any(item.holiday_date.year != year for item in holidays):
            raise ProviderPayloadError(
                f"EODHD exchange calendar does not cover requested year {year}"
            )
        checksum, _ = _canonical_record(
            {
                "Timezone": timezone,
                "TradingHours": trading,
                "ExchangeHolidays": raw_holidays,
            }
        )
        return ExchangeCalendar(
            exchange_code=exchange_code.upper(),
            timezone=timezone,
            working_weekdays=weekdays,
            regular_close=regular_close,
            holidays=tuple(sorted(holidays, key=lambda item: item.holiday_date)),
            retrieved_at=retrieved_at,
            source_checksum=checksum,
        )
