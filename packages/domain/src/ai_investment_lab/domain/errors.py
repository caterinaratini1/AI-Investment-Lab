"""Domain-level failures that callers can translate without parsing strings."""


class DomainError(ValueError):
    """Base class for rejected portfolio operations."""


class InvalidTradeError(DomainError):
    """The trade has invalid values or violates an accounting invariant."""


class InsufficientCashError(DomainError):
    """A BUY would make the portfolio cash balance negative."""


class PositionNotFoundError(DomainError):
    """A SELL references a missing or insufficient position."""


class MissingPriceError(DomainError):
    """A valuation lacks a quote for an open position."""
