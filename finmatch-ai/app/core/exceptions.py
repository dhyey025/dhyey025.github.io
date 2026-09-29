"""Domain exceptions. These are mapped to HTTP responses in ``app.main``."""


class FinMatchError(Exception):
    """Base class for all FinMatch domain errors."""


class InvestorNotFoundError(FinMatchError):
    """Raised when an investor mandate ID does not exist."""

    def __init__(self, investor_id: str) -> None:
        self.investor_id = investor_id
        super().__init__(f"Investor mandate '{investor_id}' not found")


class DataIntegrityError(FinMatchError):
    """Raised when the investor mandate dataset is missing or inconsistent."""
