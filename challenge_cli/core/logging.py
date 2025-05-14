"""
Logging configuration and utilities for Challenge CLI.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler

# Global console instance for rich output
console = Console(stderr=True)

# Logger name
LOGGER_NAME = "challenge_cli"

# Log format for file output
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Global logger instance
_logger: Optional[logging.Logger] = None


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""

    def __init__(self):
        super().__init__()
        self.context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """Set context values that will be added to all log records."""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear all context values."""
        self.context.clear()

    def filter(self, record):
        """Add context information to the log record."""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class ChallengeLogFormatter(logging.Formatter):
    """Custom formatter that includes context information."""

    def format(self, record):
        # Build context string from record attributes
        context_parts = []

        # Add standard context fields if they exist
        for field in ["platform", "challenge", "language"]:
            if hasattr(record, field):
                value = getattr(record, field)
                if value:
                    context_parts.append(f"{field}={value}")

        # Format the base message
        message = super().format(record)

        # Add context if any
        if context_parts:
            context_str = f"[{', '.join(context_parts)}]"
            return f"{context_str} {message}"

        return message


def setup_logger(
    debug: bool = False, log_file: Optional[Path] = None, verbose: bool = False
) -> logging.Logger:
    """
    Set up the logger with appropriate handlers and formatting.

    Args:
        debug: Enable debug logging
        log_file: Optional file path to write logs
        verbose: Enable verbose output (info level)

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    # Create logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove any existing handlers
    logger.handlers.clear()

    # Create and add context filter
    context_filter = ContextFilter()
    logger.addFilter(context_filter)

    # Console handler with Rich
    console_handler = RichHandler(
        console=console,
        show_time=False,
        show_path=debug,
        rich_tracebacks=True,
        tracebacks_show_locals=debug,
        markup=True,
    )

    # Set console log level based on flags
    if debug:
        console_handler.setLevel(logging.DEBUG)
    elif verbose:
        console_handler.setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.WARNING)

    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = ChallengeLogFormatter(FILE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


@contextmanager
def log_context(**kwargs):
    """
    Context manager to temporarily set logging context.

    Example:
        with log_context(platform='leetcode', challenge='two-sum'):
            logger.info("Running tests")
    """
    logger = get_logger()
    context_filter = None

    # Find the context filter
    for filter_ in logger.filters:
        if isinstance(filter_, ContextFilter):
            context_filter = filter_
            break

    if context_filter:
        old_context = context_filter.context.copy()
        context_filter.set_context(**kwargs)
        try:
            yield
        finally:
            context_filter.context = old_context
    else:
        yield


def log_debug(message: str, **kwargs):
    """Log a debug message with optional context."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.debug(message)


def log_info(message: str, **kwargs):
    """Log an info message with optional context."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.info(message)


def log_warning(message: str, **kwargs):
    """Log a warning message with optional context."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.warning(message)


def log_error(message: str, exc_info=None, **kwargs):
    """Log an error message with optional exception info and context."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.error(message, exc_info=exc_info)


def log_critical(message: str, exc_info=None, **kwargs):
    """Log a critical message with optional exception info and context."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.critical(message, exc_info=exc_info)


def log_performance(operation: str, duration: float, **kwargs):
    """Log performance information."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.info(f"Performance: {operation} took {duration:.3f}s")


def log_docker_command(command: list, **kwargs):
    """Log Docker command execution."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.debug(f"Docker command: {' '.join(command)}")


def log_file_operation(operation: str, path: Path, **kwargs):
    """Log file operations."""
    logger = get_logger()
    with log_context(**kwargs):
        logger.debug(f"File {operation}: {path}")


def logged_operation(operation_name: str):
    """
    Decorator to log function entry/exit and duration.

    Example:
        @logged_operation("test_execution")
        def run_tests(self):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()

            # Extract context from self if it's a method
            context = {}
            if args and hasattr(args[0], "platform"):
                context["platform"] = getattr(args[0], "platform", None)
            if args and hasattr(args[0], "challenge_path"):
                context["challenge"] = getattr(args[0], "challenge_path", None)
            if args and hasattr(args[0], "language"):
                context["language"] = getattr(args[0], "language", None)

            with log_context(**context):
                logger.debug(f"Starting {operation_name}")
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.debug(f"Completed {operation_name} in {duration:.3f}s")
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(
                        f"Failed {operation_name} after {duration:.3f}s: {str(e)}"
                    )
                    raise

        return wrapper

    return decorator


# Convenience function to set up logging from CLI
def configure_logging(
    debug: bool = False, verbose: bool = False, log_file: Optional[str] = None
):
    """
    Configure logging based on CLI options.

    Args:
        debug: Enable debug logging
        verbose: Enable verbose output
        log_file: Optional log file path
    """
    log_path = Path(log_file) if log_file else None
    setup_logger(debug=debug, log_file=log_path, verbose=verbose)
