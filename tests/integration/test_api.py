from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient


def create_portfolio(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/portfolios", json={"name": "Initial experiment"})
    assert response.status_code == 201
    return response.json()


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
    return response.json()


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


def test_missing_resources_return_not_found(client: TestClient) -> None:
    missing_id = uuid4()
    assert client.get(f"/api/v1/portfolios/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/assets/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/portfolios/{missing_id}/transactions/{uuid4()}").status_code == 404
