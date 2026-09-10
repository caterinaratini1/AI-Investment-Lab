"""Portfolio ledger and point-in-time market-data endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ai_investment_lab.api.database import get_db_session
from ai_investment_lab.api.providers import get_market_provider
from ai_investment_lab.api.schemas import (
    AssetCreate,
    AssetResponse,
    DataQualityIssueResponse,
    HealthResponse,
    InstrumentMatchResponse,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioSnapshotResponse,
    PositionResponse,
    PriceObservationResponse,
    ReadinessResponse,
    SnapshotPositionResponse,
    TradeCreate,
    TradeResultResponse,
    TransactionResponse,
)
from ai_investment_lab.data_providers import MarketDataProvider, ProviderError
from ai_investment_lab.db import PortfolioRepository, PositionModel, RecordNotFoundError
from ai_investment_lab.db.market_repository import MarketDataRepository
from ai_investment_lab.db.repository import AssetRecord
from ai_investment_lab.domain import (
    DomainError,
    InsufficientCashError,
    PositionNotFoundError,
    TradeRequest,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]
Provider = Annotated[MarketDataProvider, Depends(get_market_provider)]


def _position_response(position: PositionModel) -> PositionResponse:
    return PositionResponse(
        portfolio_id=position.portfolio_id,
        asset_id=position.asset_id,
        quantity=position.quantity,
        cost_basis=position.cost_basis,
        average_cost=position.cost_basis / position.quantity,
        realized_pnl=position.realized_pnl,
        opened_at=position.opened_at,
        updated_at=position.updated_at,
    )


def _not_found(error: RecordNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def _asset_response(record: AssetRecord) -> AssetResponse:
    return AssetResponse(
        id=record.asset.id,
        listing_id=record.listing.id,
        name=record.asset.name,
        ticker=record.listing.ticker,
        isin=record.asset.isin,
        exchange_mic=record.listing.exchange_mic,
        currency=record.listing.currency,
        asset_type=record.asset.asset_type,
        sector=record.asset.sector,
        provider=record.listing.provider,
        provider_symbol=record.listing.provider_symbol,
        provider_exchange_code=record.listing.provider_exchange_code,
        exchange_timezone=record.listing.exchange_timezone,
        created_at=record.asset.created_at,
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse, tags=["system"])
def readiness(session: DbSession) -> ReadinessResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database is unavailable",
        ) from error
    return ReadinessResponse()


@router.post(
    "/portfolios",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["portfolios"],
)
def create_portfolio(
    payload: PortfolioCreate,
    response: Response,
    session: DbSession,
) -> PortfolioResponse:
    repository = PortfolioRepository(session)
    try:
        with session.begin():
            record = repository.create_portfolio(
                name=payload.name,
                starting_capital=payload.starting_capital,
                base_currency=payload.base_currency,
            )
    except DomainError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    response.headers["Location"] = f"/api/v1/portfolios/{record.id}"
    return PortfolioResponse.model_validate(record)


@router.get(
    "/portfolios/{portfolio_id}",
    response_model=PortfolioResponse,
    tags=["portfolios"],
)
def get_portfolio(
    portfolio_id: UUID,
    session: DbSession,
) -> PortfolioResponse:
    try:
        record = PortfolioRepository(session).get_portfolio(portfolio_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return PortfolioResponse.model_validate(record)


@router.post(
    "/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["assets"],
)
def create_asset(
    payload: AssetCreate,
    response: Response,
    session: DbSession,
) -> AssetResponse:
    repository = PortfolioRepository(session)
    try:
        with session.begin():
            record = repository.create_asset(
                name=payload.name,
                ticker=payload.ticker,
                isin=payload.isin,
                exchange_mic=payload.exchange_mic,
                currency=payload.currency,
                asset_type=payload.asset_type.value,
                sector=payload.sector,
                provider_symbol=payload.provider_symbol,
                provider_exchange_code=payload.provider_exchange_code,
                exchange_timezone=payload.exchange_timezone,
            )
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="the asset listing already exists or violates a database constraint",
        ) from error
    response.headers["Location"] = f"/api/v1/assets/{record.id}"
    return _asset_response(record)


@router.get("/assets/{asset_id}", response_model=AssetResponse, tags=["assets"])
def get_asset(asset_id: UUID, session: DbSession) -> AssetResponse:
    try:
        record = PortfolioRepository(session).get_asset(asset_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return _asset_response(record)


@router.get(
    "/market-data/search",
    response_model=list[InstrumentMatchResponse],
    tags=["market data"],
)
def search_instruments(
    provider: Provider,
    q: str,
    exchange: str | None = None,
    instrument_type: str | None = None,
    limit: int = 20,
) -> list[InstrumentMatchResponse]:
    try:
        matches = provider.search(
            q,
            exchange=exchange,
            instrument_type=instrument_type,
            limit=limit,
        )
    except (ProviderError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    return [
        InstrumentMatchResponse(
            code=item.code,
            exchange_code=item.exchange_code,
            provider_symbol=item.provider_symbol,
            name=item.name,
            instrument_type=item.instrument_type,
            country=item.country,
            currency=item.currency,
            isin=item.isin,
            is_primary=item.is_primary,
        )
        for item in matches
    ]


@router.get(
    "/listings/{listing_id}/prices",
    response_model=list[PriceObservationResponse],
    tags=["market data"],
)
def list_prices(
    listing_id: UUID,
    session: DbSession,
    date_from: date,
    date_to: date,
) -> list[PriceObservationResponse]:
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must not be after date_to",
        )
    try:
        records = MarketDataRepository(session).list_prices(
            listing_id,
            date_from=date_from,
            date_to=date_to,
        )
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return [PriceObservationResponse.model_validate(record) for record in records]


@router.get(
    "/portfolios/{portfolio_id}/snapshots",
    response_model=list[PortfolioSnapshotResponse],
    tags=["portfolios"],
)
def list_snapshots(
    portfolio_id: UUID,
    session: DbSession,
) -> list[PortfolioSnapshotResponse]:
    repository = MarketDataRepository(session)
    try:
        records = repository.list_snapshots(portfolio_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return [
        PortfolioSnapshotResponse(
            id=record.id,
            portfolio_id=record.portfolio_id,
            valuation_date=record.valuation_date,
            cash_balance=record.cash_balance,
            positions_value=record.positions_value,
            total_value=record.total_value,
            realized_pnl=record.realized_pnl,
            unrealized_pnl=record.unrealized_pnl,
            total_return=record.total_return,
            calculation_version=record.calculation_version,
            input_fingerprint=record.input_fingerprint,
            revision=record.revision,
            supersedes_id=record.supersedes_id,
            created_at=record.created_at,
            positions=[
                SnapshotPositionResponse.model_validate(position)
                for position in repository.snapshot_positions(record.id)
            ],
        )
        for record in records
    ]


@router.get(
    "/market-data/issues",
    response_model=list[DataQualityIssueResponse],
    tags=["market data"],
)
def list_market_data_issues(
    session: DbSession,
    issue_status: str = "OPEN",
) -> list[DataQualityIssueResponse]:
    if issue_status not in {"OPEN", "RESOLVED"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="issue_status must be OPEN or RESOLVED",
        )
    return [
        DataQualityIssueResponse.model_validate(record)
        for record in MarketDataRepository(session).list_issues(status=issue_status)
    ]


@router.get(
    "/portfolios/{portfolio_id}/positions",
    response_model=list[PositionResponse],
    tags=["portfolios"],
)
def list_positions(
    portfolio_id: UUID,
    session: DbSession,
) -> list[PositionResponse]:
    try:
        records = PortfolioRepository(session).list_positions(portfolio_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return [_position_response(record) for record in records]


@router.get(
    "/portfolios/{portfolio_id}/transactions",
    response_model=list[TransactionResponse],
    tags=["portfolios"],
)
def list_transactions(
    portfolio_id: UUID,
    session: DbSession,
) -> list[TransactionResponse]:
    try:
        records = PortfolioRepository(session).list_transactions(portfolio_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return [TransactionResponse.model_validate(record) for record in records]


@router.get(
    "/portfolios/{portfolio_id}/transactions/{transaction_id}",
    response_model=TransactionResponse,
    tags=["portfolios"],
)
def get_transaction(
    portfolio_id: UUID,
    transaction_id: UUID,
    session: DbSession,
) -> TransactionResponse:
    try:
        record = PortfolioRepository(session).get_transaction(portfolio_id, transaction_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return TransactionResponse.model_validate(record)


@router.post(
    "/portfolios/{portfolio_id}/transactions",
    response_model=TradeResultResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["portfolios"],
)
def execute_trade(
    portfolio_id: UUID,
    payload: TradeCreate,
    response: Response,
    session: DbSession,
) -> TradeResultResponse:
    repository = PortfolioRepository(session)
    try:
        with session.begin():
            asset = repository.get_asset(payload.asset_id)
            request = TradeRequest(
                portfolio_id=portfolio_id,
                asset_id=payload.asset_id,
                asset_currency=asset.currency,
                side=payload.side,
                quantity=payload.quantity,
                reference_price=payload.reference_price,
                fx_rate_to_base=payload.fx_rate_to_base,
                executed_at=payload.executed_at,
                decision_id=payload.decision_id,
            )
            transaction, position = repository.execute_trade(request)
            portfolio = repository.get_portfolio(portfolio_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    except (InsufficientCashError, PositionNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (DomainError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    response.headers["Location"] = (
        f"/api/v1/portfolios/{portfolio_id}/transactions/{transaction.id}"
    )
    return TradeResultResponse(
        transaction=TransactionResponse.model_validate(transaction),
        position=_position_response(position) if position else None,
        cash_balance=portfolio.cash_balance,
        portfolio_realized_pnl=portfolio.realized_pnl,
    )
