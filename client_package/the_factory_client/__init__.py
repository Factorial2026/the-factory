"""The Factory Client — Python client for the x402 micropayment agent."""

from .client import Factory
from .exceptions import (
    FactoryError,
    PaymentRequiredError,
    PaymentVerificationError,
    InsufficientFundsError,
    CapReachedError,
    UpstreamError,
)

__all__ = [
    "Factory",
    "FactoryError",
    "PaymentRequiredError",
    "PaymentVerificationError",
    "InsufficientFundsError",
    "CapReachedError",
    "UpstreamError",
]
__version__ = "0.1.0"
