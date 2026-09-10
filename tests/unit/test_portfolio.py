from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from ai_investment_lab.domain import (
    CostModel,
    InsufficientCashError,
    InvalidTradeError,
    MarketQuote,
    MissingPriceError,
    Portfolio,
    PositionNotFoundError,
    TradeRequest,
    TradeSide,
)

NOW = datetime(2026, 9, 10, 10, 0, tzinfo=UTC)


def request(
    portfolio_id: UUID,
    asset_id: UUID,
    side: TradeSide,
    quantity: str,
    price: str,
    *,
    currency: str = "EUR",
    fx_rate: str = "1",
) -> TradeRequest:
    return TradeRequest(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        asset_currency=currency,
        side=side,
        quantity=Decimal(quantity),
        reference_price=Decimal(price),
        fx_rate_to_base=Decimal(fx_rate),
        executed_at=NOW,
    )


def test_open_portfolio_starts_entirely_in_cash() -> None:
    portfolio = Portfolio.open(name="Initial experiment")

    assert portfolio.starting_capital == Decimal("10000.00")
    assert portfolio.cash_balance == Decimal("10000.00")
    assert portfolio.realized_pnl == Decimal("0.00")
    assert portfolio.positions == {}


def test_buy_applies_slippage_commission_cash_and_cost_basis() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()

    execution = portfolio.execute(
        request(portfolio.id, asset_id, TradeSide.BUY, "10", "100"),
    )

    assert execution.execution_price == Decimal("100.05000000")
    assert execution.gross_notional == Decimal("1000.50")
    assert execution.slippage_cost == Decimal("0.50")
    assert execution.commission == Decimal("1.00")
    assert execution.fx_fee == Decimal("0")
    assert execution.cash_delta == Decimal("-1001.50")
    assert execution.total_explicit_costs == Decimal("1.50")
    assert portfolio.cash_balance == Decimal("8998.50")
    assert portfolio.positions[asset_id].quantity == Decimal("10.00000000")
    assert portfolio.positions[asset_id].cost_basis == Decimal("1001.50")
    assert portfolio.positions[asset_id].average_cost == Decimal("100.15")


def test_multiple_buys_calculate_weighted_average_cost() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "10", "100"))
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "5", "120"))

    position = portfolio.positions[asset_id]
    assert position.quantity == Decimal("15.00000000")
    assert position.cost_basis == Decimal("1602.80")
    assert position.average_cost == Decimal("106.8533333333333333333333333")
    assert portfolio.cash_balance == Decimal("8397.20")


def test_fractional_share_buy_is_accounted_exactly() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()

    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "0.125", "80"))

    position = portfolio.positions[asset_id]
    assert position.quantity == Decimal("0.12500000")
    assert position.cost_basis == Decimal("11.00")
    assert position.average_cost == Decimal("88")


def test_partial_sell_preserves_average_cost_and_realizes_pnl() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "10", "100"))
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "5", "120"))

    execution = portfolio.execute(
        request(portfolio.id, asset_id, TradeSide.SELL, "6", "130"),
    )

    position = portfolio.positions[asset_id]
    assert execution.execution_price == Decimal("129.93500000")
    assert execution.gross_notional == Decimal("779.61")
    assert execution.commission == Decimal("1.00")
    assert execution.slippage_cost == Decimal("0.39")
    assert execution.cash_delta == Decimal("778.61")
    assert execution.realized_pnl == Decimal("137.49")
    assert position.quantity == Decimal("9.00000000")
    assert position.cost_basis == Decimal("961.68")
    assert position.average_cost == Decimal("106.8533333333333333333333333")
    assert portfolio.cash_balance == Decimal("9175.81")
    assert portfolio.realized_pnl == Decimal("137.49")


def test_full_sell_closes_position_and_keeps_realized_pnl() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "10", "100"))

    execution = portfolio.execute(
        request(portfolio.id, asset_id, TradeSide.SELL, "10", "90"),
    )

    assert execution.realized_pnl == Decimal("-102.95")
    assert portfolio.realized_pnl == Decimal("-102.95")
    assert portfolio.cash_balance == Decimal("9897.05")
    assert asset_id not in portfolio.positions


def test_foreign_currency_buy_charges_fx_fee() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()

    execution = portfolio.execute(
        request(
            portfolio.id,
            asset_id,
            TradeSide.BUY,
            "10",
            "100",
            currency="USD",
            fx_rate="0.9",
        ),
    )

    assert execution.gross_notional == Decimal("900.45")
    assert execution.slippage_cost == Decimal("0.45")
    assert execution.commission == Decimal("1.00")
    assert execution.fx_fee == Decimal("1.80")
    assert execution.cash_delta == Decimal("-903.25")
    assert portfolio.positions[asset_id].cost_basis == Decimal("903.25")


