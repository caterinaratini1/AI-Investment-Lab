"""Market-data provider dependency composition."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status

from ai_investment_lab.api.settings import Settings, get_settings
from ai_investment_lab.data_providers import EodhdClient, MarketDataProvider


@lru_cache
def _eodhd_provider(api_token: str, base_url: str) -> EodhdClient:
    return EodhdClient(api_token, base_url=base_url)


def get_market_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketDataProvider:
    if not settings.eodhd_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="market-data provider credentials are not configured",
        )
    return _eodhd_provider(settings.eodhd_api_token, settings.eodhd_base_url)
