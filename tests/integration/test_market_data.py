from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal, cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_investment_lab.data_providers import (
    ExchangeCalendar,
    InstrumentMatch,
    PriceBar,
    ProviderRequestError,
)
from ai_investment_lab.db import (
    DataQualityIssueModel,
    MarketDataRepository,
    PortfolioRepository,
    PortfolioSnapshotModel,
    PriceObservationModel,
)
from ai_investment_lab.db.models import ListingModel
from ai_investment_lab.db.repository import AssetRecord
from ai_investment_lab.domain import TradeRequest, TradeSide
from ai_investment_lab.worker import DailyJob, MarketDataService, MissingMarketDataError
from ai_investment_lab.worker.service import SnapshotService


def price_bar(day: date, close: str, *, checksum: str | None = None) -> PriceBar:
    value = Decimal(close)
    return PriceBar(
        observation_date=day,
        open=value,
        high=value + Decimal("1"),
        low=value - Decimal("1"),
        close=value,
        adjusted_close=value,
        volume=Decimal("1000"),
        retrieved_at=datetime(2026, 9, 11, 6, tzinfo=UTC),
        source_checksum=checksum or close.zfill(64),
        raw_payload={"date": day.isoformat(), "close": close},
    )


class FakeProvider:
    name = "EODHD"

    def __init__(self, prices: dict[str, list[PriceBar]] | None = None) -> None:
        self.prices = prices or {}
        self.price_calls = 0
        self.calendar_calls = 0
        self.failure: ProviderRequestError | None = None

    def search(
        self,
        query: str,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[InstrumentMatch]:
        del query, exchange, instrument_type, limit
        return []

    def historical_prices(
        self,
        provider_symbol: str,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[PriceBar]:
        self.price_calls += 1
        if self.failure:
            raise self.failure
        return [
            bar
            for bar in self.prices.get(provider_symbol, [])
            if date_from <= bar.observation_date <= date_to
        ]

    def exchange_calendar(self, exchange_code: str, *, year: int) -> ExchangeCalendar:
        del year
        self.calendar_calls += 1
        return ExchangeCalendar(
            exchange_code=exchange_code,
            timezone="Europe/Amsterdam",
            working_weekdays=frozenset({0, 1, 2, 3, 4}),
            regular_close=time(17, 40),
            holidays=(),
            retrieved_at=datetime(2026, 9, 10, 20, tzinfo=UTC),
            source_checksum="c" * 64,
        )


def create_asset(
    session: Session,
    *,
    currency: str = "EUR",
    isin: str = "IE00B4L5Y983",
) -> tuple[PortfolioRepository, AssetRecord, ListingModel]:
    portfolio_repository = PortfolioRepository(session)
    asset = portfolio_repository.create_asset(
        name="Example Corp",
        ticker="EXAM",
        isin=isin,
        exchange_mic="XAMS",
        currency=currency,
        asset_type="PUBLIC_EQUITY",
        provider_symbol="EXAM.AS",
        provider_exchange_code="AS",
        exchange_timezone="Europe/Amsterdam",
    )
    return portfolio_repository, asset, asset.listing


def seed_session_and_price(
    repository: MarketDataRepository,
    listing: ListingModel,
    day: date,
    *,
    status: str = "OPEN",
    price_day: date | None = None,
    close: str = "110",
) -> PriceObservationModel:
    run, _ = repository.start_run(
        job_type="TEST_FIXTURE",
        idempotency_key=f"fixture:{listing.id}:{day}:{status}:{close}",
    )
    definition = FakeProvider().exchange_calendar("AS", year=day.year).session(day)
    definition = definition.__class__(
        session_date=day,
        status=cast(Literal["OPEN", "CLOSED", "EARLY_CLOSE"], status),
        holiday_name="Weekend" if status == "CLOSED" else None,
        close_time=None if status == "CLOSED" else time(17, 40),
    )
    repository.store_session(
        provider="EODHD",
        exchange_code="AS",
        exchange_mic="XAMS",
        timezone="Europe/Amsterdam",
        definition=definition,
        source_checksum="s" * 64,
        retrieved_at=datetime(2026, 9, 10, 20, tzinfo=UTC),
        run=run,
    )
    price, _ = repository.store_price(
        listing=listing,
        bar=price_bar(price_day or day, close),
        run=run,
    )
    repository.finish_run(run)
    return price


def test_ingestion_caches_history_versions_corrections_and_tracks_missing_data(
    session: Session,
) -> None:
    _, _, listing = create_asset(session)
    provider = FakeProvider({"EXAM.AS": [price_bar(date(2026, 9, 10), "100", checksum="a" * 64)]})
    repository = MarketDataRepository(session)
    service = MarketDataService(repository, provider)
    calendar = service.ingest_calendar(listing, year=2026, execution_key="first")
    outcome = service.ingest_prices(
        listing,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
        execution_key="first",
    )

    assert calendar.inserted == 365
    assert outcome.inserted == 1
    assert outcome.missing_expected == 1
    issue = repository.list_issues()[0]
    assert issue.observation_date == date(2026, 9, 11)
    assert issue.issue_type == "MISSING_EXPECTED_PRICE"

    provider.prices["EXAM.AS"].append(price_bar(date(2026, 9, 11), "101", checksum="b" * 64))
    filled = service.ingest_prices(
        listing,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
        execution_key="first",
    )
    assert filled.inserted == 1
    assert repository.list_issues(status="RESOLVED")[0].id == issue.id

    cached = service.ingest_prices(
        listing,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
        execution_key="cached",
    )
    repeated = service.ingest_prices(
        listing,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
        execution_key="cached",
    )
    assert cached.cached is True
    assert repeated.cached is True

    provider.prices["EXAM.AS"][0] = price_bar(date(2026, 9, 10), "102", checksum="d" * 64)
    corrected = service.ingest_prices(
        listing,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
        execution_key="correction",
        refresh=True,
    )
    current = repository.list_prices(
        listing.id,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 12),
    )
    assert corrected.inserted == 1
    assert current[0].revision == 2
    assert current[0].supersedes_id is not None
    assert any(item.issue_type == "PRICE_CORRECTION" for item in repository.list_issues())
    assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 3

    provider.prices["EXAM.AS"].append(price_bar(date(2026, 9, 14), "200", checksum="e" * 64))
    service.ingest_prices(
        listing,
        date_from=date(2026, 9, 14),
        date_to=date(2026, 9, 14),
        execution_key="anomaly",
        refresh=True,
    )
    assert any(item.issue_type == "IMPLAUSIBLE_PRICE_CHANGE" for item in repository.list_issues())


def test_ingestion_requires_complete_calendar_and_records_provider_failure(
    session: Session,
) -> None:
    _, _, listing = create_asset(session)
    provider = FakeProvider()
    repository = MarketDataRepository(session)
    service = MarketDataService(repository, provider)

    with pytest.raises(MissingMarketDataError, match="does not cover"):
        service.ingest_prices(
            listing,
            date_from=date(2026, 9, 10),
            date_to=date(2026, 9, 10),
            execution_key="no-calendar",
        )
    failed_run, retried = repository.start_run(
        job_type="PRICE_HISTORY",
        idempotency_key=f"prices:EODHD:{listing.id}:2026-09-10:2026-09-10:no-calendar",
    )
    assert failed_run.status == "RUNNING"
    assert retried is True

    service.ingest_calendar(listing, year=2026, execution_key="calendar")
    provider.failure = ProviderRequestError("upstream unavailable")
    with pytest.raises(ProviderRequestError, match="unavailable"):
        service.ingest_prices(
            listing,
            date_from=date(2026, 9, 10),
            date_to=date(2026, 9, 10),
            execution_key="provider-failure",
        )
    run, should_run = repository.start_run(
        job_type="PRICE_HISTORY",
        idempotency_key=f"prices:EODHD:{listing.id}:2026-09-10:2026-09-10:provider-failure",
    )
    assert run.status == "RUNNING"
    assert should_run is True


def test_ingestion_run_lease_blocks_concurrency_and_recovers_abandoned_work(
    session: Session,
) -> None:
    repository = MarketDataRepository(session)
    run, first = repository.start_run(job_type="TEST", idempotency_key="leased-job")
    same, concurrent = repository.start_run(job_type="TEST", idempotency_key="leased-job")
    assert first is True
    assert concurrent is False
    assert same.id == run.id

    run.started_at = datetime.now(UTC) - timedelta(hours=7)
    recovered, should_run = repository.start_run(job_type="TEST", idempotency_key="leased-job")
    assert recovered.id == run.id
    assert should_run is True


def test_snapshot_is_reproducible_versions_corrections_and_labels_holiday_carry(
    session: Session,
) -> None:
    portfolios, asset, listing = create_asset(session)
    portfolio = portfolios.create_portfolio(name="Experiment")
    portfolios.execute_trade(
        TradeRequest(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            asset_currency="EUR",
            side=TradeSide.BUY,
            quantity=Decimal("10"),
            reference_price=Decimal("100"),
            fx_rate_to_base=Decimal("1"),
            executed_at=datetime(2026, 9, 10, 7, tzinfo=UTC),
        )
    )
    repository = MarketDataRepository(session)
    seed_session_and_price(repository, listing, date(2026, 9, 11))
    run, _ = repository.start_run(job_type="DAILY_SNAPSHOT", idempotency_key="snapshot:first")
    service = SnapshotService(repository)

    snapshot = service.snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 11),
        run=run,
    )
    duplicate = service.snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 11),
        run=run,
    )
    assert snapshot.id == duplicate.id
    assert snapshot.positions_value == Decimal("1100.00")
    assert snapshot.total_value == Decimal("10098.50")
    assert repository.snapshot_positions(snapshot.id)[0].valuation_status == "FRESH"

    correction_run, _ = repository.start_run(
        job_type="PRICE_HISTORY", idempotency_key="fixture:correction"
    )
    repository.store_price(
        listing=listing,
        bar=price_bar(date(2026, 9, 11), "112", checksum="z" * 64),
        run=correction_run,
    )
    corrected = service.snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 11),
        run=run,
    )
    assert corrected.revision == 2
    assert corrected.supersedes_id == snapshot.id

    portfolios.execute_trade(
        TradeRequest(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            asset_currency="EUR",
            side=TradeSide.SELL,
            quantity=Decimal("4"),
            reference_price=Decimal("120"),
            fx_rate_to_base=Decimal("1"),
            executed_at=datetime(2026, 9, 14, 7, tzinfo=UTC),
        )
    )
    historical = service.snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 11),
        run=run,
    )
    assert historical.id == corrected.id
    assert repository.snapshot_positions(historical.id)[0].quantity == Decimal("10")

    seed_session_and_price(
        repository,
        listing,
        date(2026, 9, 12),
        status="CLOSED",
        price_day=date(2026, 9, 11),
        close="112",
    )
    weekend = service.snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 12),
        run=run,
    )
    position = repository.snapshot_positions(weekend.id)[0]
    assert position.valuation_status == "STALE_CLOSED_SESSION"
    assert position.stale_days == 1
    assert [item.valuation_date for item in repository.list_snapshots(portfolio.id)] == [
        date(2026, 9, 11),
        date(2026, 9, 12),
    ]


