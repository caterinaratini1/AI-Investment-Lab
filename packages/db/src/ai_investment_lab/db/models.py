"""SQLAlchemy models for the Phase 1 portfolio ledger."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class PortfolioModel(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint("starting_capital > 0", name="ck_portfolios_starting_capital_positive"),
        CheckConstraint("cash_balance >= 0", name="ck_portfolios_cash_non_negative"),
        CheckConstraint("length(base_currency) = 3", name="ck_portfolios_currency_length"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    starting_capital: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0.1.0")
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class AssetModel(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange_mic", name="uq_assets_listing"),
        UniqueConstraint("isin", "exchange_mic", name="uq_assets_isin_listing"),
        CheckConstraint("asset_type IN ('PUBLIC_EQUITY', 'UCITS_ETF')", name="ck_assets_type"),
        CheckConstraint("length(currency) = 3", name="ck_assets_currency_length"),
        CheckConstraint("length(exchange_mic) = 4", name="ck_assets_mic_length"),
        CheckConstraint("length(isin) = 12", name="ck_assets_isin_length"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    isin: Mapped[str] = mapped_column(String(12), nullable=False)
    exchange_mic: Mapped[str] = mapped_column(String(4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class PositionModel(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_positions_quantity_positive"),
        CheckConstraint("cost_basis >= 0", name="ck_positions_cost_basis_non_negative"),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_transactions_side"),
        CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
        CheckConstraint("reference_price > 0", name="ck_transactions_reference_price_positive"),
        CheckConstraint("execution_price > 0", name="ck_transactions_execution_price_positive"),
        CheckConstraint("fx_rate_to_base > 0", name="ck_transactions_fx_positive"),
        CheckConstraint("gross_notional > 0", name="ck_transactions_notional_positive"),
        CheckConstraint("commission >= 0", name="ck_transactions_commission_non_negative"),
        CheckConstraint("slippage_cost >= 0", name="ck_transactions_slippage_non_negative"),
        CheckConstraint("fx_fee >= 0", name="ck_transactions_fx_fee_non_negative"),
        Index("ix_transactions_portfolio_executed", "portfolio_id", "executed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    asset_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    execution_price: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    gross_notional: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    slippage_cost: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fx_fee: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class CashLedgerEntryModel(Base):
    __tablename__ = "cash_ledger_entries"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_cash_ledger_transaction"),
        CheckConstraint(
            "entry_type IN ('INITIAL_CAPITAL', 'TRADE')",
            name="ck_cash_ledger_entry_type",
        ),
        CheckConstraint("balance_after >= 0", name="ck_cash_ledger_balance_non_negative"),
        Index("ix_cash_ledger_portfolio_effective", "portfolio_id", "effective_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    transaction_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
