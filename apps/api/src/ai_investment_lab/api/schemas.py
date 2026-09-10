"""Validated public API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from ai_investment_lab.domain import AssetType, TradeSide

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Mic = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{4}$")]
Isin = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")]
PositiveMoney = Annotated[Decimal, Field(gt=0, decimal_places=2, max_digits=20)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, decimal_places=8, max_digits=28)]
PositivePrice = Annotated[Decimal, Field(gt=0, decimal_places=8, max_digits=28)]
PositiveFxRate = Annotated[Decimal, Field(gt=0, decimal_places=12, max_digits=24)]


class PortfolioCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    starting_capital: PositiveMoney = Decimal("10000.00")
    base_currency: Literal["EUR"] = "EUR"


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    base_currency: str
    starting_capital: Decimal
    cash_balance: Decimal
    realized_pnl: Decimal
    policy_version: str
    version: int
    created_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    ticker: Annotated[
        str,
        StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32),
    ]
    isin: Isin
    exchange_mic: Mic
    currency: Currency
    asset_type: AssetType
    sector: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=80)] = None


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    ticker: str
    isin: str
    exchange_mic: str
    currency: str
    asset_type: AssetType
    sector: str | None
    created_at: datetime


class TradeCreate(BaseModel):
    asset_id: UUID
    side: TradeSide
    quantity: PositiveQuantity
    reference_price: PositivePrice
    fx_rate_to_base: PositiveFxRate = Decimal("1.000000000000")
    executed_at: AwareDatetime
    decision_id: UUID | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    asset_id: UUID
    decision_id: UUID | None
    side: TradeSide
    asset_currency: str
    quantity: Decimal
    reference_price: Decimal
    execution_price: Decimal
    fx_rate_to_base: Decimal
    gross_notional: Decimal
    commission: Decimal
    slippage_cost: Decimal
    fx_fee: Decimal
    cash_delta: Decimal
    realized_pnl: Decimal
    executed_at: datetime
    created_at: datetime


class PositionResponse(BaseModel):
    portfolio_id: UUID
    asset_id: UUID
    quantity: Decimal
    cost_basis: Decimal
    average_cost: Decimal
    realized_pnl: Decimal
    opened_at: datetime
    updated_at: datetime


class TradeResultResponse(BaseModel):
    transaction: TransactionResponse
    position: PositionResponse | None
    cash_balance: Decimal
    portfolio_realized_pnl: Decimal


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
