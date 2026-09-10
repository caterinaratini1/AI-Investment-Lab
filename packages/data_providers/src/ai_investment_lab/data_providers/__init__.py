"""Provider-neutral market-data contracts and the EODHD adapter."""

from ai_investment_lab.data_providers.eodhd import EodhdClient
from ai_investment_lab.data_providers.models import (
    ExchangeCalendar,
    ExchangeHoliday,
    InstrumentMatch,
    MarketDataProvider,
    PriceBar,
    ProviderAuthenticationError,
    ProviderError,
    ProviderPayloadError,
    ProviderRequestError,
    SessionDefinition,
)

__all__ = [
    "EodhdClient",
    "ExchangeCalendar",
    "ExchangeHoliday",
    "InstrumentMatch",
    "MarketDataProvider",
    "PriceBar",
    "ProviderAuthenticationError",
    "ProviderError",
    "ProviderPayloadError",
    "ProviderRequestError",
    "SessionDefinition",
]
