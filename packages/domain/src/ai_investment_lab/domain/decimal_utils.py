"""Fixed-precision decimal rules shared by all accounting operations."""

from decimal import ROUND_HALF_EVEN, Decimal

from ai_investment_lab.domain.errors import InvalidTradeError

MONEY_QUANTUM = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.00000001")
QUANTITY_QUANTUM = Decimal("0.00000001")
RATE_QUANTUM = Decimal("0.000000000001")
ZERO = Decimal("0")
ONE = Decimal("1")


def require_decimal(value: Decimal, *, name: str, quantum: Decimal, positive: bool) -> Decimal:
    """Validate finiteness, sign, and precision without silently changing an input."""
    if not value.is_finite():
        raise InvalidTradeError(f"{name} must be finite")
    if positive and value <= ZERO:
        raise InvalidTradeError(f"{name} must be greater than zero")
    if not positive and value < ZERO:
        raise InvalidTradeError(f"{name} cannot be negative")
    normalized = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if normalized != value:
        exponent = quantum.as_tuple().exponent
        if not isinstance(exponent, int):
            raise InvalidTradeError(f"{name} has an invalid precision")
        decimal_places = -exponent
        raise InvalidTradeError(f"{name} supports at most {decimal_places} decimal places")
    return normalized


def require_signed_decimal(value: Decimal, *, name: str, quantum: Decimal) -> Decimal:
    """Validate a signed decimal and its precision without changing the input."""
    if not value.is_finite():
        raise InvalidTradeError(f"{name} must be finite")
    normalized = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if normalized != value:
        exponent = quantum.as_tuple().exponent
        if not isinstance(exponent, int):
            raise InvalidTradeError(f"{name} has an invalid precision")
        decimal_places = -exponent
        raise InvalidTradeError(f"{name} supports at most {decimal_places} decimal places")
    return normalized


def money(value: Decimal) -> Decimal:
    """Round a calculated monetary amount to euro cents using banker's rounding."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def rate(value: Decimal) -> Decimal:
    """Round a calculated ratio while retaining enough precision for analytics."""
    return value.quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN)
