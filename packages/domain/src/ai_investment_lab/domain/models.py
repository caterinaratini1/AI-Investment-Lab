"""Value objects used by the portfolio aggregate."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from ai_investment_lab.domain.decimal_utils import (
    MONEY_QUANTUM,
    ONE,
    PRICE_QUANTUM,
    QUANTITY_QUANTUM,
    RATE_QUANTUM,
    ZERO,
    require_decimal,
    require_signed_decimal,
)
from ai_investment_lab.domain.errors import InvalidTradeError


class AssetType(StrEnum):
    PUBLIC_EQUITY = "PUBLIC_EQUITY"
    UCITS_ETF = "UCITS_ETF"


class TradeSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class CostModel:
    commission_rate: Decimal = Decimal("0.0010")
    minimum_commission: Decimal = Decimal("1.00")
    slippage_rate: Decimal = Decimal("0.0005")
    fx_fee_rate: Decimal = Decimal("0.0020")

    def __post_init__(self) -> None:
        commission_rate = require_decimal(
            self.commission_rate,
            name="commission_rate",
            quantum=RATE_QUANTUM,
            positive=False,
        )
        slippage_rate = require_decimal(
            self.slippage_rate,
            name="slippage_rate",
            quantum=RATE_QUANTUM,
            positive=False,
        )
        fx_fee_rate = require_decimal(
            self.fx_fee_rate,
            name="fx_fee_rate",
            quantum=RATE_QUANTUM,
            positive=False,
        )
        minimum = require_decimal(
            self.minimum_commission,
            name="minimum_commission",
            quantum=MONEY_QUANTUM,
            positive=False,
        )
        if any(value > ONE for value in (commission_rate, slippage_rate, fx_fee_rate)):
            raise InvalidTradeError("cost rates cannot exceed 1")
        if slippage_rate == ONE:
            raise InvalidTradeError("slippage_rate must be less than 1")
        object.__setattr__(self, "commission_rate", commission_rate)
        object.__setattr__(self, "slippage_rate", slippage_rate)
        object.__setattr__(self, "fx_fee_rate", fx_fee_rate)
        object.__setattr__(self, "minimum_commission", minimum)


@dataclass(frozen=True, slots=True)
class TradeRequest:
    portfolio_id: UUID
    asset_id: UUID
    asset_currency: str
    side: TradeSide
    quantity: Decimal
    reference_price: Decimal
    fx_rate_to_base: Decimal
    executed_at: datetime
    decision_id: UUID | None = None

    def __post_init__(self) -> None:
        currency = self.asset_currency.upper()
        if len(currency) != 3 or not currency.isalpha():
            raise InvalidTradeError("asset_currency must be a three-letter code")
        if self.executed_at.tzinfo is None or self.executed_at.utcoffset() is None:
            raise InvalidTradeError("executed_at must include a timezone")
        object.__setattr__(self, "asset_currency", currency)
        object.__setattr__(
            self,
            "quantity",
            require_decimal(
                self.quantity,
                name="quantity",
                quantum=QUANTITY_QUANTUM,
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "reference_price",
            require_decimal(
                self.reference_price,
                name="reference_price",
                quantum=PRICE_QUANTUM,
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "fx_rate_to_base",
            require_decimal(
                self.fx_rate_to_base,
                name="fx_rate_to_base",
                quantum=RATE_QUANTUM,
                positive=True,
            ),
        )


@dataclass(slots=True)
class Position:
    asset_id: UUID
    quantity: Decimal
    cost_basis: Decimal
    realized_pnl: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        self.quantity = require_decimal(
            self.quantity,
            name="position quantity",
            quantum=QUANTITY_QUANTUM,
            positive=True,
        )
        self.cost_basis = require_decimal(
            self.cost_basis,
            name="position cost_basis",
            quantum=MONEY_QUANTUM,
            positive=False,
        )
        self.realized_pnl = require_signed_decimal(
            self.realized_pnl,
            name="position realized_pnl",
            quantum=MONEY_QUANTUM,
        )

    @property
    def average_cost(self) -> Decimal:
        if self.quantity == ZERO:
            return ZERO
        return self.cost_basis / self.quantity


@dataclass(frozen=True, slots=True)
class TradeExecution:
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

    @property
    def total_explicit_costs(self) -> Decimal:
        return self.commission + self.slippage_cost + self.fx_fee


@dataclass(frozen=True, slots=True)
class MarketQuote:
    asset_id: UUID
    price: Decimal
    fx_rate_to_base: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidTradeError("quote observed_at must include a timezone")
        object.__setattr__(
            self,
            "price",
            require_decimal(self.price, name="price", quantum=PRICE_QUANTUM, positive=True),
        )
        object.__setattr__(
            self,
            "fx_rate_to_base",
            require_decimal(
                self.fx_rate_to_base,
                name="fx_rate_to_base",
                quantum=RATE_QUANTUM,
                positive=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class PositionValuation:
    asset_id: UUID
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    return_fraction: Decimal
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    portfolio_id: UUID
    cash_balance: Decimal
    market_value: Decimal
    total_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_return_fraction: Decimal
    positions: tuple[PositionValuation, ...]
