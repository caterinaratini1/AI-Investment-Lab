"""Create the Phase 1 portfolio accounting ledger.

Revision ID: 20260910_0001
Revises:
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("starting_capital", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(base_currency) = 3",
            name="ck_portfolios_currency_length",
        ),
        sa.CheckConstraint(
            "starting_capital > 0",
            name="ck_portfolios_starting_capital_positive",
        ),
        sa.CheckConstraint("cash_balance >= 0", name="ck_portfolios_cash_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=False),
        sa.Column("exchange_mic", sa.String(length=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("sector", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "asset_type IN ('PUBLIC_EQUITY', 'UCITS_ETF')",
            name="ck_assets_type",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_assets_currency_length"),
        sa.CheckConstraint("length(exchange_mic) = 4", name="ck_assets_mic_length"),
        sa.CheckConstraint("length(isin) = 12", name="ck_assets_isin_length"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("isin", "exchange_mic", name="uq_assets_isin_listing"),
        sa.UniqueConstraint("ticker", "exchange_mic", name="uq_assets_listing"),
    )
    op.create_table(
        "positions",
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("cost_basis", sa.Numeric(20, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost_basis >= 0", name="ck_positions_cost_basis_non_negative"),
        sa.CheckConstraint("quantity > 0", name="ck_positions_quantity_positive"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portfolio_id", "asset_id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=True),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("asset_currency", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("reference_price", sa.Numeric(28, 8), nullable=False),
        sa.Column("execution_price", sa.Numeric(28, 8), nullable=False),
        sa.Column("fx_rate_to_base", sa.Numeric(24, 12), nullable=False),
        sa.Column("gross_notional", sa.Numeric(20, 2), nullable=False),
        sa.Column("commission", sa.Numeric(20, 2), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(20, 2), nullable=False),
        sa.Column("fx_fee", sa.Numeric(20, 2), nullable=False),
        sa.Column("cash_delta", sa.Numeric(20, 2), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 2), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("commission >= 0", name="ck_transactions_commission_non_negative"),
        sa.CheckConstraint(
            "execution_price > 0",
            name="ck_transactions_execution_price_positive",
        ),
        sa.CheckConstraint("fx_fee >= 0", name="ck_transactions_fx_fee_non_negative"),
        sa.CheckConstraint("fx_rate_to_base > 0", name="ck_transactions_fx_positive"),
        sa.CheckConstraint("gross_notional > 0", name="ck_transactions_notional_positive"),
        sa.CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
        sa.CheckConstraint(
            "reference_price > 0",
            name="ck_transactions_reference_price_positive",
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_transactions_side"),
        sa.CheckConstraint(
            "slippage_cost >= 0",
            name="ck_transactions_slippage_non_negative",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transactions_portfolio_executed",
        "transactions",
        ["portfolio_id", "executed_at"],
    )
    op.create_table(
        "cash_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(20, 2), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "balance_after >= 0",
            name="ck_cash_ledger_balance_non_negative",
        ),
        sa.CheckConstraint(
            "entry_type IN ('INITIAL_CAPITAL', 'TRADE')",
            name="ck_cash_ledger_entry_type",
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", name="uq_cash_ledger_transaction"),
    )
    op.create_index(
        "ix_cash_ledger_portfolio_effective",
        "cash_ledger_entries",
        ["portfolio_id", "effective_at"],
    )

    op.execute(
        """
        CREATE FUNCTION reject_ledger_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'sealed ledger rows are append-only';
        END;
        $$ LANGUAGE plpgsql
        """,
    )
    for table in ("transactions", "cash_ledger_entries"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation()
            """,
        )


def downgrade() -> None:
    for table in ("cash_ledger_entries", "transactions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_ledger_mutation()")
    op.drop_index("ix_cash_ledger_portfolio_effective", table_name="cash_ledger_entries")
    op.drop_table("cash_ledger_entries")
    op.drop_index("ix_transactions_portfolio_executed", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("positions")
    op.drop_table("assets")
    op.drop_table("portfolios")
