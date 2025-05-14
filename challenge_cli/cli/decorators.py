"""
Decorators and mixins for Challenge CLI.
"""

from functools import wraps
from typing import Callable

import typer
from rich.console import Console

console = Console()


def with_error_handling(func: Callable) -> Callable:
    """Decorator to handle common error patterns in CLI commands."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            console.print(f"[bold red]Error in {func.__name__}:[/bold red] {e}")
            options = kwargs.get("options")
            if options and hasattr(options, "debug") and options.debug:
                import traceback

                console.print(traceback.format_exc())
            raise typer.Exit(code=1)

    return wrapper
