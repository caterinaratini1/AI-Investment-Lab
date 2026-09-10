"""Phase 1 portfolio, asset, and transaction endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ai_investment_lab.api.database import get_db_session
from ai_investment_lab.api.schemas import (
    AssetCreate,
    AssetResponse,
    HealthResponse,
    PortfolioCreate,
    PortfolioResponse,
    PositionResponse,
    ReadinessResponse,
    TradeCreate,
    TradeResultResponse,
    TransactionResponse,
)
from ai_investment_lab.db import PortfolioRepository, PositionModel, RecordNotFoundError
from ai_investment_lab.domain import (
    DomainError,
    InsufficientCashError,
    PositionNotFoundError,
    TradeRequest,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]


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
            )
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="the asset listing already exists or violates a database constraint",
        ) from error
    response.headers["Location"] = f"/api/v1/assets/{record.id}"
    return AssetResponse.model_validate(record)


@router.get("/assets/{asset_id}", response_model=AssetResponse, tags=["assets"])
def get_asset(asset_id: UUID, session: DbSession) -> AssetResponse:
    try:
        record = PortfolioRepository(session).get_asset(asset_id)
    except RecordNotFoundError as error:
        raise _not_found(error) from error
    return AssetResponse.model_validate(record)


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