def test_percentage_commission_applies_above_minimum() -> None:
    portfolio = Portfolio.open(name="Larger test", starting_capital=Decimal("20000.00"))
    asset_id = uuid4()

    execution = portfolio.execute(
        request(portfolio.id, asset_id, TradeSide.BUY, "100", "100"),
    )

    assert execution.gross_notional == Decimal("10005.00")
    assert execution.commission == Decimal("10.00")


def test_buy_rejects_insufficient_cash_without_mutation() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()

    with pytest.raises(InsufficientCashError, match=r"only 10000\.00 is available"):
        portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "100", "100"))

    assert portfolio.cash_balance == Decimal("10000.00")
    assert portfolio.positions == {}


def test_sell_rejects_missing_and_excess_positions() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()

    with pytest.raises(PositionNotFoundError, match="no open position"):
        portfolio.execute(request(portfolio.id, asset_id, TradeSide.SELL, "1", "100"))

    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "1", "100"))
    with pytest.raises(PositionNotFoundError, match=r"only 1\.00000000 is held"):
        portfolio.execute(request(portfolio.id, asset_id, TradeSide.SELL, "2", "100"))


def test_sell_rejects_negative_net_cash_without_mutating_position() -> None:
    portfolio = Portfolio.open(name="Small account", starting_capital=Decimal("1.50"))
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "1", "0.50"))

    with pytest.raises(InsufficientCashError, match="sale costs exceed"):
        portfolio.execute(request(portfolio.id, asset_id, TradeSide.SELL, "1", "0.50"))

    assert portfolio.cash_balance == Decimal("0.00")
    assert portfolio.positions[asset_id].quantity == Decimal("1.00000000")


def test_valuation_calculates_market_value_and_unrealized_pnl() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "10", "100"))

    valuation = portfolio.value(
        {
            asset_id: MarketQuote(
                asset_id=asset_id,
                price=Decimal("110"),
                fx_rate_to_base=Decimal("1"),
                observed_at=NOW,
            ),
        },
    )

    assert valuation.market_value == Decimal("1100.00")
    assert valuation.cash_balance == Decimal("8998.50")
    assert valuation.total_value == Decimal("10098.50")
    assert valuation.unrealized_pnl == Decimal("98.50")
    assert valuation.total_return_fraction == Decimal("0.009850000000")
    assert valuation.positions[0].return_fraction == Decimal("0.098352471293")


def test_valuation_requires_every_open_position_price() -> None:
    portfolio = Portfolio.open(name="Initial experiment")
    asset_id = uuid4()
    portfolio.execute(request(portfolio.id, asset_id, TradeSide.BUY, "1", "100"))

    with pytest.raises(MissingPriceError, match=str(asset_id)):
        portfolio.value({})

    with pytest.raises(MissingPriceError, match="quote identity"):
        portfolio.value(
            {
                asset_id: MarketQuote(
                    asset_id=uuid4(),
                    price=Decimal("100"),
                    fx_rate_to_base=Decimal("1"),
                    observed_at=NOW,
                ),
            },
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("quantity", Decimal("0"), "quantity must be greater than zero"),
        ("quantity", Decimal("1.000000001"), "quantity supports at most 8"),
        ("reference_price", Decimal("0"), "reference_price must be greater than zero"),
        ("fx_rate_to_base", Decimal("0"), "fx_rate_to_base must be greater than zero"),
    ],
)
def test_trade_request_rejects_invalid_numbers(
    field: str,
    value: Decimal,
    message: str,
) -> None:
    values = {
        "portfolio_id": uuid4(),
        "asset_id": uuid4(),
        "asset_currency": "EUR",
        "side": TradeSide.BUY,
        "quantity": Decimal("1"),
        "reference_price": Decimal("100"),
        "fx_rate_to_base": Decimal("1"),
        "executed_at": NOW,
    }
    values[field] = value

    with pytest.raises(InvalidTradeError, match=message):
        TradeRequest(**values)  # type: ignore[arg-type]


def test_trade_request_rejects_naive_timestamp() -> None:
    with pytest.raises(InvalidTradeError, match="include a timezone"):
        TradeRequest(
            portfolio_id=uuid4(),
            asset_id=uuid4(),
            asset_currency="EUR",
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            reference_price=Decimal("100"),
            fx_rate_to_base=Decimal("1"),
            executed_at=datetime(2026, 9, 10, 10, 0),
        )


def test_trade_rejects_notional_that_rounds_to_zero() -> None:
    portfolio = Portfolio.open(name="Initial experiment")

    with pytest.raises(InvalidTradeError, match="remain positive"):
        portfolio.execute(request(portfolio.id, uuid4(), TradeSide.BUY, "0.00000001", "0.01"))


def test_cost_model_rejects_impossible_rate() -> None:
    with pytest.raises(InvalidTradeError, match="cannot exceed 1"):
        CostModel(slippage_rate=Decimal("1.1"))

    with pytest.raises(InvalidTradeError, match="less than 1"):
        CostModel(slippage_rate=Decimal("1"))
