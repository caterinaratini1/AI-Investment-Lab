"""Portfolio aggregate and all authoritative accounting calculations."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from uuid import UUID, uuid4

from ai_investment_lab.domain.decimal_utils import (
    MONEY_QUANTUM,
    ONE,
    PRICE_QUANTUM,
    ZERO,
    money,
    rate,
    require_decimal,
    require_signed_decimal,
)
from ai_investment_lab.domain.errors import (
    InsufficientCashError,
    InvalidTradeError,
    MissingPriceError,
    PositionNotFoundError,
)
from ai_investment_lab.domain.models import (
    CostModel,
    MarketQuote,
    PortfolioValuation,
    Position,
    PositionValuation,
    TradeExecution,
    TradeRequest,
    TradeSide,
)


@dataclass(slots=True)
class Portfolio:
    id: UUID
    name: str
    base_currency: str
    starting_capital: Decimal
    cash_balance: Decimal
    realized_pnl: Decimal = Decimal("0.00")
    positions: dict[UUID, Position] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.base_currency = self.base_currency.upper()
        if len(self.base_currency) != 3 or not self.base_currency.isalpha():
            raise InvalidTradeError("base_currency must be a three-letter code")
        if not self.name.strip():
            raise InvalidTradeError("portfolio name cannot be blank")
        self.name = self.name.strip()
        self.starting_capital = require_decimal(
            self.starting_capital,
            name="starting_capital",
            quantum=MONEY_QUANTUM,
            positive=True,
        )
        self.cash_balance = require_decimal(
            self.cash_balance,
            name="cash_balance",
            quantum=MONEY_QUANTUM,
            positive=False,
        )
        self.realized_pnl = require_signed_decimal(
            self.realized_pnl,
            name="realized_pnl",
            quantum=MONEY_QUANTUM,
        )
        if any(asset_id != position.asset_id for asset_id, position in self.positions.items()):
            raise InvalidTradeError("position map keys must match position asset IDs")

    @classmethod
    def open(
        cls,
        *,
        name: str,
        starting_capital: Decimal = Decimal("10000.00"),
        base_currency: str = "EUR",
        portfolio_id: UUID | None = None,
    ) -> "Portfolio":
        capital = require_decimal(
            starting_capital,
            name="starting_capital",
            quantum=MONEY_QUANTUM,
            positive=True,
        )
        return cls(
            id=portfolio_id or uuid4(),
            name=name,
            base_currency=base_currency,
            starting_capital=capital,
            cash_balance=capital,
        )

    def execute(
        self,
        request: TradeRequest,
        *,
        costs: CostModel | None = None,
    ) -> TradeExecution:
        if request.portfolio_id != self.id:
            raise InvalidTradeError("trade portfolio_id does not match the portfolio")
        cost_model = costs or CostModel()
        direction = ONE + cost_model.slippage_rate
        if request.side is TradeSide.SELL:
            direction = ONE - cost_model.slippage_rate
        execution_price = (request.reference_price * direction).quantize(
            PRICE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
        gross_notional = money(
            request.quantity * execution_price * request.fx_rate_to_base,
        )
        if execution_price <= ZERO or gross_notional <= ZERO:
            raise InvalidTradeError("trade notional must remain positive after rounding")
        reference_notional = money(
            request.quantity * request.reference_price * request.fx_rate_to_base,
        )
        slippage_cost = abs(gross_notional - reference_notional)
        commission = max(
            cost_model.minimum_commission,
            money(gross_notional * cost_model.commission_rate),
        )
        fx_fee = ZERO
        if request.asset_currency != self.base_currency:
            fx_fee = money(gross_notional * cost_model.fx_fee_rate)

        if request.side is TradeSide.BUY:
            return self._buy(
                request=request,
                execution_price=execution_price,
                gross_notional=gross_notional,
                commission=commission,
                slippage_cost=slippage_cost,
                fx_fee=fx_fee,
            )
        return self._sell(
            request=request,
            execution_price=execution_price,
            gross_notional=gross_notional,
            commission=commission,
            slippage_cost=slippage_cost,
            fx_fee=fx_fee,
        )

    def _buy(
        self,
        *,
        request: TradeRequest,
        execution_price: Decimal,
        gross_notional: Decimal,
        commission: Decimal,
        slippage_cost: Decimal,
        fx_fee: Decimal,
    ) -> TradeExecution:
        total_debit = gross_notional + commission + fx_fee
        if total_debit > self.cash_balance:
            raise InsufficientCashError(
                f"trade requires {total_debit} {self.base_currency}, "
                f"but only {self.cash_balance} is available",
            )
        position = self.positions.get(request.asset_id)
        if position is None:
            position = Position(
                asset_id=request.asset_id,
                quantity=request.quantity,
                cost_basis=total_debit,
            )
            self.positions[request.asset_id] = position
        else:
            position.quantity += request.quantity
            position.cost_basis = money(position.cost_basis + total_debit)
        self.cash_balance = money(self.cash_balance - total_debit)
        return TradeExecution(
            id=uuid4(),
            portfolio_id=self.id,
            asset_id=request.asset_id,
            decision_id=request.decision_id,
            side=request.side,
            asset_currency=request.asset_currency,
            quantity=request.quantity,
            reference_price=request.reference_price,
            execution_price=execution_price,
            fx_rate_to_base=request.fx_rate_to_base,
            gross_notional=gross_notional,
            commission=commission,
            slippage_cost=slippage_cost,
            fx_fee=fx_fee,
            cash_delta=-total_debit,
            realized_pnl=money(ZERO),
            executed_at=request.executed_at,
        )

    def _sell(
        self,
        *,
        request: TradeRequest,
        execution_price: Decimal,
        gross_notional: Decimal,
        commission: Decimal,
        slippage_cost: Decimal,
        fx_fee: Decimal,
    ) -> TradeExecution:
        position = self.positions.get(request.asset_id)
        if position is None:
            raise PositionNotFoundError("cannot sell an asset with no open position")
        if request.quantity > position.quantity:
            raise PositionNotFoundError(
                f"cannot sell {request.quantity}; only {position.quantity} is held",
            )
        if request.quantity == position.quantity:
            removed_cost_basis = position.cost_basis
        else:
            removed_cost_basis = money(
                position.cost_basis * request.quantity / position.quantity,
            )
        net_proceeds = gross_notional - commission - fx_fee
        resulting_cash = money(self.cash_balance + net_proceeds)
        if resulting_cash < ZERO:
            raise InsufficientCashError(
                "sale costs exceed its proceeds and available cash",
            )
        realized_pnl = money(net_proceeds - removed_cost_basis)
        position.quantity -= request.quantity
        position.cost_basis = money(position.cost_basis - removed_cost_basis)
        position.realized_pnl = money(position.realized_pnl + realized_pnl)
        if position.quantity == ZERO:
            del self.positions[request.asset_id]
        self.cash_balance = resulting_cash
        self.realized_pnl = money(self.realized_pnl + realized_pnl)
        return TradeExecution(
            id=uuid4(),
            portfolio_id=self.id,
            asset_id=request.asset_id,
            decision_id=request.decision_id,
            side=request.side,
            asset_currency=request.asset_currency,
            quantity=request.quantity,
            reference_price=request.reference_price,
            execution_price=execution_price,
            fx_rate_to_base=request.fx_rate_to_base,
            gross_notional=gross_notional,
            commission=commission,
            slippage_cost=slippage_cost,
            fx_fee=fx_fee,
            cash_delta=net_proceeds,
            realized_pnl=realized_pnl,
            executed_at=request.executed_at,
        )

    def value(self, quotes: dict[UUID, MarketQuote]) -> PortfolioValuation:
        valuations: list[PositionValuation] = []
        for asset_id, position in sorted(self.positions.items(), key=lambda item: str(item[0])):
            quote = quotes.get(asset_id)
            if quote is None:
                raise MissingPriceError(f"missing quote for asset {asset_id}")
            if quote.asset_id != asset_id:
                raise MissingPriceError(f"quote identity does not match asset {asset_id}")
            market_value = money(position.quantity * quote.price * quote.fx_rate_to_base)
            unrealized_pnl = money(market_value - position.cost_basis)
            return_fraction = ZERO
            if position.cost_basis != ZERO:
                return_fraction = rate(unrealized_pnl / position.cost_basis)
            valuations.append(
                PositionValuation(
                    asset_id=asset_id,
                    quantity=position.quantity,
                    average_cost=position.average_cost,
                    cost_basis=position.cost_basis,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    return_fraction=return_fraction,
                    observed_at=quote.observed_at,
                ),
            )
        positions = tuple(valuations)
        market_value = money(sum((item.market_value for item in positions), ZERO))
        unrealized_pnl = money(sum((item.unrealized_pnl for item in positions), ZERO))
        total_value = money(self.cash_balance + market_value)
        total_return = rate(total_value / self.starting_capital - ONE)
        return PortfolioValuation(
            portfolio_id=self.id,
            cash_balance=self.cash_balance,
            market_value=market_value,
            total_value=total_value,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_return_fraction=total_return,
            positions=positions,
        )
