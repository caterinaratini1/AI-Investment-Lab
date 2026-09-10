from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_investment_lab.db import (
    CashLedgerEntryModel,
    PortfolioRepository,
    PositionModel,
    TransactionModel,
)
from ai_investment_lab.domain import InsufficientCashError, TradeRequest, TradeSide


def test_repository_persists_portfolio_trade_position_and_ledgers(session: Session) -> None:
    repository = PortfolioRepository(session)
    with session.begin():
        portfolio = repository.create_portfolio(name="Initial experiment")
        asset = repository.create_asset(
            name="Example Corp",
            ticker="exam",
            isin="IE00B4L5Y983",
            exchange_mic="XAMS",
            currency="EUR",
            asset_type="PUBLIC_EQUITY",
        )
        transaction, position = repository.execute_trade(
            TradeRequest(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                asset_currency="EUR",
                side=TradeSide.BUY,
                quantity=Decimal("10"),
                reference_price=Decimal("100"),
                fx_rate_to_base=Decimal("1"),
                executed_at=datetime(2026, 9, 11, 7, 0, tzinfo=UTC),
            ),
        )

    assert transaction.gross_notional == Decimal("1000.50")
    assert position is not None
    assert position.quantity == Decimal("10.00000000")
    assert portfolio.cash_balance == Decimal("8998.50")
    assert session.scalar(select(func.count()).select_from(TransactionModel)) == 1
    assert session.scalar(select(func.count()).select_from(PositionModel)) == 1
    ledger = list(
        session.scalars(
            select(CashLedgerEntryModel).order_by(CashLedgerEntryModel.effective_at),
        ),
    )
    assert [entry.entry_type for entry in ledger] == ["INITIAL_CAPITAL", "TRADE"]
    assert [entry.balance_after for entry in ledger] == [
        Decimal("10000.00"),
        Decimal("8998.50"),
    ]


def test_repository_full_sell_removes_position_and_persists_loss(session: Session) -> None:
    repository = PortfolioRepository(session)
    with session.begin():
        portfolio = repository.create_portfolio(name="Initial experiment")
        asset = repository.create_asset(
            name="Example Corp",
            ticker="EXAM",
            isin="IE00B4L5Y983",
            exchange_mic="XAMS",
            currency="EUR",
            asset_type="PUBLIC_EQUITY",
        )
        repository.execute_trade(
            TradeRequest(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                asset_currency="EUR",
                side=TradeSide.BUY,
                quantity=Decimal("10"),
                reference_price=Decimal("100"),
                fx_rate_to_base=Decimal("1"),
                executed_at=datetime(2026, 9, 11, 7, 0, tzinfo=UTC),
            ),
        )
        transaction, position = repository.execute_trade(
            TradeRequest(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                asset_currency="EUR",
                side=TradeSide.SELL,
                quantity=Decimal("10"),
                reference_price=Decimal("90"),
                fx_rate_to_base=Decimal("1"),
                executed_at=datetime(2026, 9, 14, 7, 0, tzinfo=UTC),
            ),
        )

    assert position is None
    assert transaction.realized_pnl == Decimal("-102.95")
    assert portfolio.realized_pnl == Decimal("-102.95")
    assert repository.list_positions(portfolio.id) == []


def test_repository_failed_buy_can_be_rolled_back_without_ledger_mutation(
    session: Session,
) -> None:
    repository = PortfolioRepository(session)
    with session.begin():
        portfolio = repository.create_portfolio(name="Initial experiment")
        asset = repository.create_asset(
            name="Example Corp",
            ticker="EXAM",
            isin="IE00B4L5Y983",
            exchange_mic="XAMS",
            currency="EUR",
            asset_type="PUBLIC_EQUITY",
        )

    with pytest.raises(InsufficientCashError), session.begin():
        repository.execute_trade(
            TradeRequest(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                asset_currency="EUR",
                side=TradeSide.BUY,
                quantity=Decimal("1000"),
                reference_price=Decimal("100"),
                fx_rate_to_base=Decimal("1"),
                executed_at=datetime(2026, 9, 11, 7, 0, tzinfo=UTC),
            ),
        )

    session.expire_all()
    refreshed = repository.get_portfolio(portfolio.id)
    assert refreshed.cash_balance == Decimal("10000.00")
    assert session.scalar(select(func.count()).select_from(TransactionModel)) == 0
    assert session.scalar(select(func.count()).select_from(CashLedgerEntryModel)) == 1
