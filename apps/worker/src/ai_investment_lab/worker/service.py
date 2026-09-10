"""Application services for cached ingestion and reproducible portfolio snapshots."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import NoReturn
from uuid import UUID, uuid4

from ai_investment_lab.data_providers import MarketDataProvider, ProviderError
from ai_investment_lab.db.market_repository import MarketDataRepository
from ai_investment_lab.db.models import (
    ExchangeSessionModel,
    FxRateObservationModel,
    IngestionRunModel,
    ListingModel,
    PortfolioModel,
    PortfolioSnapshotModel,
    PriceObservationModel,
    SnapshotPositionModel,
    TransactionModel,
)
from ai_investment_lab.domain import MarketQuote, Portfolio, Position
from ai_investment_lab.domain.decimal_utils import ZERO, money

CALCULATION_VERSION = "phase2-v1"


class MissingMarketDataError(RuntimeError):
    """A valuation was frozen because an expected point-in-time input is absent."""


@dataclass(frozen=True)
class IngestionOutcome:
    run_id: UUID
    inserted: int
    unchanged: int
    missing_expected: int = 0
    cached: bool = False


@dataclass(frozen=True)
class DailyOutcome:
    valuation_date: date
    listings_processed: int
    snapshots_created: int
    run_id: UUID


def _dates(date_from: date, date_to: date) -> list[date]:
    return [date_from + timedelta(days=offset) for offset in range((date_to - date_from).days + 1)]


class MarketDataService:
    def __init__(self, repository: MarketDataRepository, provider: MarketDataProvider) -> None:
        self.repository = repository
        self.provider = provider

    def ingest_calendar(
        self,
        listing: ListingModel,
        *,
        year: int,
        execution_key: str,
    ) -> IngestionOutcome:
        if not listing.provider_exchange_code:
            raise MissingMarketDataError(f"listing {listing.id} has no provider exchange code")
        run, should_run = self.repository.start_run(
            job_type="EXCHANGE_CALENDAR",
            idempotency_key=(
                f"calendar:{listing.provider}:{listing.provider_exchange_code}:{year}:{execution_key}"
            ),
            requested_from=date(year, 1, 1),
            requested_to=date(year, 12, 31),
        )
        if not should_run:
            return IngestionOutcome(run_id=run.id, inserted=0, unchanged=0, cached=True)
        try:
            calendar = self.provider.exchange_calendar(listing.provider_exchange_code, year=year)
        except ProviderError as error:
            self.repository.finish_run(run, error=str(error))
            raise
        inserted = 0
        unchanged = 0
        for session_date in _dates(date(year, 1, 1), date(year, 12, 31)):
            _, created = self.repository.store_session(
                provider=self.provider.name,
                exchange_code=listing.provider_exchange_code,
                exchange_mic=listing.exchange_mic,
                timezone=calendar.timezone,
                definition=calendar.session(session_date),
                source_checksum=calendar.source_checksum,
                retrieved_at=calendar.retrieved_at,
                run=run,
            )
            inserted += int(created)
            unchanged += int(not created)
        self.repository.finish_run(run)
        return IngestionOutcome(run_id=run.id, inserted=inserted, unchanged=unchanged)

    def ingest_prices(
        self,
        listing: ListingModel,
        *,
        date_from: date,
        date_to: date,
        execution_key: str,
        refresh: bool = False,
    ) -> IngestionOutcome:
        if not listing.provider_symbol or not listing.provider_exchange_code:
            raise MissingMarketDataError(f"listing {listing.id} has incomplete provider metadata")
        run, should_run = self.repository.start_run(
            job_type="PRICE_HISTORY",
            idempotency_key=(
                f"prices:{listing.provider}:{listing.id}:{date_from}:{date_to}:{execution_key}"
            ),
            requested_from=date_from,
            requested_to=date_to,
        )
        if not should_run:
            return IngestionOutcome(run_id=run.id, inserted=0, unchanged=0, cached=True)

        sessions = {
            item.session_date: item
            for item in self.repository.list_sessions(
                listing.provider_exchange_code,
                date_from=date_from,
                date_to=date_to,
            )
        }
        if len(sessions) != len(_dates(date_from, date_to)):
            self.repository.finish_run(run, error="exchange calendar is incomplete")
            raise MissingMarketDataError(
                f"calendar for {listing.provider_exchange_code} does not cover the requested range"
            )
        cached_prices = {
            item.observation_date: item
            for item in self.repository.list_prices(
                listing.id,
                date_from=date_from,
                date_to=date_to,
            )
        }
        expected = {
            day for day, session in sessions.items() if session.status in {"OPEN", "EARLY_CLOSE"}
        }
        missing_before = expected - cached_prices.keys()
        if not refresh and not missing_before:
            self.repository.finish_run(run)
            return IngestionOutcome(
                run_id=run.id,
                inserted=0,
                unchanged=len(cached_prices),
                cached=True,
            )
        try:
            bars = self.provider.historical_prices(
                listing.provider_symbol,
                date_from=date_from,
                date_to=date_to,
            )
        except ProviderError as error:
            self.repository.finish_run(run, error=str(error))
            raise
        inserted = 0
        unchanged = 0
        for bar in bars:
            previous = self.repository.latest_price_before(listing.id, bar.observation_date)
            _, created = self.repository.store_price(listing=listing, bar=bar, run=run)
            inserted += int(created)
            unchanged += int(not created)
            if previous is not None:
                absolute_change = abs(bar.close / previous.close - Decimal("1"))
                if absolute_change >= Decimal("0.35"):
                    self.repository.record_issue(
                        listing_id=listing.id,
                        observation_date=bar.observation_date,
                        issue_type="IMPLAUSIBLE_PRICE_CHANGE",
                        detail=(
                            f"raw close changed {absolute_change:.2%}; reconcile a split, "
                            "symbol change, or provider error"
                        ),
                        run=run,
                    )
        observed = {
            item.observation_date
            for item in self.repository.list_prices(
                listing.id,
                date_from=date_from,
                date_to=date_to,
            )
        }
        missing = expected - observed
        for missing_date in sorted(missing):
            self.repository.record_issue(
                listing_id=listing.id,
                observation_date=missing_date,
                issue_type="MISSING_EXPECTED_PRICE",
                detail=(
                    f"{listing.provider_symbol} has no EOD bar for an expected "
                    f"{sessions[missing_date].status.lower()} session"
                ),
                run=run,
            )
        self.repository.finish_run(
            run,
            error=(f"{len(missing)} expected price observations are missing" if missing else None),
        )
        return IngestionOutcome(
            run_id=run.id,
            inserted=inserted,
            unchanged=unchanged,
            missing_expected=len(missing),
        )

    def ingest_fx(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        date_from: date,
        date_to: date,
        execution_key: str,
    ) -> IngestionOutcome:
        provider_symbol = f"{base_currency}{quote_currency}.FOREX"
        run, should_run = self.repository.start_run(
            job_type="FX_HISTORY",
            idempotency_key=(f"fx:{provider_symbol}:{date_from}:{date_to}:{execution_key}"),
            requested_from=date_from,
            requested_to=date_to,
        )
        if not should_run:
            return IngestionOutcome(run_id=run.id, inserted=0, unchanged=0, cached=True)
        try:
            bars = self.provider.historical_prices(
                provider_symbol,
                date_from=date_from,
                date_to=date_to,
            )
        except ProviderError as error:
            self.repository.finish_run(run, error=str(error))
            raise
        inserted = 0
        unchanged = 0
        for bar in bars:
            _, created = self.repository.store_fx_rate(
                base_currency=base_currency,
                quote_currency=quote_currency,
                provider_symbol=provider_symbol,
                bar=bar,
                run=run,
            )
            inserted += int(created)
            unchanged += int(not created)
        observed = {bar.observation_date for bar in bars}
        expected = {day for day in _dates(date_from, date_to) if day.weekday() < 5}
        missing = expected - observed
        self.repository.finish_run(
            run,
            error=(f"{len(missing)} expected FX observations are missing" if missing else None),
        )
        return IngestionOutcome(
            run_id=run.id,
            inserted=inserted,
            unchanged=unchanged,
            missing_expected=len(missing),
        )


class SnapshotService:
    def __init__(self, repository: MarketDataRepository) -> None:
        self.repository = repository

    def snapshot_portfolio(
        self,
        portfolio_record: PortfolioModel,
        *,
        valuation_date: date,
        run: IngestionRunModel,
    ) -> PortfolioSnapshotModel:
        if valuation_date < portfolio_record.created_at.date():
            raise ValueError("valuation date cannot precede portfolio creation")
        cutoff = datetime.combine(valuation_date, time.max, tzinfo=UTC)
        transactions = self.repository.transactions_through(portfolio_record.id, cutoff)
        positions = self._replay_positions(transactions)
        cash_balance = money(
            portfolio_record.starting_capital
            + sum((transaction.cash_delta for transaction in transactions), ZERO)
        )
        realized_pnl = money(sum((transaction.realized_pnl for transaction in transactions), ZERO))
        portfolio = Portfolio(
            id=portfolio_record.id,
            name=portfolio_record.name,
            base_currency=portfolio_record.base_currency,
            starting_capital=portfolio_record.starting_capital,
            cash_balance=cash_balance,
            realized_pnl=realized_pnl,
            positions=positions,
        )
        position_rows = [
            (position, self.repository.primary_listing(position.asset_id))
            for position in sorted(positions.values(), key=lambda item: str(item.asset_id))
        ]
        quotes: dict[UUID, MarketQuote] = {}
        inputs: list[dict[str, object]] = []
        position_inputs: list[
            tuple[
                Position,
                ListingModel,
                PriceObservationModel,
                FxRateObservationModel | None,
                ExchangeSessionModel,
                str,
            ]
        ] = []
        for position, listing in position_rows:
            if not listing.provider_exchange_code:
                self._fail(
                    listing,
                    valuation_date,
                    "MISSING_CALENDAR",
                    "listing has no provider exchange code",
                    run,
                )
            exchange_session = self.repository.latest_session(
                listing.provider_exchange_code,
                valuation_date,
            )
            if exchange_session is None:
                self._fail(
                    listing,
                    valuation_date,
                    "MISSING_CALENDAR",
                    "no exchange session is stored for the valuation date",
                    run,
                )
            price = self.repository.latest_price_on_or_before(listing.id, valuation_date)
            if price is None:
                self._fail(
                    listing,
                    valuation_date,
                    "MISSING_EXPECTED_PRICE",
                    "no price exists on or before the valuation date",
                    run,
                )
            assert exchange_session is not None
            assert price is not None
            if price.observation_date != valuation_date and exchange_session.status != "CLOSED":
                self._fail(
                    listing,
                    valuation_date,
                    "MISSING_EXPECTED_PRICE",
                    "the exchange was open but the valuation-date price is absent",
                    run,
                )
            fx = None
            fx_rate = Decimal("1")
            if listing.currency != portfolio.base_currency:
                fx = self.repository.latest_fx_on_or_before(
                    portfolio.base_currency,
                    listing.currency,
                    valuation_date,
                )
                if fx is None or (
                    fx.observation_date != valuation_date and valuation_date.weekday() < 5
                ):
                    self._fail(
                        listing,
                        valuation_date,
                        "MISSING_FX_RATE",
                        f"no eligible {portfolio.base_currency}/{listing.currency} FX close",
                        run,
                    )
                assert fx is not None
                fx_rate = fx.rate_to_base
            observed_at = datetime.combine(price.observation_date, time.max, tzinfo=UTC)
            quotes[position.asset_id] = MarketQuote(
                asset_id=position.asset_id,
                price=price.close,
                fx_rate_to_base=fx_rate,
                observed_at=observed_at,
            )
            status = "FRESH" if price.observation_date == valuation_date else "STALE_CLOSED_SESSION"
            inputs.append(
                {
                    "asset_id": str(position.asset_id),
                    "position_quantity": str(position.quantity),
                    "position_cost_basis": str(position.cost_basis),
                    "price_observation_id": str(price.id),
                    "exchange_session_id": str(exchange_session.id),
                    "fx_rate_observation_id": str(fx.id) if fx else None,
                }
            )
            position_inputs.append((position, listing, price, fx, exchange_session, status))
        fingerprint_payload = {
            "calculation_version": CALCULATION_VERSION,
            "portfolio_id": str(portfolio.id),
            "policy_version": portfolio_record.policy_version,
            "base_currency": portfolio.base_currency,
            "starting_capital": str(portfolio.starting_capital),
            "cash_balance": str(portfolio.cash_balance),
            "transaction_ids": [str(transaction.id) for transaction in transactions],
            "positions": inputs,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        existing = self.repository.find_snapshot(
            portfolio.id,
            valuation_date,
            fingerprint,
        )
        if existing is not None:
            return existing
        valuation = portfolio.value(quotes)
        previous = self.repository.latest_snapshot(portfolio.id, valuation_date)
        snapshot = PortfolioSnapshotModel(
            id=uuid4(),
            portfolio_id=portfolio.id,
            valuation_date=valuation_date,
            cash_balance=valuation.cash_balance,
            positions_value=valuation.market_value,
            total_value=valuation.total_value,
            realized_pnl=valuation.realized_pnl,
            unrealized_pnl=valuation.unrealized_pnl,
            total_return=valuation.total_return_fraction,
            calculation_version=CALCULATION_VERSION,
            input_fingerprint=fingerprint,
            revision=previous.revision + 1 if previous else 1,
            supersedes_id=previous.id if previous else None,
            ingestion_run_id=run.id,
        )
        valued_by_asset = {item.asset_id: item for item in valuation.positions}
        snapshot_positions: list[SnapshotPositionModel] = []
        for position, listing, price_value, fx_value, session_value, status in position_inputs:
            price = price_value
            fx = fx_value
            exchange_session = session_value
            valued = valued_by_asset[position.asset_id]
            snapshot_positions.append(
                SnapshotPositionModel(
                    snapshot_id=snapshot.id,
                    asset_id=position.asset_id,
                    listing_id=listing.id,
                    price_observation_id=price.id,
                    exchange_session_id=exchange_session.id,
                    fx_rate_observation_id=fx.id if fx else None,
                    quantity=position.quantity,
                    cost_basis=position.cost_basis,
                    price=price.close,
                    fx_rate_to_base=fx.rate_to_base if fx else Decimal("1"),
                    market_value=valued.market_value,
                    unrealized_pnl=valued.unrealized_pnl,
                    price_date=price.observation_date,
                    stale_days=(valuation_date - price.observation_date).days,
                    valuation_status=status,
                )
            )
        return self.repository.add_snapshot(snapshot, snapshot_positions)

    @staticmethod
    def _replay_positions(transactions: list[TransactionModel]) -> dict[UUID, Position]:
        state: dict[UUID, Position] = {}
        for transaction in transactions:
            position = state.get(transaction.asset_id)
            if transaction.side == "BUY":
                if position is None:
                    state[transaction.asset_id] = Position(
                        asset_id=transaction.asset_id,
                        quantity=transaction.quantity,
                        cost_basis=-transaction.cash_delta,
                    )
                else:
                    position.quantity += transaction.quantity
                    position.cost_basis = money(position.cost_basis - transaction.cash_delta)
                continue
            if position is None or transaction.quantity > position.quantity:
                raise RuntimeError("transaction ledger cannot be replayed into a valid position")
            removed_basis = money(transaction.cash_delta - transaction.realized_pnl)
            position.quantity -= transaction.quantity
            position.cost_basis = money(position.cost_basis - removed_basis)
            position.realized_pnl = money(position.realized_pnl + transaction.realized_pnl)
            if position.quantity == ZERO:
                del state[transaction.asset_id]
        return state

    def _fail(
        self,
        listing: ListingModel,
        valuation_date: date,
        issue_type: str,
        detail: str,
        run: IngestionRunModel,
    ) -> NoReturn:
        self.repository.record_issue(
            listing_id=listing.id,
            observation_date=valuation_date,
            issue_type=issue_type,
            detail=detail,
            run=run,
        )
        raise MissingMarketDataError(f"{listing.ticker}: {detail}")


class DailyJob:
    """Idempotent composition root for one completed UTC valuation date."""

    def __init__(
        self,
        repository: MarketDataRepository,
        provider: MarketDataProvider,
    ) -> None:
        self.repository = repository
        self.market_data = MarketDataService(repository, provider)
        self.snapshots = SnapshotService(repository)

    def run(self, valuation_date: date, *, execution_key: str | None = None) -> DailyOutcome:
        execution_key = execution_key or valuation_date.isoformat()
        listings = self.repository.active_primary_listings()
        for listing in listings:
            self.market_data.ingest_calendar(
                listing,
                year=valuation_date.year,
                execution_key=execution_key,
            )
            self.market_data.ingest_prices(
                listing,
                date_from=valuation_date,
                date_to=valuation_date,
                execution_key=execution_key,
                refresh=True,
            )
        portfolios = self.repository.portfolios()
        currencies = {
            listing.currency
            for listing in listings
            if any(portfolio.base_currency != listing.currency for portfolio in portfolios)
        }
        for currency in sorted(currencies):
            self.market_data.ingest_fx(
                base_currency="EUR",
                quote_currency=currency,
                date_from=valuation_date,
                date_to=valuation_date,
                execution_key=execution_key,
            )
        run, should_run = self.repository.start_run(
            job_type="DAILY_SNAPSHOT",
            idempotency_key=f"snapshots:{valuation_date}:{execution_key}",
            requested_from=valuation_date,
            requested_to=valuation_date,
        )
        if not should_run:
            return DailyOutcome(
                valuation_date=valuation_date,
                listings_processed=len(listings),
                snapshots_created=0,
                run_id=run.id,
            )
        created = 0
        try:
            for portfolio in portfolios:
                prior = self.repository.latest_snapshot(portfolio.id, valuation_date)
                snapshot = self.snapshots.snapshot_portfolio(
                    portfolio,
                    valuation_date=valuation_date,
                    run=run,
                )
                created += int(prior is None or prior.id != snapshot.id)
        except MissingMarketDataError as error:
            self.repository.finish_run(run, error=str(error))
            raise
        self.repository.finish_run(run)
        return DailyOutcome(
            valuation_date=valuation_date,
            listings_processed=len(listings),
            snapshots_created=created,
            run_id=run.id,
        )
