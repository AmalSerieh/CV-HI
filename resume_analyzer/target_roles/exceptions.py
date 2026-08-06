"""Domain-specific errors with messages suitable for CLI users."""


class TargetRoleError(Exception):
    """Base error for deterministic target-role analysis."""


class InvalidPipelineInputError(TargetRoleError, ValueError):
    """Raised when a recognized pipeline field has an invalid shape."""


class InvalidCatalogError(TargetRoleError, ValueError):
    """Raised when the role catalog or alias data is invalid."""
