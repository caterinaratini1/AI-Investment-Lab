"""Normalized market-data values exposed by every provider adapter."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Protocol


class ProviderError(RuntimeError):
    """Base class for safe provider failures that never expose credentials."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected or was not given credentials."""


class ProviderRequestError(ProviderError):
    """The provider request failed before a valid payload was returned."""


class ProviderPayloadError(ProviderError):
    """The provider returned data that violates the normalized contract."""


@dataclass(frozen=True)
class PriceBar:
    observation_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: Decimal
    retrieved_at: datetime
    source_checksum: str
    raw_payload: dict[str, object]


@dataclass(frozen=True)
class InstrumentMatch:
    code: str
    exchange_code: str
    name: str
    instrument_type: str
    country: str | None
    currency: str | None
    isin: str | None
    is_primary: bool | None

    @property
    def provider_symbol(self) -> str:
        return f"{self.code}.{self.exchange_code}"


@dataclass(frozen=True)
class ExchangeHoliday:
    holiday_date: date
    name: str
    kind: Literal["OFFICIAL", "BANK", "EARLY_CLOSE"]
    early_close: time | None


@dataclass(frozen=True)
class SessionDefinition:
    session_date: date
    status: Literal["OPEN", "CLOSED", "EARLY_CLOSE"]
    holiday_name: str | None
    close_time: time | None


@dataclass(frozen=True)
class ExchangeCalendar:
    exchange_code: str
    timezone: str
    working_weekdays: frozenset[int]
    regular_close: time
    holidays: tuple[ExchangeHoliday, ...]
    retrieved_at: datetime
    source_checksum: str

    def session(self, session_date: date) -> SessionDefinition:
        holiday = next(
            (item for item in self.holidays if item.holiday_date == session_date),
            None,
        )
        if holiday is not None and holiday.kind == "EARLY_CLOSE":
            return SessionDefinition(
                session_date=session_date,
                status="EARLY_CLOSE",
                holiday_name=holiday.name,
                close_time=holiday.early_close or self.regular_close,
            )
        if holiday is not None or session_date.weekday() not in self.working_weekdays:
            return SessionDefinition(
                session_date=session_date,
                status="CLOSED",
                holiday_name=holiday.name if holiday else "Weekend",
                close_time=None,
            )
        return SessionDefinition(
            session_date=session_date,
            status="OPEN",
            holiday_name=None,
            close_time=self.regular_close,
        )


class MarketDataProvider(Protocol):
    name: str

    def search(
        self,
        query: str,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[InstrumentMatch]: ...

    def historical_prices(
        self,
        provider_symbol: str,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[PriceBar]: ...

    def exchange_calendar(self, exchange_code: str, *, year: int) -> ExchangeCalendar: ...