def test_snapshot_freezes_on_missing_open_session_price(session: Session) -> None:
    portfolios, asset, listing = create_asset(session)
    portfolio = portfolios.create_portfolio(name="Experiment")
    portfolios.execute_trade(
        TradeRequest(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            asset_currency="EUR",
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            reference_price=Decimal("100"),
            fx_rate_to_base=Decimal("1"),
            executed_at=datetime(2026, 9, 10, 7, tzinfo=UTC),
        )
    )
    repository = MarketDataRepository(session)
    seed_session_and_price(repository, listing, date(2026, 9, 11))
    run, _ = repository.start_run(job_type="DAILY_SNAPSHOT", idempotency_key="missing-open")
    definition = FakeProvider().exchange_calendar("AS", year=2026).session(date(2026, 9, 14))
    repository.store_session(
        provider="EODHD",
        exchange_code="AS",
        exchange_mic="XAMS",
        timezone="Europe/Amsterdam",
        definition=definition,
        source_checksum="m" * 64,
        retrieved_at=datetime.now(UTC),
        run=run,
    )

    with pytest.raises(MissingMarketDataError, match="exchange was open"):
        SnapshotService(repository).snapshot_portfolio(
            portfolio,
            valuation_date=date(2026, 9, 14),
            run=run,
        )

    issue = session.scalar(
        select(DataQualityIssueModel).where(
            DataQualityIssueModel.observation_date == date(2026, 9, 14)
        )
    )
    assert issue is not None and issue.status == "OPEN"


