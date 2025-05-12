import os
import json
from typing import List, Optional, Tuple

# Moved imports to top
from challenge_cli.tester import ChallengeTester
from challenge_cli.plugins.docker_utils import shutdown_all_containers
# Import consolidated utils and history constant
from challenge_cli.utils import load_config, resolve_language_shorthand
from challenge_cli.history_manager import HISTORY_DIR_NAME

import typer
from rich.console import Console

app = typer.Typer(
    help="Challenge Testing CLI - A modern CLI for testing coding challenges",
    add_completion=True,
    rich_markup_mode="markdown",
)
console = Console()

# Removed load_config and resolve_language_shorthand - using versions from utils.py

# --- Helper Function for Option Resolution ---
def _resolve_options(
    language_override: Optional[str],
    platform_override: Optional[str],
    config_override: Optional[str],
    debug_override: bool,
    history_override: Optional[bool],
    no_history_override: bool,
) -> Tuple[str, str, bool, int, Optional[str], bool]:
    """Resolves options based on command args, config files, and defaults."""
    # Use imported load_config
    config_data = load_config(config_override)
    resolved_problems_dir = config_data.get("problems_dir", os.getcwd())
    resolved_platform = platform_override or config_data.get("default_platform", "leetcode")

    # Resolve language: command override > platform config in config file
    # Use imported resolve_language_shorthand
    resolved_lang_shorthand = resolve_language_shorthand(language_override)
    platform_config = config_data.get("platforms", {}).get(resolved_platform, {})
    resolved_language = resolved_lang_shorthand or platform_config.get("language")

    # Resolve history settings
    resolved_use_history = True
    # Check config file first
    if isinstance(config_data.get("history"), bool):
        resolved_use_history = config_data["history"]
    # Command-line flags override config
    if history_override is not None:
        resolved_use_history = history_override
    if no_history_override:
        resolved_use_history = False # --no-history takes precedence

    resolved_max_snapshots = config_data.get("history", {}).get("max_snapshots", 50)
    resolved_debug = debug_override

    return (
        resolved_platform,
        resolved_problems_dir,
        resolved_use_history,
        resolved_max_snapshots,
        resolved_language,
        resolved_debug, # Pass debug status back
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
    config = load_config()
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
    config = load_config()
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, _, resolved_debug = _resolve_options(
        language_override=language, # Pass language for potential config use
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    # 'init' requires an explicit language via the command line option
    # Use imported resolve_language_shorthand
    resolved_language = resolve_language_shorthand(language)
    if not resolved_language:
         console.print("[bold red]Error:[/bold red] The '--language' option is required for 'init'.")
         raise typer.Exit(code=1)

    if resolved_debug:
        console.print(f"Debug: Initializing challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{resolved_language}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language, # Use the validated language
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.init_problem(language=resolved_language, function_name=function)
        console.print(f"[green]Successfully initialized challenge '{challenge_path}' for {resolved_language}.[/green]")
    except Exception as e:
        console.print(f"[bold red]Error initializing challenge:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_language:
        # If language still not resolved, try reading from challenge config?
        # For now, let ChallengeTester handle it or error if needed.
        # Or exit early? Let's allow ChallengeTester to try.
        pass
        # console.print("[bold red]Error:[/bold red] Could not determine language. Use -l or configure.")
        # raise typer.Exit(code=1)

    if resolved_debug:
         console.print(f"Debug: Testing challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{resolved_language or 'auto'}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language, # Pass resolved language (could be None)
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        # Tester's run_tests method should handle None language if possible (e.g., by detecting)
        tester.run_tests(
            language=resolved_language, # Pass it along
            detailed=detailed,
            cases_arg=cases,
            snapshot_comment=comment,
            snapshot_tag=tag
        )
    except Exception as e:
        console.print(f"[bold red]Error running tests:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if resolved_debug:
         console.print(f"Debug: Profiling challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{resolved_language or 'auto'}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language,
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.profile(
            language=resolved_language,
            iterations=iterations,
            detailed=detailed,
            cases_arg=cases,
            snapshot_comment=comment,
            snapshot_tag=tag
        )
    except Exception as e:
        console.print(f"[bold red]Error profiling solution:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=language, # Pass explicitly provided language
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    # Analysis currently only supports Python. Default or validate.
    final_language = resolved_language or "python" # Default to python if not specified
    if final_language != "python":
        console.print("[bold red]Error:[/bold red] Analysis currently only supports Python ('-l python').")
        raise typer.Exit(code=1)

    if resolved_debug:
         console.print(f"Debug: Analyzing challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{final_language}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=final_language, # Use validated 'python'
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.analyze_complexity(language=final_language)
    except Exception as e:
        console.print(f"[bold red]Error analyzing complexity:[/bold red] {e}")
        if resolved_debug:
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
    # Resolve options mainly to get platform and debug status if needed
    resolved_platform, _, _, _, _, resolved_debug = _resolve_options(
        language_override=None, # Not needed for clean
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=None, # Not needed
        no_history_override=False, # Not needed
    )

    if resolved_debug:
        console.print(f"Debug: Shutting down containers for platform '{resolved_platform}'")

    try:
        shutdown_all_containers()
        # Use resolved_platform in the message
        console.print(f"[green]Shutdown all running challenge containers for platform '{resolved_platform}'.[/green]")
    except Exception as e:
        console.print(f"[bold red]Error shutting down containers:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_use_history:
        console.print("[yellow]History is disabled. Cannot list snapshots.[/yellow]")
        raise typer.Exit()

    if resolved_debug:
         console.print(f"Debug: Listing history for challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{resolved_language or 'auto'}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language,
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history, # Pass resolved value
            max_snapshots=resolved_max_snapshots
        )
        # Let tester handle language resolution if None
        tester.list_history(language=resolved_language, limit=limit)
    except Exception as e:
        console.print(f"[bold red]Error listing history:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=None, # Language not directly used by show, tester infers?
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_use_history:
        console.print("[yellow]History is disabled. Cannot show snapshot.[/yellow]")
        raise typer.Exit()

    if resolved_debug:
         console.print(f"Debug: Showing snapshot '{snapshot_id}' for challenge '{challenge_path}' on platform '{resolved_platform}'")

    try:
        # Tester needs language, even if just for context? Pass resolved default.
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language, # Pass resolved language
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.show_snapshot(snapshot_id)
    except Exception as e:
        console.print(f"[bold red]Error showing snapshot:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=None, # Language not directly used by compare?
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_use_history:
        console.print("[yellow]History is disabled. Cannot compare snapshots.[/yellow]")
        raise typer.Exit()

    if resolved_debug:
         console.print(f"Debug: Comparing snapshots '{snapshot1}' and '{snapshot2}' for challenge '{challenge_path}' on platform '{resolved_platform}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language, # Pass resolved language
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.compare_snapshots(snapshot1, snapshot2)
    except Exception as e:
        console.print(f"[bold red]Error comparing snapshots:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=None, # Language not directly used by restore?
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_use_history:
        console.print("[yellow]History is disabled. Cannot restore snapshot.[/yellow]")
        raise typer.Exit()

    if resolved_debug:
         console.print(f"Debug: Restoring snapshot '{snapshot_id}' for challenge '{challenge_path}' on platform '{resolved_platform}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language, # Pass resolved language
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.restore_snapshot(snapshot_id, backup=backup)
    except Exception as e:
        console.print(f"[bold red]Error restoring snapshot:[/bold red] {e}")
        if resolved_debug:
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
    resolved_platform, resolved_problems_dir, resolved_use_history, \
    resolved_max_snapshots, resolved_language, resolved_debug = _resolve_options(
        language_override=language,
        platform_override=platform,
        config_override=config,
        debug_override=debug,
        history_override=history,
        no_history_override=no_history,
    )

    if not resolved_use_history:
        console.print("[yellow]History is disabled. Cannot visualize history.[/yellow]")
        raise typer.Exit()

    if resolved_debug:
         console.print(f"Debug: Visualizing history for challenge '{challenge_path}' for platform '{resolved_platform}' in '{resolved_problems_dir}' with language '{resolved_language or 'auto'}'")

    try:
        tester = ChallengeTester(
            platform=resolved_platform,
            challenge_path=challenge_path,
            language=resolved_language,
            problems_dir=resolved_problems_dir,
            use_history=resolved_use_history,
            max_snapshots=resolved_max_snapshots
        )
        tester.visualize_history(language=resolved_language, output_path=output_path, cases_arg=cases)
    except Exception as e:
        console.print(f"[bold red]Error visualizing history:[/bold red] {e}")
        if resolved_debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
