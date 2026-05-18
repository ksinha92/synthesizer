"""Domain errors. No framework dependencies."""


class DomainError(Exception):
    """Base domain error."""

    def __init__(self, message: str = "", code: str = "domain_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthenticationError(DomainError):
    """Invalid credentials, expired token, or missing authentication."""

    def __init__(self, message: str = "Authentication failed", code: str = "authentication_error"):
        super().__init__(message=message, code=code)


class AuthorizationError(DomainError):
    """Insufficient permissions for the requested operation."""

    def __init__(self, message: str = "Insufficient permissions", code: str = "authorization_error"):
        super().__init__(message=message, code=code)


class NotFoundError(DomainError):
    """Requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(message=message, code=code)
