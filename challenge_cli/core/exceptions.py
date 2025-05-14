class ChallengeCLIError(Exception):
    """Base exception for all Challenge CLI errors."""

    pass


class ConfigurationError(ChallengeCLIError):
    """Raised when configuration is invalid or missing."""

    pass


class PluginError(ChallengeCLIError):
    """Raised when a language plugin fails."""

    pass


class TestExecutionError(ChallengeCLIError):
    """Raised when test execution fails."""

    pass


class HistoryError(ChallengeCLIError):
    """Raised when history operations fail."""

    pass


class DockerError(ChallengeCLIError):
    """Raised when Docker operations fail."""

    pass


class ValidationError(ChallengeCLIError):
    """Raised when input validation fails."""

    pass


class HistoryManagerError(Exception):
    """Base exception for HistoryManager errors."""

    pass


class SnapshotNotFoundError(HistoryManagerError):
    """Raised when a snapshot ID is not found."""

    pass