def test_non_eur_snapshot_uses_normalized_fx_rate(session: Session) -> None:
    portfolios, asset, listing = create_asset(
        session,
        currency="USD",
        isin="US0378331005",
    )
    portfolio = portfolios.create_portfolio(name="Experiment")
    portfolios.execute_trade(
        TradeRequest(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            asset_currency="USD",
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            reference_price=Decimal("100"),
            fx_rate_to_base=Decimal("0.8"),
            executed_at=datetime(2026, 9, 10, 7, tzinfo=UTC),
        )
    )
    repository = MarketDataRepository(session)
    seed_session_and_price(repository, listing, date(2026, 9, 11), close="110")
    run, _ = repository.start_run(job_type="FX_HISTORY", idempotency_key="fx:first")
    fx, created = repository.store_fx_rate(
        base_currency="EUR",
        quote_currency="USD",
        provider_symbol="EURUSD.FOREX",
        bar=price_bar(date(2026, 9, 11), "1.25", checksum="f" * 64),
        run=run,
    )
    same, duplicate = repository.store_fx_rate(
        base_currency="EUR",
        quote_currency="USD",
        provider_symbol="EURUSD.FOREX",
        bar=price_bar(date(2026, 9, 11), "1.25", checksum="f" * 64),
        run=run,
    )
    assert created is True and duplicate is False and same.id == fx.id
    assert fx.rate_to_base == Decimal("0.800000000000")

    snapshot_run, _ = repository.start_run(job_type="DAILY_SNAPSHOT", idempotency_key="snapshot:fx")
    snapshot = SnapshotService(repository).snapshot_portfolio(
        portfolio,
        valuation_date=date(2026, 9, 11),
        run=snapshot_run,
    )
    assert snapshot.positions_value == Decimal("88.00")


