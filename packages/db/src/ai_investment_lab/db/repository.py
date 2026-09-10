"""Transactional repository for portfolios and their append-only ledgers."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_investment_lab.db.models import (
    AssetModel,
    CashLedgerEntryModel,
    ListingModel,
    PortfolioModel,
    PositionModel,
    TransactionModel,
)
from ai_investment_lab.domain import CostModel, Portfolio, Position, TradeExecution, TradeRequest


class RecordNotFoundError(LookupError):
    """A requested persistence record does not exist."""


@dataclass(frozen=True)
class AssetRecord:
    """Stable security identity paired with its primary tradable listing."""

    asset: AssetModel
    listing: ListingModel

    @property
    def id(self) -> UUID:
        return self.asset.id

    @property
    def currency(self) -> str:
        return self.listing.currency


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_portfolio(
        self,
        *,
        name: str,
        starting_capital: Decimal = Decimal("10000.00"),
        base_currency: str = "EUR",
        policy_version: str = "0.1.0",
    ) -> PortfolioModel:
        portfolio = Portfolio.open(
            name=name,
            starting_capital=starting_capital,
            base_currency=base_currency,
        )
        record = PortfolioModel(
            id=portfolio.id,
            name=portfolio.name,
            base_currency=portfolio.base_currency,
            starting_capital=portfolio.starting_capital,
            cash_balance=portfolio.cash_balance,
            realized_pnl=portfolio.realized_pnl,
            policy_version=policy_version,
        )
        self.session.add(record)
        self.session.flush()
        self.session.add(
            CashLedgerEntryModel(
                portfolio_id=record.id,
                entry_type="INITIAL_CAPITAL",
                amount=portfolio.starting_capital,
                balance_after=portfolio.cash_balance,
                effective_at=datetime.now(UTC),
            ),
        )
        self.session.flush()
        return record

    def get_portfolio(self, portfolio_id: UUID, *, for_update: bool = False) -> PortfolioModel:
        statement = select(PortfolioModel).where(PortfolioModel.id == portfolio_id)
        if for_update:
            statement = statement.with_for_update()
        record = self.session.scalar(statement)
        if record is None:
            raise RecordNotFoundError(f"portfolio {portfolio_id} was not found")
        return record

    def create_asset(
        self,
        *,
        name: str,
        ticker: str,
        isin: str,
        exchange_mic: str,
        currency: str,
        asset_type: str,
        sector: str | None = None,
        provider: str = "EODHD",
        provider_symbol: str | None = None,
        provider_exchange_code: str | None = None,
        exchange_timezone: str | None = None,
    ) -> AssetRecord:
        asset = AssetModel(
            name=name.strip(),
            isin=isin.strip().upper(),
            asset_type=asset_type,
            sector=sector.strip() if sector else None,
        )
        self.session.add(asset)
        self.session.flush()
        listing = ListingModel(
            asset_id=asset.id,
            ticker=ticker.strip().upper(),
            exchange_mic=exchange_mic.strip().upper(),
            currency=currency.strip().upper(),
            provider=provider.strip().upper(),
            provider_symbol=provider_symbol.strip().upper() if provider_symbol else None,
            provider_exchange_code=(
                provider_exchange_code.strip().upper() if provider_exchange_code else None
            ),
            exchange_timezone=exchange_timezone.strip() if exchange_timezone else None,
            is_primary=True,
        )
        self.session.add(listing)
        self.session.flush()
        return AssetRecord(asset=asset, listing=listing)

    def get_asset(self, asset_id: UUID) -> AssetRecord:
        asset = self.session.get(AssetModel, asset_id)
        if asset is None:
            raise RecordNotFoundError(f"asset {asset_id} was not found")
        listing = self.session.scalar(
            select(ListingModel).where(
                ListingModel.asset_id == asset_id,
                ListingModel.is_primary.is_(True),
                ListingModel.active.is_(True),
            )
        )
        if listing is None:
            raise RecordNotFoundError(f"asset {asset_id} has no active primary listing")
        return AssetRecord(asset=asset, listing=listing)

    def get_listing(self, listing_id: UUID) -> ListingModel:
        listing = self.session.get(ListingModel, listing_id)
        if listing is None:
            raise RecordNotFoundError(f"listing {listing_id} was not found")
        return listing

    def list_positions(self, portfolio_id: UUID) -> list[PositionModel]:
        self.get_portfolio(portfolio_id)
        statement = (
            select(PositionModel)
            .where(PositionModel.portfolio_id == portfolio_id)
            .order_by(PositionModel.asset_id)
        )
        return list(self.session.scalars(statement))

    def list_transactions(self, portfolio_id: UUID) -> list[TransactionModel]:
        self.get_portfolio(portfolio_id)
        statement = (
            select(TransactionModel)
            .where(TransactionModel.portfolio_id == portfolio_id)
            .order_by(TransactionModel.executed_at, TransactionModel.created_at)
        )
        return list(self.session.scalars(statement))

    def get_transaction(self, portfolio_id: UUID, transaction_id: UUID) -> TransactionModel:
        statement = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.portfolio_id == portfolio_id,
        )
        record = self.session.scalar(statement)
        if record is None:
            raise RecordNotFoundError(
                f"transaction {transaction_id} was not found in portfolio {portfolio_id}",
            )
        return record

    def execute_trade(
        self,
        request: TradeRequest,
        *,
        costs: CostModel | None = None,
    ) -> tuple[TransactionModel, PositionModel | None]:
        portfolio_record = self.get_portfolio(request.portfolio_id, for_update=True)
        asset_record = self.get_asset(request.asset_id)
        if asset_record.currency != request.asset_currency:
            raise ValueError(
                f"trade currency {request.asset_currency} does not match asset currency "
                f"{asset_record.currency}",
            )
        position_statement = (
            select(PositionModel)
            .where(
                PositionModel.portfolio_id == request.portfolio_id,
                PositionModel.asset_id == request.asset_id,
            )
            .with_for_update()
        )
        position_record = self.session.scalar(position_statement)
        positions: dict[UUID, Position] = {}
        if position_record is not None:
            positions[position_record.asset_id] = Position(
                asset_id=position_record.asset_id,
                quantity=position_record.quantity,
                cost_basis=position_record.cost_basis,
                realized_pnl=position_record.realized_pnl,
            )
        portfolio = Portfolio(
            id=portfolio_record.id,
            name=portfolio_record.name,
            base_currency=portfolio_record.base_currency,
            starting_capital=portfolio_record.starting_capital,
            cash_balance=portfolio_record.cash_balance,
            realized_pnl=portfolio_record.realized_pnl,
            positions=positions,
        )
        execution = portfolio.execute(request, costs=costs)
        portfolio_record.cash_balance = portfolio.cash_balance
        portfolio_record.realized_pnl = portfolio.realized_pnl
        portfolio_record.version += 1

        current = portfolio.positions.get(request.asset_id)
        if current is None:
            if position_record is not None:
                self.session.delete(position_record)
            persisted_position = None
        elif position_record is None:
            persisted_position = PositionModel(
                portfolio_id=portfolio.id,
                asset_id=request.asset_id,
                quantity=current.quantity,
                cost_basis=current.cost_basis,
                realized_pnl=current.realized_pnl,
                opened_at=request.executed_at,
            )
            self.session.add(persisted_position)
        else:
            position_record.quantity = current.quantity
            position_record.cost_basis = current.cost_basis
            position_record.realized_pnl = current.realized_pnl
            persisted_position = position_record

        transaction = self._transaction_from_execution(execution)
        self.session.add(transaction)
        self.session.flush()
        self.session.add(
            CashLedgerEntryModel(
                portfolio_id=portfolio.id,
                transaction_id=transaction.id,
                entry_type="TRADE",
                amount=execution.cash_delta,
                balance_after=portfolio.cash_balance,
                effective_at=execution.executed_at,
            ),
        )
        self.session.flush()
        return transaction, persisted_position

    @staticmethod
    def _transaction_from_execution(execution: TradeExecution) -> TransactionModel:
        return TransactionModel(
            id=execution.id,
            portfolio_id=execution.portfolio_id,
            asset_id=execution.asset_id,
            decision_id=execution.decision_id,
            side=execution.side.value,
            asset_currency=execution.asset_currency,
            quantity=execution.quantity,
            reference_price=execution.reference_price,
            execution_price=execution.execution_price,
            fx_rate_to_base=execution.fx_rate_to_base,
            gross_notional=execution.gross_notional,
            commission=execution.commission,
            slippage_cost=execution.slippage_cost,
            fx_fee=execution.fx_fee,
            cash_delta=execution.cash_delta,
            realized_pnl=execution.realized_pnl,
            executed_at=execution.executed_at,
        )
