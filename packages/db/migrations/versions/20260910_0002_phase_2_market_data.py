"""Create the Phase 2 market-data and snapshot ledger.

Revision ID: 20260910_0002
Revises: 20260910_0001
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0002"
down_revision: str | None = "20260910_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("exchange_mic", sa.String(length=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_symbol", sa.String(length=80), nullable=True),
        sa.Column("provider_exchange_code", sa.String(length=16), nullable=True),
        sa.Column("exchange_timezone", sa.String(length=64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(currency) = 3", name="ck_listings_currency_length"),
        sa.CheckConstraint("length(exchange_mic) = 4", name="ck_listings_mic_length"),
        sa.CheckConstraint("provider IN ('EODHD')", name="ck_listings_provider"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_symbol", name="uq_listings_provider_symbol"),
        sa.UniqueConstraint("ticker", "exchange_mic", name="uq_listings_ticker_mic"),
    )
    op.create_index(
        "uq_listings_primary_asset",
        "listings",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.execute(
        """
        INSERT INTO listings (
            id, asset_id, ticker, exchange_mic, currency, provider,
            provider_symbol, provider_exchange_code, exchange_timezone,
            is_primary, active, created_at
        )
        SELECT
            id, id, ticker, exchange_mic, currency, 'EODHD',
            CASE WHEN exchange_mic = 'XAMS' THEN ticker || '.AS' ELSE NULL END,
            CASE WHEN exchange_mic = 'XAMS' THEN 'AS' ELSE NULL END,
            CASE WHEN exchange_mic = 'XAMS' THEN 'Europe/Amsterdam' ELSE NULL END,
            true, true, created_at
        FROM assets
        """
    )
    op.drop_constraint("uq_assets_listing", "assets", type_="unique")
    op.drop_constraint("uq_assets_isin_listing", "assets", type_="unique")
    op.drop_constraint("ck_assets_currency_length", "assets", type_="check")
    op.drop_constraint("ck_assets_mic_length", "assets", type_="check")
    op.drop_column("assets", "ticker")
    op.drop_column("assets", "exchange_mic")
    op.drop_column("assets", "currency")
    op.create_unique_constraint("uq_assets_isin", "assets", ["isin"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_from", sa.Date(), nullable=True),
        sa.Column("requested_to", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_ingestion_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ingestion_runs_idempotency_key"),
    )
    op.create_table(
        "price_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_symbol", sa.String(length=80), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(28, 8), nullable=False),
        sa.Column("high", sa.Numeric(28, 8), nullable=False),
        sa.Column("low", sa.Numeric(28, 8), nullable=False),
        sa.Column("close", sa.Numeric(28, 8), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(28, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "adjusted_close > 0", name="ck_price_observations_adjusted_close_positive"
        ),
        sa.CheckConstraint("close > 0", name="ck_price_observations_close_positive"),
        sa.CheckConstraint("high > 0", name="ck_price_observations_high_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_price_observations_currency_length"),
        sa.CheckConstraint("low > 0", name="ck_price_observations_low_positive"),
        sa.CheckConstraint("open > 0", name="ck_price_observations_open_positive"),
        sa.CheckConstraint("revision > 0", name="ck_price_observations_revision_positive"),
        sa.CheckConstraint("volume >= 0", name="ck_price_observations_volume_non_negative"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["price_observations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "listing_id",
            "provider",
            "observation_date",
            "revision",
            name="uq_price_observations_revision",
        ),
        sa.UniqueConstraint("supersedes_id", name="uq_price_observations_supersedes"),
    )
    op.create_index(
        "ix_price_observations_listing_date",
        "price_observations",
        ["listing_id", "observation_date"],
    )
    op.create_table(
        "exchange_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("exchange_mic", sa.String(length=4), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("holiday_name", sa.String(length=160), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED', 'EARLY_CLOSE')",
            name="ck_exchange_sessions_status",
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["exchange_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "exchange_code",
            "session_date",
            "revision",
            name="uq_exchange_sessions_revision",
        ),
        sa.UniqueConstraint("supersedes_id", name="uq_exchange_sessions_supersedes"),
    )
    op.create_index(
        "ix_exchange_sessions_mic_date",
        "exchange_sessions",
        ["exchange_mic", "session_date"],
    )
    op.create_table(
        "fx_rate_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("provider_symbol", sa.String(length=80), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("raw_rate", sa.Numeric(24, 12), nullable=False),
        sa.Column("rate_to_base", sa.Numeric(24, 12), nullable=False),
        sa.Column("inverted", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(base_currency) = 3", name="ck_fx_rates_base_currency_length"),
        sa.CheckConstraint("length(quote_currency) = 3", name="ck_fx_rates_quote_currency_length"),
        sa.CheckConstraint("rate_to_base > 0", name="ck_fx_rate_observations_rate_positive"),
        sa.CheckConstraint("revision > 0", name="ck_fx_rate_observations_revision_positive"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["fx_rate_observations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "base_currency",
            "quote_currency",
            "observation_date",
            "revision",
            name="uq_fx_rate_observations_revision",
        ),
        sa.UniqueConstraint("supersedes_id", name="uq_fx_rate_observations_supersedes"),
    )
    op.create_index(
        "ix_fx_rate_observations_pair_date",
        "fx_rate_observations",
        ["base_currency", "quote_currency", "observation_date"],
    )
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("issue_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED')", name="ck_data_quality_issues_status"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "listing_id",
            "observation_date",
            "issue_type",
            name="uq_data_quality_issues_identity",
        ),
    )
    op.create_index(
        "ix_data_quality_issues_status",
        "data_quality_issues",
        ["status", "detected_at"],
    )
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 2), nullable=False),
        sa.Column("positions_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_return", sa.Numeric(24, 12), nullable=False),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cash_balance >= 0", name="ck_snapshots_cash_non_negative"),
        sa.CheckConstraint("positions_value >= 0", name="ck_snapshots_positions_non_negative"),
        sa.CheckConstraint("revision > 0", name="ck_snapshots_revision_positive"),
        sa.CheckConstraint("total_value >= 0", name="ck_snapshots_total_non_negative"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["portfolio_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "valuation_date",
            "input_fingerprint",
            name="uq_portfolio_snapshots_inputs",
        ),
        sa.UniqueConstraint("supersedes_id", name="uq_portfolio_snapshots_supersedes"),
    )
    op.create_index(
        "ix_portfolio_snapshots_portfolio_date",
        "portfolio_snapshots",
        ["portfolio_id", "valuation_date"],
    )
    op.create_table(
        "snapshot_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("price_observation_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_session_id", sa.Uuid(), nullable=False),
        sa.Column("fx_rate_observation_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 2), nullable=False),
        sa.Column("price", sa.Numeric(28, 8), nullable=False),
        sa.Column("fx_rate_to_base", sa.Numeric(24, 12), nullable=False),
        sa.Column("market_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("stale_days", sa.Integer(), nullable=False),
        sa.Column("valuation_status", sa.String(length=32), nullable=False),
        sa.CheckConstraint("fx_rate_to_base > 0", name="ck_snapshot_positions_fx_positive"),
        sa.CheckConstraint("market_value >= 0", name="ck_snapshot_positions_value_non_negative"),
        sa.CheckConstraint("price > 0", name="ck_snapshot_positions_price_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_snapshot_positions_quantity_positive"),
        sa.CheckConstraint("stale_days >= 0", name="ck_snapshot_positions_stale_non_negative"),
        sa.CheckConstraint(
            "valuation_status IN ('FRESH', 'STALE_CLOSED_SESSION')",
            name="ck_snapshot_positions_status",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exchange_session_id"], ["exchange_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fx_rate_observation_id"], ["fx_rate_observations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["price_observation_id"], ["price_observations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "asset_id", name="uq_snapshot_positions_asset"),
    )

    for table in (
        "price_observations",
        "exchange_sessions",
        "fx_rate_observations",
        "portfolio_snapshots",
        "snapshot_positions",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation()
            """
        )


