"""
History-specific commands for Challenge CLI.
"""

from typing import Optional

import typer

from challenge_cli.core.logging import log_warning
from challenge_cli.output import console

from .completions import Completions
from .decorators import with_error_handling
from .handlers import HistoryCommandHandlers
from .options import resolve_options

# Create history subcommand group
history_app = typer.Typer(help="Manage solution history")


@history_app.command("list")
@with_error_handling
def history_list(
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
    limit: int = typer.Option(10, "--limit", "-n", help="Number of snapshots to show"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """List solution snapshots."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not options.use_history:
        log_warning("History list command called but history is disabled")
        console.print("[yellow]History is disabled. Cannot list snapshots.[/yellow]")
        raise typer.Exit()

    HistoryCommandHandlers.handle_list(options, challenge_path, limit)


@history_app.command("show")
@with_error_handling
def history_show(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    snapshot_id: str = typer.Option(
        ...,
        "--snapshot",
        "-s",
        help="Snapshot ID",
        autocompletion=Completions.snapshots,
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Show details of a specific snapshot."""
    options = resolve_options(
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not options.use_history:
        log_warning("History show command called but history is disabled")
        console.print("[yellow]History is disabled. Cannot show snapshot.[/yellow]")
        raise typer.Exit()

    HistoryCommandHandlers.handle_show(options, challenge_path, snapshot_id)


@history_app.command("compare")
@with_error_handling
def history_compare(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    snapshot1: str = typer.Option(
        ...,
        "--first",
        "-1",
        help="First snapshot ID",
        autocompletion=Completions.snapshots,
    ),
    snapshot2: str = typer.Option(
        ...,
        "--second",
        "-2",
        help="Second snapshot ID",
        autocompletion=Completions.snapshots,
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Compare two snapshots."""
    options = resolve_options(
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not options.use_history:
        log_warning("History compare command called but history is disabled")
        console.print("[yellow]History is disabled. Cannot compare snapshots.[/yellow]")
        raise typer.Exit()

    HistoryCommandHandlers.handle_compare(options, challenge_path, snapshot1, snapshot2)


@history_app.command("restore")
@with_error_handling
def history_restore(
    challenge_path: str = typer.Option(
        ...,
        "--challenge",
        "-c",
        help="Challenge path",
        autocompletion=Completions.challenges,
    ),
    snapshot_id: str = typer.Option(
        ...,
        "--snapshot",
        "-s",
        help="Snapshot ID",
        autocompletion=Completions.snapshots,
    ),
    backup: bool = typer.Option(
        False, "--backup", "-b", help="Backup before restoring"
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Restore a snapshot."""
    options = resolve_options(
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not options.use_history:
        log_warning("History restore command called but history is disabled")
        console.print("[yellow]History is disabled. Cannot restore snapshot.[/yellow]")
        raise typer.Exit()

    HistoryCommandHandlers.handle_restore(options, challenge_path, snapshot_id, backup)


@history_app.command("visualize")
@with_error_handling
def history_visualize(
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
    output_path: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file (e.g., history.html)"
    ),
    cases: Optional[str] = typer.Option(None, "--cases", help="Test cases to include"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Visualize solution history."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not options.use_history:
        log_warning("History visualize command called but history is disabled")
        console.print("[yellow]History is disabled. Cannot visualize history.[/yellow]")
        raise typer.Exit()

    HistoryCommandHandlers.handle_visualize(options, challenge_path, output_path, cases)
