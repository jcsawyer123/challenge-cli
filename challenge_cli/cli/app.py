"""
Main Typer app and command definitions for Challenge CLI.
"""

import subprocess
from typing import Optional

import typer

from challenge_cli.core.logging import log_warning
from challenge_cli.output.terminal import console

# Import history and cache commands to register them
from . import cache, history
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
# Register history and cache subcommands
app.add_typer(history.history_app, name="history")
app.add_typer(cache.cache_app, name="cache")


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
def containers(
    filter_language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Filter containers by language",
        autocompletion=Completions.languages,
    ),
    all: bool = typer.Option(
        False, "--all", "-a", help="Show all containers including stopped ones"
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        "-f",
        help="Custom format string (e.g., 'table {{.Names}}\\t{{.Status}}')",
    ),
):
    """List challenge CLI containers."""
    cmd = ["docker", "ps"]

    if all:
        cmd.append("-a")

    # Add filter for challenge-cli containers
    cmd.extend(["--filter", "name=challenge-cli-"])

    # Add language filter if specified
    if filter_language:
        cmd.extend(["--filter", f"name=challenge-cli-{filter_language}"])

    # Add format
    if format:
        cmd.extend(["--format", format])
    else:
        cmd.extend(
            [
                "--format",
                "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}\t{{.RunningFor}}",
            ]
        )

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout.strip():
        if not format:  # Only add header if using default format
            console.print("[bold]Challenge CLI Containers:[/bold]")
        console.print(result.stdout)
    else:
        filter_msg = f" for language '{filter_language}'" if filter_language else ""
        console.print(f"[yellow]No challenge CLI containers found{filter_msg}[/yellow]")


@app.command(name="ps")
@with_error_handling
def ps():
    """Alias for 'containers' command - list all challenge CLI containers."""
    containers(filter_language=None, all=True, format=None)


@app.command()
@with_error_handling
def start(
    language: str = typer.Option(
        ...,
        "--language",
        "-l",
        help="Language to start container for",
        autocompletion=Completions.languages,
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
):
    """Pre-start a container for a specific language."""
    import os

    from challenge_cli.plugins import get_plugin
    from challenge_cli.plugins.docker_utils import start_hot_container

    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
    )

    try:
        plugin = get_plugin(language)
        if not plugin:
            console.print(
                f"[bold red]Error:[/bold red] No plugin found for language '{language}'"
            )
            raise typer.Exit(code=1)

        plugin.ensure_image()

        # Create a dummy workdir for pre-warming
        dummy_workdir = "/tmp/challenge-cli-warmup"
        os.makedirs(dummy_workdir, exist_ok=True)

        container_name = f"challenge-cli-{language}"

        # Start the container
        start_hot_container(
            plugin.docker_image,
            dummy_workdir,
            container_name,
            problems_dir=str(options.config.problems_dir),
            cache_dir=str(options.config.get_cache_dir()),
        )

        console.print(f"[green]✓[/green] Started container for {language}")
        console.print(f"[dim]Container name: {container_name}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to start container: {e}")
        raise typer.Exit(code=1)


@app.command()
@with_error_handling
def stop(
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Stop container for specific language",
        autocompletion=Completions.languages,
    ),
    all: bool = typer.Option(
        False, "--all", "-a", help="Stop all challenge CLI containers"
    ),
):
    """Stop challenge CLI containers."""
    from challenge_cli.plugins.docker_utils import shutdown_container

    if not language and not all:
        console.print("[bold red]Error:[/bold red] Please specify --language or --all")
        raise typer.Exit(code=1)

    if all:
        # Stop all challenge containers
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=challenge-cli-",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
        )

        container_names = result.stdout.strip().split("\n")
        container_names = [name for name in container_names if name]

        if not container_names:
            console.print("[yellow]No running challenge CLI containers found[/yellow]")
            return

        for container_name in container_names:
            shutdown_container(container_name)
            console.print(f"[green]✓[/green] Stopped container: {container_name}")
    else:
        # Stop specific language container
        container_name = f"challenge-cli-{language}"

        # Check if container exists
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
        )

        if container_name in result.stdout:
            shutdown_container(container_name)
            console.print(f"[green]✓[/green] Stopped container: {container_name}")
        else:
            console.print(f"[yellow]Container '{container_name}' not found[/yellow]")


@app.command()
@with_error_handling
def clean(
    language: Optional[str] = typer.Option(
        None, "--language", "-l", help="Clean containers for specific language only"
    ),
    stopped: bool = typer.Option(
        False, "--stopped", "-s", help="Only remove stopped containers"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force remove running containers"
    ),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
):
    """Remove challenge CLI containers."""
    options = resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
    )

    if language:
        # Clean specific language container
        container_name = f"challenge-cli-{language}"

        # Check container status
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            is_running = "Up" in result.stdout

            if is_running and not force and not stopped:
                console.print(
                    f"[yellow]Container '{container_name}' is running. Use --force to remove it.[/yellow]"
                )
                raise typer.Exit(code=1)

            if not is_running or force:
                subprocess.run(["docker", "rm", "-f", container_name], check=False)
                console.print(f"[green]✓[/green] Removed container: {container_name}")
            else:
                console.print(
                    f"[yellow]Skipping running container: {container_name}[/yellow]"
                )
        else:
            console.print(f"[yellow]Container '{container_name}' not found[/yellow]")
    else:
        # Clean all containers
        CommandHandlers.handle_clean(options)



if __name__ == "__main__":
    app()
