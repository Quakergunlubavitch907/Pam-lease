"""Custom exceptions for pam-lease."""


class LeaseNotFoundError(Exception):
    """Raised when a lease file does not exist for the given user."""


class LeaseExpiredError(Exception):
    """Raised when a lease exists but its expiry time has passed."""


class LeaseExistsError(Exception):
    """Raised when a lease already exists and --force was not specified."""


class UserNotFoundError(Exception):
    """Raised when the specified system user does not exist."""
