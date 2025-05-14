"""Cache-specific commands for Challenge CLI."""

from typing import Optional

import typer

from challenge_cli.cli.cache_management import (
    clean_old_cache,
    clear_cache,
    show_cache_info,
    show_cache_statistics,
)
from challenge_cli.output.terminal import console

# Create cache subcommand group
cache_app = typer.Typer(help="Manage challenge CLI cache")


@cache_app.command("show")
def cache_show():
    """Show cache information."""
    show_cache_info()


@cache_app.command("clear")
def cache_clear(
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Language to clear cache for (or 'all' for all languages)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Clear cache directory."""
    if not force:
        confirm = typer.confirm(
            f"Clear {'all' if not language else language} cache?", default=False
        )
        if not confirm:
            console.print("Operation cancelled")
            return

    clear_cache(language)


@cache_app.command("stats")
def cache_stats():
    """Show cache statistics."""
    show_cache_statistics()


@cache_app.command("clean")
def cache_clean(
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Remove files older than this many days",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Clean old cache files."""
    if not force:
        confirm = typer.confirm(
            f"Remove cache files older than {days} days?", default=False
        )
        if not confirm:
            console.print("Operation cancelled")
            return

    clean_old_cache(days)
