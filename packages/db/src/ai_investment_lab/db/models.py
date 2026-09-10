"""SQLAlchemy models for the portfolio ledger and point-in-time market data."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
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
        UniqueConstraint("isin", name="uq_assets_isin"),
        CheckConstraint("asset_type IN ('PUBLIC_EQUITY', 'UCITS_ETF')", name="ck_assets_type"),
        CheckConstraint("length(isin) = 12", name="ck_assets_isin_length"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    isin: Mapped[str] = mapped_column(String(12), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class ListingModel(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("ticker", "exchange_mic", name="uq_listings_ticker_mic"),
        UniqueConstraint("provider", "provider_symbol", name="uq_listings_provider_symbol"),
        CheckConstraint("length(currency) = 3", name="ck_listings_currency_length"),
        CheckConstraint("length(exchange_mic) = 4", name="ck_listings_mic_length"),
        CheckConstraint("provider IN ('EODHD')", name="ck_listings_provider"),
        Index(
            "uq_listings_primary_asset",
            "asset_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange_mic: Mapped[str] = mapped_column(String(4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="EODHD")
    provider_symbol: Mapped[str | None] = mapped_column(String(80))
    provider_exchange_code: Mapped[str | None] = mapped_column(String(16))
    exchange_timezone: Mapped[str | None] = mapped_column(String(64))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class IngestionRunModel(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingestion_runs_idempotency_key"),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_ingestion_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    requested_from: Mapped[date | None] = mapped_column(Date)
    requested_to: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class PriceObservationModel(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "provider",
            "observation_date",
            "revision",
            name="uq_price_observations_revision",
        ),
        UniqueConstraint("supersedes_id", name="uq_price_observations_supersedes"),
        CheckConstraint("open > 0", name="ck_price_observations_open_positive"),
        CheckConstraint("high > 0", name="ck_price_observations_high_positive"),
        CheckConstraint("low > 0", name="ck_price_observations_low_positive"),
        CheckConstraint("close > 0", name="ck_price_observations_close_positive"),
        CheckConstraint("adjusted_close > 0", name="ck_price_observations_adjusted_close_positive"),
        CheckConstraint("volume >= 0", name="ck_price_observations_volume_non_negative"),
        CheckConstraint("revision > 0", name="ck_price_observations_revision_positive"),
        CheckConstraint("length(currency) = 3", name="ck_price_observations_currency_length"),
        Index(
            "ix_price_observations_listing_date",
            "listing_id",
            "observation_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("listings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    adjusted_close: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("price_observations.id", ondelete="RESTRICT"),
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    ingestion_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ExchangeSessionModel(Base):
    __tablename__ = "exchange_sessions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "exchange_code",
            "session_date",
            "revision",
            name="uq_exchange_sessions_revision",
        ),
        UniqueConstraint("supersedes_id", name="uq_exchange_sessions_supersedes"),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'EARLY_CLOSE')",
            name="ck_exchange_sessions_status",
        ),
        Index("ix_exchange_sessions_mic_date", "exchange_mic", "session_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    exchange_code: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange_mic: Mapped[str] = mapped_column(String(4), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    holiday_name: Mapped[str | None] = mapped_column(String(160))
    close_time: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exchange_sessions.id", ondelete="RESTRICT"),
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )


class FxRateObservationModel(Base):
    __tablename__ = "fx_rate_observations"
    __table_args__ = (
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "observation_date",
            "revision",
            name="uq_fx_rate_observations_revision",
        ),
        UniqueConstraint("supersedes_id", name="uq_fx_rate_observations_supersedes"),
        CheckConstraint("rate_to_base > 0", name="ck_fx_rate_observations_rate_positive"),
        CheckConstraint("revision > 0", name="ck_fx_rate_observations_revision_positive"),
        CheckConstraint("length(base_currency) = 3", name="ck_fx_rates_base_currency_length"),
        CheckConstraint("length(quote_currency) = 3", name="ck_fx_rates_quote_currency_length"),
        Index(
            "ix_fx_rate_observations_pair_date",
            "base_currency",
            "quote_currency",
            "observation_date",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_rate: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    rate_to_base: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    inverted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fx_rate_observations.id", ondelete="RESTRICT"),
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    ingestion_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DataQualityIssueModel(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        UniqueConstraint(
            "listing_id",
            "observation_date",
            "issue_type",
            name="uq_data_quality_issues_identity",
        ),
        CheckConstraint("status IN ('OPEN', 'RESOLVED')", name="ck_data_quality_issues_status"),
        Index("ix_data_quality_issues_status", "status", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("listings.id", ondelete="RESTRICT")
    )
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingestion_runs.id", ondelete="RESTRICT")
    )


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id",
            "valuation_date",
            "input_fingerprint",
            name="uq_portfolio_snapshots_inputs",
        ),
        UniqueConstraint("supersedes_id", name="uq_portfolio_snapshots_supersedes"),
        CheckConstraint("cash_balance >= 0", name="ck_snapshots_cash_non_negative"),
        CheckConstraint("positions_value >= 0", name="ck_snapshots_positions_non_negative"),
        CheckConstraint("total_value >= 0", name="ck_snapshots_total_non_negative"),
        CheckConstraint("revision > 0", name="ck_snapshots_revision_positive"),
        Index("ix_portfolio_snapshots_portfolio_date", "portfolio_id", "valuation_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    positions_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_return: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_snapshots.id", ondelete="RESTRICT"),
    )
    ingestion_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SnapshotPositionModel(Base):
    __tablename__ = "snapshot_positions"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "asset_id", name="uq_snapshot_positions_asset"),
        CheckConstraint("quantity > 0", name="ck_snapshot_positions_quantity_positive"),
        CheckConstraint("price > 0", name="ck_snapshot_positions_price_positive"),
        CheckConstraint("fx_rate_to_base > 0", name="ck_snapshot_positions_fx_positive"),
        CheckConstraint("market_value >= 0", name="ck_snapshot_positions_value_non_negative"),
        CheckConstraint("stale_days >= 0", name="ck_snapshot_positions_stale_non_negative"),
        CheckConstraint(
            "valuation_status IN ('FRESH', 'STALE_CLOSED_SESSION')",
            name="ck_snapshot_positions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("portfolio_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    )
    listing_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("listings.id", ondelete="RESTRICT"), nullable=False
    )
    price_observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("price_observations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    exchange_session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exchange_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fx_rate_observation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fx_rate_observations.id", ondelete="RESTRICT")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    fx_rate_to_base: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    stale_days: Mapped[int] = mapped_column(Integer, nullable=False)
    valuation_status: Mapped[str] = mapped_column(String(32), nullable=False)


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
