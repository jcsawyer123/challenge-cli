from dataclasses import dataclass
import os
import json
from typing import List, Optional, Tuple

# Moved imports to top
from challenge_cli.core.config import ChallengeConfig, load_config_file
from challenge_cli.plugins.registry import resolve_language
from challenge_cli.tester import ChallengeTester
from challenge_cli.plugins.docker_utils import shutdown_all_containers
# Import consolidated utils and history constant
from challenge_cli.history_manager import HISTORY_DIR_NAME

import typer
from rich.console import Console

app = typer.Typer(
    help="Challenge Testing CLI - A modern CLI for testing coding challenges",
    add_completion=True,
    rich_markup_mode="markdown",
)
console = Console()


# --- Helper Function for Option Resolution ---
@dataclass
class ResolvedOptions:
    """Container for resolved CLI options."""
    platform: str
    problems_dir: str
    use_history: bool
    max_snapshots: int
    language: Optional[str]
    debug: bool
    config: ChallengeConfig  # Include the full config object


def _resolve_options(
    language_override: Optional[str],
    platform_override: Optional[str], 
    config_override: Optional[str],
    debug_override: bool,
    history_override: Optional[bool],
    no_history_override: bool,
) -> ResolvedOptions:
    """Resolves options based on command args, config files, and defaults."""
    # Load configuration
    config_data = load_config_file(config_override)
    config = ChallengeConfig.from_dict(config_data)
    
    # Apply overrides
    if platform_override:
        config.platform = platform_override
    
    if debug_override:
        config.debug = True
    
    # Resolve language
    language = None
    if language_override:
        language = resolve_language(language_override)
    elif config.language:
        language = config.language
    else:
        # Try platform-specific config
        platform_config = config.get_platform_config()
        if platform_config.language:
            language = platform_config.language
    
    # Resolve history settings
    use_history = config.history.enabled
    
    # Command-line flags override config
    if history_override is not None:
        use_history = history_override
    if no_history_override:
        use_history = False  # --no-history takes precedence
    
    return ResolvedOptions(
        platform=config.platform,
        problems_dir=str(config.problems_dir),
        use_history=use_history,
        max_snapshots=config.history.max_snapshots,
        language=language,
        debug=config.debug,
        config=config  # Pass the full config for future use
    )

# --- Autocompletion ---
# Note: Autocompletion functions now load config directly as needed
def get_challenges(platform: str, problems_dir: str) -> List[str]:
    platform_dir = os.path.join(problems_dir, platform)
    if not os.path.exists(platform_dir):
        return []
    challenges = []
    for root, dirs, _ in os.walk(platform_dir):
        # Use imported HISTORY_DIR_NAME constant
        history_dir_segment = f"{os.sep}{HISTORY_DIR_NAME}"
        if history_dir_segment in root or "/." in root or "/__pycache__" in root:
            continue
        rel_path = os.path.relpath(root, platform_dir)
        if rel_path == ".":
            for d in dirs:
                if not d.startswith('.'):
                    challenges.append(d)
        else:
            if any(segment in ["python", "go", "javascript"] for segment in rel_path.split(os.sep)):
                continue
            if os.path.basename(rel_path) not in challenges:
                challenges.append(rel_path)
    return sorted(list(set(challenges)))

def challenge_path_completer(incomplete: str) -> List[str]:
    # Load config directly using imported function
    # This avoids reliance on global state or complex context passing
    config = load_config_file()
    # Use getcwd() as fallback if not in config, mirroring old options default
    problems_dir = config.get("problems_dir", os.getcwd())
    # Use 'leetcode' as fallback, mirroring old options default
    platform = config.get("default_platform", "leetcode")
    challenges = get_challenges(platform, problems_dir)
    return [c for c in challenges if c.startswith(incomplete)]

def language_completer(incomplete: str) -> List[str]:
    return [l for l in ["python", "py", "javascript", "js", "go", "golang"] if l.startswith(incomplete.lower())]

