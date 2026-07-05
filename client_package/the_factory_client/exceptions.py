"""Exception hierarchy for The Factory client."""


class FactoryError(Exception):
    """Base class for all Factory client errors."""


class PaymentRequiredError(FactoryError):
    """Server returned 402 — payment required.

    Attributes:
        challenge: The x402 challenge dict (asset, amount, pay_to, mint, ...).
    """

    def __init__(self, message: str, challenge: dict = None):
        super().__init__(message)
        self.challenge = challenge or {}


class PaymentVerificationError(FactoryError):
    """Server returned 402 with verification failure.

    Attributes:
        reason: Why verification failed (e.g. 'expired', 'signature_already_used').
        amount_paid_usd: How much was actually paid.
        required_usd: How much was required.
    """

    def __init__(self, message: str, reason: str = "",
                 amount_paid_usd: float = 0.0, required_usd: float = 0.0):
        super().__init__(message)
        self.reason = reason
        self.amount_paid_usd = amount_paid_usd
        self.required_usd = required_usd


class InsufficientFundsError(FactoryError):
    """Wallet does not have enough USDC to pay."""


class CapReachedError(FactoryError):
    """Service is paused because the ethical monthly cap was reached."""


class UpstreamError(FactoryError):
    """Upstream data source returned an error (502)."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
