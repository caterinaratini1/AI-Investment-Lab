"""Persistence operations for versioned market data and valuation snapshots."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_investment_lab.db.models import (
    DataQualityIssueModel,
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
from ai_investment_lab.db.repository import RecordNotFoundError


class PriceBarInput(Protocol):
    @property
    def observation_date(self) -> date: ...

    @property
    def open(self) -> Decimal: ...

    @property
    def high(self) -> Decimal: ...

    @property
    def low(self) -> Decimal: ...

    @property
    def close(self) -> Decimal: ...

    @property
    def adjusted_close(self) -> Decimal: ...

    @property
    def volume(self) -> Decimal: ...

    @property
    def retrieved_at(self) -> datetime: ...

    @property
    def source_checksum(self) -> str: ...

    @property
    def raw_payload(self) -> dict[str, object]: ...


class SessionInput(Protocol):
    @property
    def session_date(self) -> date: ...

    @property
    def status(self) -> str: ...

    @property
    def holiday_name(self) -> str | None: ...

    @property
    def close_time(self) -> time | None: ...


class MarketDataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start_run(
        self,
        *,
        job_type: str,
        idempotency_key: str,
        requested_from: date | None = None,
        requested_to: date | None = None,
    ) -> tuple[IngestionRunModel, bool]:
        existing = self.session.scalar(
            select(IngestionRunModel).where(IngestionRunModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            now = datetime.now(UTC)
            started_at = existing.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            lease_expired = now - started_at > timedelta(hours=6)
            if existing.status == "FAILED" or (existing.status == "RUNNING" and lease_expired):
                existing.status = "RUNNING"
                existing.error = None
                existing.completed_at = None
                existing.started_at = now
                self.session.flush()
                return existing, True
            return existing, False
        run = IngestionRunModel(
            job_type=job_type,
            idempotency_key=idempotency_key,
            requested_from=requested_from,
            requested_to=requested_to,
        )
        self.session.add(run)
        self.session.flush()
        return run, True

    def finish_run(self, run: IngestionRunModel, *, error: str | None = None) -> None:
        run.status = "FAILED" if error else "SUCCEEDED"
        run.error = error
        run.completed_at = datetime.now(UTC)
        self.session.flush()

    def store_price(
        self,
        *,
        listing: ListingModel,
        bar: PriceBarInput,
        run: IngestionRunModel,
    ) -> tuple[PriceObservationModel, bool]:
        current = self._latest_price(listing.id, bar.observation_date)
        if current is not None and current.source_checksum == bar.source_checksum:
            self.resolve_issue(
                listing_id=listing.id,
                observation_date=bar.observation_date,
                issue_type="MISSING_EXPECTED_PRICE",
            )
            return current, False
        record = PriceObservationModel(
            listing_id=listing.id,
            provider=listing.provider,
            provider_symbol=listing.provider_symbol or "",
            observation_date=bar.observation_date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            adjusted_close=bar.adjusted_close,
            volume=bar.volume,
            currency=listing.currency,
            revision=(current.revision + 1 if current else 1),
            supersedes_id=current.id if current else None,
            retrieved_at=bar.retrieved_at,
            source_checksum=bar.source_checksum,
            raw_payload=bar.raw_payload,
            ingestion_run_id=run.id,
        )
        self.session.add(record)
        self.session.flush()
        if current is not None:
            self.record_issue(
                listing_id=listing.id,
                observation_date=bar.observation_date,
                issue_type="PRICE_CORRECTION",
                detail=f"provider payload changed from revision {current.revision}",
                run=run,
            )
        self.resolve_issue(
            listing_id=listing.id,
            observation_date=bar.observation_date,
            issue_type="MISSING_EXPECTED_PRICE",
        )
        return record, True

    def _latest_price(
        self, listing_id: UUID, observation_date: date
    ) -> PriceObservationModel | None:
        return self.session.scalar(
            select(PriceObservationModel)
            .where(
                PriceObservationModel.listing_id == listing_id,
                PriceObservationModel.observation_date == observation_date,
            )
            .order_by(PriceObservationModel.revision.desc())
            .limit(1)
        )

    def list_prices(
        self, listing_id: UUID, *, date_from: date, date_to: date
    ) -> list[PriceObservationModel]:
        self.get_listing(listing_id)
        records = self.session.scalars(
            select(PriceObservationModel)
            .where(
                PriceObservationModel.listing_id == listing_id,
                PriceObservationModel.observation_date >= date_from,
                PriceObservationModel.observation_date <= date_to,
            )
            .order_by(
                PriceObservationModel.observation_date,
                PriceObservationModel.revision,
            )
        )
        current: dict[date, PriceObservationModel] = {}
        for record in records:
            current[record.observation_date] = record
        return list(current.values())

    def latest_price_on_or_before(
        self, listing_id: UUID, valuation_date: date
    ) -> PriceObservationModel | None:
        records = self.session.scalars(
            select(PriceObservationModel)
            .where(
                PriceObservationModel.listing_id == listing_id,
                PriceObservationModel.observation_date <= valuation_date,
            )
            .order_by(
                PriceObservationModel.observation_date.desc(),
                PriceObservationModel.revision.desc(),
            )
        )
        return next(iter(records), None)

    def latest_price_before(
        self, listing_id: UUID, observation_date: date
    ) -> PriceObservationModel | None:
        return self.session.scalar(
            select(PriceObservationModel)
            .where(
                PriceObservationModel.listing_id == listing_id,
                PriceObservationModel.observation_date < observation_date,
            )
            .order_by(
                PriceObservationModel.observation_date.desc(),
                PriceObservationModel.revision.desc(),
            )
            .limit(1)
        )

    def store_session(
        self,
        *,
        provider: str,
        exchange_code: str,
        exchange_mic: str,
        timezone: str,
        definition: SessionInput,
        source_checksum: str,
        retrieved_at: datetime,
        run: IngestionRunModel,
    ) -> tuple[ExchangeSessionModel, bool]:
        current = self.latest_session(exchange_code, definition.session_date)
        identity = (
            definition.status,
            definition.holiday_name,
            definition.close_time,
            source_checksum,
        )
        if current is not None and identity == (
            current.status,
            current.holiday_name,
            current.close_time,
            current.source_checksum,
        ):
            return current, False
        record = ExchangeSessionModel(
            provider=provider,
            exchange_code=exchange_code,
            exchange_mic=exchange_mic,
            session_date=definition.session_date,
            status=definition.status,
            holiday_name=definition.holiday_name,
            close_time=definition.close_time,
            timezone=timezone,
            source_checksum=source_checksum,
            revision=current.revision + 1 if current else 1,
            supersedes_id=current.id if current else None,
            retrieved_at=retrieved_at,
            ingestion_run_id=run.id,
        )
        self.session.add(record)
        self.session.flush()
        return record, True

    def latest_session(self, exchange_code: str, session_date: date) -> ExchangeSessionModel | None:
        return self.session.scalar(
            select(ExchangeSessionModel)
            .where(
                ExchangeSessionModel.exchange_code == exchange_code,
                ExchangeSessionModel.session_date == session_date,
            )
            .order_by(ExchangeSessionModel.revision.desc())
            .limit(1)
        )

    def list_sessions(
        self, exchange_code: str, *, date_from: date, date_to: date
    ) -> list[ExchangeSessionModel]:
        records = self.session.scalars(
            select(ExchangeSessionModel)
            .where(
                ExchangeSessionModel.exchange_code == exchange_code,
                ExchangeSessionModel.session_date >= date_from,
                ExchangeSessionModel.session_date <= date_to,
            )
            .order_by(ExchangeSessionModel.session_date, ExchangeSessionModel.revision)
        )
        current: dict[date, ExchangeSessionModel] = {}
        for record in records:
            current[record.session_date] = record
        return list(current.values())

    def store_fx_rate(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        provider_symbol: str,
        bar: PriceBarInput,
        run: IngestionRunModel,
    ) -> tuple[FxRateObservationModel, bool]:
        raw_rate = bar.close
        rate_to_base = Decimal("1") / raw_rate
        current = self._latest_fx(base_currency, quote_currency, bar.observation_date)
        if current is not None and current.source_checksum == bar.source_checksum:
            return current, False
        record = FxRateObservationModel(
            provider="EODHD",
            provider_symbol=provider_symbol,
            base_currency=base_currency,
            quote_currency=quote_currency,
            observation_date=bar.observation_date,
            raw_rate=raw_rate,
            rate_to_base=rate_to_base.quantize(Decimal("0.000000000001")),
            inverted=True,
            revision=current.revision + 1 if current else 1,
            supersedes_id=current.id if current else None,
            retrieved_at=bar.retrieved_at,
            source_checksum=bar.source_checksum,
            raw_payload=bar.raw_payload,
            ingestion_run_id=run.id,
        )
        self.session.add(record)
        self.session.flush()
        return record, True

    def _latest_fx(
        self, base_currency: str, quote_currency: str, observation_date: date
    ) -> FxRateObservationModel | None:
        return self.session.scalar(
            select(FxRateObservationModel)
            .where(
                FxRateObservationModel.base_currency == base_currency,
                FxRateObservationModel.quote_currency == quote_currency,
                FxRateObservationModel.observation_date == observation_date,
            )
            .order_by(FxRateObservationModel.revision.desc())
            .limit(1)
        )

    def latest_fx_on_or_before(
        self, base_currency: str, quote_currency: str, valuation_date: date
    ) -> FxRateObservationModel | None:
        return self.session.scalar(
            select(FxRateObservationModel)
            .where(
                FxRateObservationModel.base_currency == base_currency,
                FxRateObservationModel.quote_currency == quote_currency,
                FxRateObservationModel.observation_date <= valuation_date,
            )
            .order_by(
                FxRateObservationModel.observation_date.desc(),
                FxRateObservationModel.revision.desc(),
            )
            .limit(1)
        )

    def record_issue(
        self,
        *,
        listing_id: UUID | None,
        observation_date: date,
        issue_type: str,
        detail: str,
        run: IngestionRunModel | None,
    ) -> DataQualityIssueModel:
        existing = self.session.scalar(
            select(DataQualityIssueModel).where(
                DataQualityIssueModel.listing_id == listing_id,
                DataQualityIssueModel.observation_date == observation_date,
                DataQualityIssueModel.issue_type == issue_type,
            )
        )
        if existing is not None:
            return existing
        issue = DataQualityIssueModel(
            listing_id=listing_id,
            observation_date=observation_date,
            issue_type=issue_type,
            detail=detail,
            ingestion_run_id=run.id if run else None,
        )
        self.session.add(issue)
        self.session.flush()
        return issue

    def resolve_issue(self, *, listing_id: UUID, observation_date: date, issue_type: str) -> None:
        issue = self.session.scalar(
            select(DataQualityIssueModel).where(
                DataQualityIssueModel.listing_id == listing_id,
                DataQualityIssueModel.observation_date == observation_date,
                DataQualityIssueModel.issue_type == issue_type,
                DataQualityIssueModel.status == "OPEN",
            )
        )
        if issue is not None:
            issue.status = "RESOLVED"
            issue.resolved_at = datetime.now(UTC)

    def list_issues(self, *, status: str = "OPEN") -> list[DataQualityIssueModel]:
        return list(
            self.session.scalars(
                select(DataQualityIssueModel)
                .where(DataQualityIssueModel.status == status)
                .order_by(DataQualityIssueModel.detected_at)
            )
        )

    def get_listing(self, listing_id: UUID) -> ListingModel:
        listing = self.session.get(ListingModel, listing_id)
        if listing is None:
            raise RecordNotFoundError(f"listing {listing_id} was not found")
        return listing

    def active_primary_listings(self) -> list[ListingModel]:
        return list(
            self.session.scalars(
                select(ListingModel)
                .where(ListingModel.active.is_(True), ListingModel.is_primary.is_(True))
                .order_by(ListingModel.id)
            )
        )

    def primary_listing(self, asset_id: UUID) -> ListingModel:
        listing = self.session.scalar(
            select(ListingModel).where(
                ListingModel.asset_id == asset_id,
                ListingModel.is_primary.is_(True),
                ListingModel.active.is_(True),
            )
        )
        if listing is None:
            raise RecordNotFoundError(f"asset {asset_id} has no active primary listing")
        return listing

    def transactions_through(self, portfolio_id: UUID, cutoff: datetime) -> list[TransactionModel]:
        return list(
            self.session.scalars(
                select(TransactionModel)
                .where(
                    TransactionModel.portfolio_id == portfolio_id,
                    TransactionModel.executed_at <= cutoff,
                )
                .order_by(TransactionModel.executed_at, TransactionModel.created_at)
            )
        )

    def portfolios(self) -> list[PortfolioModel]:
        return list(self.session.scalars(select(PortfolioModel).order_by(PortfolioModel.id)))

    def find_snapshot(
        self, portfolio_id: UUID, valuation_date: date, input_fingerprint: str
    ) -> PortfolioSnapshotModel | None:
        return self.session.scalar(
            select(PortfolioSnapshotModel).where(
                PortfolioSnapshotModel.portfolio_id == portfolio_id,
                PortfolioSnapshotModel.valuation_date == valuation_date,
                PortfolioSnapshotModel.input_fingerprint == input_fingerprint,
            )
        )

    def latest_snapshot(
        self, portfolio_id: UUID, valuation_date: date
    ) -> PortfolioSnapshotModel | None:
        return self.session.scalar(
            select(PortfolioSnapshotModel)
            .where(
                PortfolioSnapshotModel.portfolio_id == portfolio_id,
                PortfolioSnapshotModel.valuation_date == valuation_date,
            )
            .order_by(PortfolioSnapshotModel.revision.desc())
            .limit(1)
        )

    def add_snapshot(
        self,
        snapshot: PortfolioSnapshotModel,
        positions: Iterable[SnapshotPositionModel],
    ) -> PortfolioSnapshotModel:
        self.session.add(snapshot)
        self.session.flush()
        for position in positions:
            position.snapshot_id = snapshot.id
            self.session.add(position)
        self.session.flush()
        return snapshot

    def list_snapshots(self, portfolio_id: UUID) -> list[PortfolioSnapshotModel]:
        records = self.session.scalars(
            select(PortfolioSnapshotModel)
            .where(PortfolioSnapshotModel.portfolio_id == portfolio_id)
            .order_by(
                PortfolioSnapshotModel.valuation_date,
                PortfolioSnapshotModel.revision,
            )
        )
        current: dict[date, PortfolioSnapshotModel] = {}
        for record in records:
            current[record.valuation_date] = record
        if not current and self.session.get(PortfolioModel, portfolio_id) is None:
            raise RecordNotFoundError(f"portfolio {portfolio_id} was not found")
        return list(current.values())

    def snapshot_positions(self, snapshot_id: UUID) -> list[SnapshotPositionModel]:
        return list(
            self.session.scalars(
                select(SnapshotPositionModel)
                .where(SnapshotPositionModel.snapshot_id == snapshot_id)
                .order_by(SnapshotPositionModel.asset_id)
            )
        )