def snapshot_id_completer(ctx: typer.Context, incomplete: str) -> List[str]:
    challenge_path = ctx.params.get("challenge_path", "")
    if not challenge_path:
        return []
    # Load config directly using imported function
    config = load_config_file()
    problems_dir = config.get("problems_dir", os.getcwd())
    # Determine platform: Use context if available, else config, else default
    platform = ctx.params.get("platform") or config.get("default_platform", "leetcode")

    # Use imported HISTORY_DIR_NAME constant
    history_dir = os.path.join(problems_dir, platform, challenge_path, HISTORY_DIR_NAME)
    snapshots_dir = os.path.join(history_dir, 'snapshots') # Assuming 'snapshots' is internal detail of history manager
    if not os.path.exists(snapshots_dir):
        return []
    return sorted([item for item in os.listdir(snapshots_dir) if incomplete.lower() in item.lower()])

# --- Commands ---

@app.command()
def init(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path (e.g., 'two-sum')"),
    language: str = typer.Option("python", "--language", "-l", help="Programming language", autocompletion=language_completer),
    function: str = typer.Option("solve", "--function", "-f", help="Function/method name"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform (leetcode, aoc, etc.)"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Initialize a new challenge."""
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    # Language is required for init
    if not options.language:
        console.print("[bold red]Error:[/bold red] The '--language' option is required for 'init'.")
        raise typer.Exit(code=1)
    
    if options.debug:
        console.print(f"Debug: Initializing challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{options.language}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.init_problem(language=options.language, function_name=function)
        console.print(f"[green]Successfully initialized challenge '{challenge_path}' for {options.language}.[/green]")
    except Exception as e:
        console.print(f"[bold red]Error initializing challenge:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def test(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language", autocompletion=language_completer),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Detailed test info"),
    cases: Optional[str] = typer.Option(None, "--cases", help="Test cases to run (e.g., '1,2,5-7')"),
    comment: Optional[str] = typer.Option(None, "--comment", help="Snapshot comment"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Snapshot tag"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Test a solution."""
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if options.debug:
        console.print(f"Debug: Testing challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{options.language or 'auto'}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.run_tests(
            language=options.language,
            detailed=detailed,
            cases_arg=cases,
            snapshot_comment=comment,
            snapshot_tag=tag
        )
    except Exception as e:
        console.print(f"[bold red]Error running tests:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def profile(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language", autocompletion=language_completer),
    iterations: int = typer.Option(100, "--iterations", "-i", help="Profiling iterations"),
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
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if options.debug:
        console.print(f"Debug: Profiling challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{options.language or 'auto'}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.profile(
            language=options.language,
            iterations=iterations,
            detailed=detailed,
            cases_arg=cases,
            snapshot_comment=comment,
            snapshot_tag=tag
        )
    except Exception as e:
        console.print(f"[bold red]Error profiling solution:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def analyze(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    language: str = typer.Option("python", "--language", "-l", help="Programming language (Python only)", autocompletion=language_completer),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Analyze solution complexity (Python only)."""
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    # Validate language for analysis
    final_language = options.language or "python"
    if final_language != "python":
        console.print("[bold red]Error:[/bold red] Analysis currently only supports Python ('-l python').")
        raise typer.Exit(code=1)
    
    if options.debug:
        console.print(f"Debug: Analyzing challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{final_language}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=final_language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.analyze_complexity(language=final_language)
    except Exception as e:
        console.print(f"[bold red]Error analyzing complexity:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@app.command()
def clean(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
):
    """Shutdown all running challenge containers immediately."""
    options = _resolve_options(
        language_override=None,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=None,
        no_history_override=False,
    )
    
    if options.debug:
        console.print(f"Debug: Shutting down containers for platform '{options.platform}'")
    
    try:
        shutdown_all_containers()
        console.print(f"[green]Shutdown all running challenge containers for platform '{options.platform}'.[/green]")
    except Exception as e:
        console.print(f"[bold red]Error shutting down containers:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


# --- History Subcommands ---
history_app = typer.Typer(help="Manage solution history")
app.add_typer(history_app, name="history")


@history_app.command("list")
def history_list(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language", autocompletion=language_completer),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of snapshots to show"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """List solution snapshots."""
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if not options.use_history:
        console.print("[yellow]History is disabled. Cannot list snapshots.[/yellow]")
        raise typer.Exit()
    
    if options.debug:
        console.print(f"Debug: Listing history for challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{options.language or 'auto'}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.list_history(language=options.language, limit=limit)
    except Exception as e:
        console.print(f"[bold red]Error listing history:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@history_app.command("show")
def history_show(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    snapshot_id: str = typer.Option(..., "--snapshot", "-s", help="Snapshot ID", autocompletion=snapshot_id_completer),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Show details of a specific snapshot."""
    options = _resolve_options(
        language_override=None,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if not options.use_history:
        console.print("[yellow]History is disabled. Cannot show snapshot.[/yellow]")
        raise typer.Exit()
    
    if options.debug:
        console.print(f"Debug: Showing snapshot '{snapshot_id}' for challenge '{challenge_path}' on platform '{options.platform}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.show_snapshot(snapshot_id)
    except Exception as e:
        console.print(f"[bold red]Error showing snapshot:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@history_app.command("compare")
def history_compare(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    snapshot1: str = typer.Option(..., "--first", "-1", help="First snapshot ID", autocompletion=snapshot_id_completer),
    snapshot2: str = typer.Option(..., "--second", "-2", help="Second snapshot ID", autocompletion=snapshot_id_completer),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Compare two snapshots."""
    options = _resolve_options(
        language_override=None,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if not options.use_history:
        console.print("[yellow]History is disabled. Cannot compare snapshots.[/yellow]")
        raise typer.Exit()
    
    if options.debug:
        console.print(f"Debug: Comparing snapshots '{snapshot1}' and '{snapshot2}' for challenge '{challenge_path}' on platform '{options.platform}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.compare_snapshots(snapshot1, snapshot2)
    except Exception as e:
        console.print(f"[bold red]Error comparing snapshots:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@history_app.command("restore")
def history_restore(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    snapshot_id: str = typer.Option(..., "--snapshot", "-s", help="Snapshot ID", autocompletion=snapshot_id_completer),
    backup: bool = typer.Option(False, "--backup", "-b", help="Backup before restoring"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Restore a snapshot."""
    options = _resolve_options(
        language_override=None,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if not options.use_history:
        console.print("[yellow]History is disabled. Cannot restore snapshot.[/yellow]")
        raise typer.Exit()
    
    if options.debug:
        console.print(f"Debug: Restoring snapshot '{snapshot_id}' for challenge '{challenge_path}' on platform '{options.platform}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.restore_snapshot(snapshot_id, backup=backup)
    except Exception as e:
        console.print(f"[bold red]Error restoring snapshot:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)


@history_app.command("visualize")
def history_visualize(
    challenge_path: str = typer.Option(..., "--challenge", "-c", help="Challenge path", autocompletion=challenge_path_completer),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language", autocompletion=language_completer),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (e.g., history.html)"),
    cases: Optional[str] = typer.Option(None, "--cases", help="Test cases to include"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Visualize solution history."""
    options = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )
    
    if not options.use_history:
        console.print("[yellow]History is disabled. Cannot visualize history.[/yellow]")
        raise typer.Exit()
    
    if options.debug:
        console.print(f"Debug: Visualizing history for challenge '{challenge_path}' for platform '{options.platform}' in '{options.problems_dir}' with language '{options.language or 'auto'}'")
    
    try:
        tester = ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots
        )
        tester.visualize_history(language=options.language, output_path=output_path, cases_arg=cases)
    except Exception as e:
        console.print(f"[bold red]Error visualizing history:[/bold red] {e}")
        if options.debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)
    
# --- Main Entry Point ---
if __name__ == "__main__":
    app()