def downgrade() -> None:
    for table in (
        "snapshot_positions",
        "portfolio_snapshots",
        "fx_rate_observations",
        "exchange_sessions",
        "price_observations",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.drop_table("snapshot_positions")
    op.drop_index("ix_portfolio_snapshots_portfolio_date", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_index("ix_data_quality_issues_status", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
    op.drop_index("ix_fx_rate_observations_pair_date", table_name="fx_rate_observations")
    op.drop_table("fx_rate_observations")
    op.drop_index("ix_exchange_sessions_mic_date", table_name="exchange_sessions")
    op.drop_table("exchange_sessions")
    op.drop_index("ix_price_observations_listing_date", table_name="price_observations")
    op.drop_table("price_observations")
    op.drop_table("ingestion_runs")

    op.drop_constraint("uq_assets_isin", "assets", type_="unique")
    op.add_column("assets", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("assets", sa.Column("exchange_mic", sa.String(length=4), nullable=True))
    op.add_column("assets", sa.Column("ticker", sa.String(length=32), nullable=True))
    op.execute(
        """
        UPDATE assets
        SET ticker = listings.ticker,
            exchange_mic = listings.exchange_mic,
            currency = listings.currency
        FROM listings
        WHERE listings.asset_id = assets.id AND listings.is_primary = true
        """
    )
    op.alter_column("assets", "ticker", nullable=False)
    op.alter_column("assets", "exchange_mic", nullable=False)
    op.alter_column("assets", "currency", nullable=False)
    op.create_check_constraint("ck_assets_currency_length", "assets", "length(currency) = 3")
    op.create_check_constraint("ck_assets_mic_length", "assets", "length(exchange_mic) = 4")
    op.create_unique_constraint("uq_assets_isin_listing", "assets", ["isin", "exchange_mic"])
    op.create_unique_constraint("uq_assets_listing", "assets", ["ticker", "exchange_mic"])
    op.drop_index("uq_listings_primary_asset", table_name="listings")
    op.drop_table("listings")
