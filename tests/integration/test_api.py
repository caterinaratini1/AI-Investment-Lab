from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_investment_lab.api.providers import get_market_provider
from ai_investment_lab.data_providers import InstrumentMatch, ProviderRequestError
from ai_investment_lab.db import MarketDataRepository, PortfolioRepository
from ai_investment_lab.worker.service import SnapshotService


def create_portfolio(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/portfolios", json={"name": "Initial experiment"})
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def create_asset(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/assets",
        json={
            "name": "Example Corp",
            "ticker": "exam",
            "isin": "IE00B4L5Y983",
            "exchange_mic": "XAMS",
            "currency": "EUR",
            "asset_type": "PUBLIC_EQUITY",
            "sector": "Industrials",
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ready").json() == {"status": "ready"}


def test_portfolio_asset_buy_and_sell_workflow(client: TestClient) -> None:
    portfolio = create_portfolio(client)
    asset = create_asset(client)

    buy = client.post(
        f"/api/v1/portfolios/{portfolio['id']}/transactions",
        json={
            "asset_id": asset["id"],
            "side": "BUY",
            "quantity": "10",
            "reference_price": "100",
            "fx_rate_to_base": "1",
            "executed_at": "2026-09-11T07:00:00Z",
        },
    )
    assert buy.status_code == 201, buy.text
    buy_result = buy.json()
    persisted_buy = client.get(buy.headers["location"])
    assert persisted_buy.status_code == 200
    assert persisted_buy.json()["id"] == buy_result["transaction"]["id"]
    assert Decimal(str(buy_result["cash_balance"])) == Decimal("8998.50")
    assert Decimal(str(buy_result["position"]["quantity"])) == Decimal("10")
    assert Decimal(str(buy_result["position"]["average_cost"])) == Decimal("100.15")

    sell = client.post(
        f"/api/v1/portfolios/{portfolio['id']}/transactions",
        json={
            "asset_id": asset["id"],
            "side": "SELL",
            "quantity": "4",
            "reference_price": "110",
            "fx_rate_to_base": "1",
            "executed_at": "2026-09-14T07:00:00Z",
        },
    )
    assert sell.status_code == 201, sell.text
    sell_result = sell.json()
    assert Decimal(str(sell_result["position"]["quantity"])) == Decimal("6")
    assert Decimal(str(sell_result["transaction"]["realized_pnl"])) == Decimal("38.18")

    positions = client.get(f"/api/v1/portfolios/{portfolio['id']}/positions")
    transactions = client.get(f"/api/v1/portfolios/{portfolio['id']}/transactions")
    assert positions.status_code == 200
    assert len(positions.json()) == 1
    assert transactions.status_code == 200
    assert [item["side"] for item in transactions.json()] == ["BUY", "SELL"]


def test_api_rejects_oversell_and_preserves_position(client: TestClient) -> None:
    portfolio = create_portfolio(client)
    asset = create_asset(client)
    endpoint = f"/api/v1/portfolios/{portfolio['id']}/transactions"
    client.post(
        endpoint,
        json={
            "asset_id": asset["id"],
            "side": "BUY",
            "quantity": "1",
            "reference_price": "100",
            "executed_at": "2026-09-11T07:00:00Z",
        },
    )

    response = client.post(
        endpoint,
        json={
            "asset_id": asset["id"],
            "side": "SELL",
            "quantity": "2",
            "reference_price": "110",
            "executed_at": "2026-09-14T07:00:00Z",
        },
    )

    assert response.status_code == 409
    positions = client.get(f"/api/v1/portfolios/{portfolio['id']}/positions").json()
    assert Decimal(str(positions[0]["quantity"])) == Decimal("1")


def test_api_validates_timestamp_and_duplicate_asset(client: TestClient) -> None:
    create_asset(client)
    duplicate = client.post(
        "/api/v1/assets",
        json={
            "name": "Duplicate Corp",
            "ticker": "EXAM",
            "isin": "IE00B4L5Y983",
            "exchange_mic": "XAMS",
            "currency": "EUR",
            "asset_type": "PUBLIC_EQUITY",
        },
    )
    assert duplicate.status_code == 409

    portfolio = create_portfolio(client)
    response = client.post(
        f"/api/v1/portfolios/{portfolio['id']}/transactions",
        json={
            "asset_id": str(uuid4()),
            "side": "BUY",
            "quantity": "1",
            "reference_price": "100",
            "executed_at": "2026-09-11T07:00:00",
        },
    )
    assert response.status_code == 422


def test_api_rejects_incomplete_or_inconsistent_provider_identity(client: TestClient) -> None:
    base_asset = {
        "name": "iShares Core MSCI World",
        "ticker": "IWDA",
        "isin": "IE00B4L5Y983",
        "exchange_mic": "XAMS",
        "currency": "EUR",
        "asset_type": "UCITS_ETF",
    }

    incomplete = client.post(
        "/api/v1/assets",
        json={**base_asset, "provider_symbol": "IWDA.AS"},
    )
    inconsistent = client.post(
        "/api/v1/assets",
        json={
            **base_asset,
            "provider_symbol": "IWDA.US",
            "provider_exchange_code": "AS",
        },
    )

    assert incomplete.status_code == 422
    assert inconsistent.status_code == 422


def test_missing_resources_return_not_found(client: TestClient) -> None:
    missing_id = uuid4()
    assert client.get(f"/api/v1/portfolios/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/assets/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/portfolios/{missing_id}/transactions/{uuid4()}").status_code == 404


class SearchProvider:
    name = "EODHD"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def search(
        self,
        query: str,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[InstrumentMatch]:
        del query, exchange, instrument_type, limit
        if self.fail:
            raise ProviderRequestError("provider unavailable")
        return [
            InstrumentMatch(
                code="IWDA",
                exchange_code="AS",
                name="iShares Core MSCI World",
                instrument_type="ETF",
                country="Netherlands",
                currency="EUR",
                isin="IE00B4L5Y983",
                is_primary=True,
            )
        ]

    def historical_prices(self, *args: object, **kwargs: object) -> Sequence[object]:
        del args, kwargs
        return []

    def exchange_calendar(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("not used")


def test_market_search_exposes_normalized_matches_and_safe_failures(client: TestClient) -> None:
    assert client.get("/api/v1/market-data/search", params={"q": "IWDA"}).status_code == 503
    application = cast(FastAPI, client.app)
    application.dependency_overrides[get_market_provider] = lambda: SearchProvider()
    response = client.get(
        "/api/v1/market-data/search",
        params={"q": "IE00B4L5Y983", "exchange": "AS", "instrument_type": "etf"},
    )
    assert response.status_code == 200
    assert response.json()[0]["provider_symbol"] == "IWDA.AS"

    application.dependency_overrides[get_market_provider] = lambda: SearchProvider(fail=True)
    failed = client.get("/api/v1/market-data/search", params={"q": "IWDA"})
    assert failed.status_code == 502
    assert failed.json()["detail"] == "provider unavailable"


def test_market_data_query_validation_and_cash_snapshot_api(
    client: TestClient,
    engine: Engine,
) -> None:
    portfolio = create_portfolio(client)
    asset_response = client.post(
        "/api/v1/assets",
        json={
            "name": "iShares Core MSCI World",
            "ticker": "IWDA",
            "isin": "IE00B4L5Y983",
            "exchange_mic": "XAMS",
            "currency": "EUR",
            "asset_type": "UCITS_ETF",
            "provider_symbol": "iwda.as",
            "provider_exchange_code": "as",
            "exchange_timezone": "Europe/Amsterdam",
        },
    )
    assert asset_response.status_code == 201
    asset = asset_response.json()
    assert asset["provider_symbol"] == "IWDA.AS"

    bad_range = client.get(
        f"/api/v1/listings/{asset['listing_id']}/prices",
        params={"date_from": "2026-09-11", "date_to": "2026-09-10"},
    )
    assert bad_range.status_code == 422
    missing_listing = client.get(
        f"/api/v1/listings/{uuid4()}/prices",
        params={"date_from": "2026-09-10", "date_to": "2026-09-11"},
    )
    assert missing_listing.status_code == 404
    assert client.get("/api/v1/market-data/issues?issue_status=BAD").status_code == 422

    with Session(engine, expire_on_commit=False) as session:
        repository = MarketDataRepository(session)
        portfolio_record = PortfolioRepository(session).get_portfolio(UUID(str(portfolio["id"])))
        run, _ = repository.start_run(
            job_type="DAILY_SNAPSHOT",
            idempotency_key="api-cash-snapshot",
        )
        SnapshotService(repository).snapshot_portfolio(
            portfolio_record,
            valuation_date=date(2026, 9, 10),
            run=run,
        )
        repository.finish_run(run)
        session.commit()

    snapshots = client.get(f"/api/v1/portfolios/{portfolio['id']}/snapshots")
    assert snapshots.status_code == 200
    assert Decimal(str(snapshots.json()[0]["total_value"])) == Decimal("10000.00")
    assert snapshots.json()[0]["positions"] == []
    assert client.get(f"/api/v1/portfolios/{uuid4()}/snapshots").status_code == 404
