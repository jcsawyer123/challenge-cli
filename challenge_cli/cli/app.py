"""
Main Typer app and command definitions for Challenge CLI.
"""

from typing import Optional

import typer

from challenge_cli.core.logging import log_warning
from challenge_cli.output import console

# Import history commands to register them
from . import history
from .completions import Completions
from .decorators import with_error_handling
from .handlers import CommandHandlers
from .options import resolve_options

# Create main typer app
app = typer.Typer(
    help="Challenge Testing CLI - A modern CLI for testing coding challenges",
    add_completion=True,
    rich_markup_mode="markdown",
)
# Register history subcommands
app.add_typer(history.history_app, name="history")


# ---- Commands ----


@app.command()
@with_error_handling
def init(
    challenge_path: str = typer.Option(
        ..., "--challenge", "-c", help="Challenge path (e.g., 'two-sum')"
    ),
    language: str = typer.Option(
        "python",
        "--language",
        "-l",
        help="Programming language",
        autocompletion=Completions.languages,
    ),
    function: str = typer.Option(
        "solve", "--function", "-f", help="Function/method name"
    ),
    platform: Optional[str] = typer.Option(
        None, "--platform", "-p", help="Platform (leetcode, aoc, etc.)"
    ),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Initialize a new challenge."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    # Language is required for init
    if not options.language:
        log_warning("Init command called without language")
        console.print(
            "[bold red]Error:[/bold red] The '--language' option is required for 'init'."
        )
        raise typer.Exit(code=1)

    CommandHandlers.handle_init(options, challenge_path, language, function)


@app.command()
@with_error_handling
def test(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Programming language",
        autocompletion=Completions.languages,
    ),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Detailed test info"),
    cases: Optional[str] = typer.Option(
        None, "--cases", help="Test cases to run (e.g., '1,2,5-7')"
    ),
    comment: Optional[str] = typer.Option(None, "--comment", help="Snapshot comment"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Snapshot tag"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Test a solution."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    CommandHandlers.handle_test(options, challenge_path, detailed, cases, comment, tag)


@app.command()
@with_error_handling
def profile(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Programming language",
        autocompletion=Completions.languages,
    ),
    iterations: int = typer.Option(
        100, "--iterations", "-i", help="Profiling iterations"
    ),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Detailed profiling"),
    cases: Optional[str] = typer.Option(None, "--cases", "-tc", help="Test cases"),
    comment: Optional[str] = typer.Option(None, "--comment", help="Snapshot comment"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Snapshot tag"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Profile a solution."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    CommandHandlers.handle_profile(
        options, challenge_path, iterations, detailed, cases, comment, tag
    )


@app.command()
@with_error_handling
def analyze(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    language: str = typer.Option(
        "python",
        "--language",
        "-l",
        help="Programming language (Python only)",
        autocompletion=Completions.languages,
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Analyze solution complexity (Python only)."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    CommandHandlers.handle_analyze(options, challenge_path, language)


@app.command()
@with_error_handling
def clean(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
):
    """Shutdown all running challenge containers immediately."""
    options = resolve_options(
        platform_override=platform,
        config_override=config,
        debug_override=debug,
    )

    CommandHandlers.handle_clean(options)


if __name__ == "__main__":
    app()