def test_missing_fx_run_retries_with_the_same_idempotency_key(session: Session) -> None:
    provider = FakeProvider()
    repository = MarketDataRepository(session)
    service = MarketDataService(repository, provider)
    missing = service.ingest_fx(
        base_currency="EUR",
        quote_currency="USD",
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 10),
        execution_key="daily",
    )
    assert missing.missing_expected == 1

    provider.prices["EURUSD.FOREX"] = [price_bar(date(2026, 9, 10), "1.25", checksum="x" * 64)]
    retried = service.ingest_fx(
        base_currency="EUR",
        quote_currency="USD",
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 10),
        execution_key="daily",
    )
    cached = service.ingest_fx(
        base_currency="EUR",
        quote_currency="USD",
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 10),
        execution_key="daily",
    )
    assert retried.inserted == 1
    assert cached.cached is True


def test_daily_job_is_idempotent_for_prices_and_snapshots(session: Session) -> None:
    portfolios, _, listing = create_asset(session)
    portfolios.create_portfolio(name="Cash portfolio")
    provider = FakeProvider({"EXAM.AS": [price_bar(date(2026, 9, 10), "100", checksum="a" * 64)]})
    job = DailyJob(MarketDataRepository(session), provider)

    first = job.run(date(2026, 9, 10))
    second = job.run(date(2026, 9, 10))

    assert first.listings_processed == 1
    assert first.snapshots_created == 1
    assert second.snapshots_created == 0
    assert provider.price_calls == 1
    assert session.scalar(select(func.count()).select_from(PortfolioSnapshotModel)) == 1
    assert listing.provider_symbol == "EXAM.AS"


def test_daily_job_explicit_key_restates_a_corrected_snapshot(session: Session) -> None:
    portfolios, asset, _ = create_asset(session)
    portfolio = portfolios.create_portfolio(name="Invested portfolio")
    portfolios.execute_trade(
        TradeRequest(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            asset_currency="EUR",
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            reference_price=Decimal("90"),
            fx_rate_to_base=Decimal("1"),
            executed_at=datetime(2026, 9, 10, 7, tzinfo=UTC),
        )
    )
    provider = FakeProvider({"EXAM.AS": [price_bar(date(2026, 9, 10), "100", checksum="a" * 64)]})
    job = DailyJob(MarketDataRepository(session), provider)

    first = job.run(date(2026, 9, 10))
    provider.prices["EXAM.AS"] = [price_bar(date(2026, 9, 10), "110", checksum="b" * 64)]
    restated = job.run(date(2026, 9, 10), execution_key="provider-correction-1")

    assert first.snapshots_created == 1
    assert restated.snapshots_created == 1
    snapshots = session.scalars(
        select(PortfolioSnapshotModel).order_by(PortfolioSnapshotModel.revision)
    ).all()
    assert len(snapshots) == 2
    assert snapshots[1].revision == 2
    assert snapshots[1].supersedes_id == snapshots[0].id
    assert snapshots[1].total_value > snapshots[0].total_value
