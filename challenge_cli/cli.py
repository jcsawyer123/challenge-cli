import os
import json
from typing import List, Optional

import typer
from rich.console import Console

app = typer.Typer(
    help="Challenge Testing CLI - A modern CLI for testing coding challenges",
    add_completion=True,
    rich_markup_mode="markdown",
)
console = Console()

# --- Global Options State ---
class GlobalOptions:
    platform: str = "leetcode"
    problems_dir: str = os.getcwd()
    use_history: bool = True
    max_snapshots: int = 50
    debug: bool = False
    language: Optional[str] = None

options = GlobalOptions()

# --- Config and Context ---
def load_config(config_path: Optional[str] = None) -> dict:
    config_paths = [
        config_path,
        os.path.join(os.getcwd(), "challenge_cli_config.json"),
        os.path.expanduser("~/.challenge_cli_config.json"),
    ]
    for path in config_paths:
        if path and os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                continue
    return {}

def resolve_language_shorthand(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    mapping = {
        "python": "python", "py": "python",
        "go": "go", "golang": "go",
        "javascript": "javascript", "js": "javascript", "node": "javascript"
    }
    return mapping.get(lang.lower(), lang.lower())

def setup_options(
    platform: Optional[str] = None,
    config: Optional[str] = None,
    debug: bool = False,
    history: Optional[bool] = None,
    no_history: bool = False,
    language: Optional[str] = None,
) -> None:
    config_data = load_config(config)
    options.problems_dir = config_data.get("problems_dir", os.getcwd())
    options.platform = platform or config_data.get("default_platform", "leetcode")
    lang = resolve_language_shorthand(language)
    platform_config = config_data.get("platforms", {}).get(options.platform, {})
    options.language = lang or platform_config.get("language")
    options.use_history = True
    if "history" in config_data:
        options.use_history = config_data["history"]
    if history is not None:
        options.use_history = history
    if no_history:
        options.use_history = False
    options.max_snapshots = config_data.get("history", {}).get("max_snapshots", 50)
    options.debug = debug

# --- Autocompletion ---
def get_challenges(platform: str, problems_dir: str) -> List[str]:
    platform_dir = os.path.join(problems_dir, platform)
    if not os.path.exists(platform_dir):
        return []
    challenges = []
    for root, dirs, _ in os.walk(platform_dir):
        if "/.history" in root or "/." in root or "/__pycache__" in root:
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
    config = load_config()
    problems_dir = config.get("problems_dir", options.problems_dir)
    platform = config.get("default_platform", options.platform)
    challenges = get_challenges(platform, problems_dir)
    return [c for c in challenges if c.startswith(incomplete)]

def language_completer(incomplete: str) -> List[str]:
    return [l for l in ["python", "py", "javascript", "js", "go", "golang"] if l.startswith(incomplete.lower())]

def snapshot_id_completer(ctx: typer.Context, incomplete: str) -> List[str]:
    challenge_path = ctx.params.get("challenge_path", "")
    if not challenge_path:
        return []
    config = load_config()
    problems_dir = config.get("problems_dir", options.problems_dir)
    platform = config.get("default_platform", options.platform)
    history_dir = os.path.join(problems_dir, platform, challenge_path, '.history')
    snapshots_dir = os.path.join(history_dir, 'snapshots')
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
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.init_problem(language=language, function_name=function)

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
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language or options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.run_tests(
        language=language or options.language,
        detailed=detailed,
        cases_arg=cases,
        snapshot_comment=comment,
        snapshot_tag=tag
    )

@app.command()
def profile(
    challenge_path: str = typer.Argument(..., help="Challenge path", autocompletion=challenge_path_completer),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language", autocompletion=language_completer),
    iterations: int = typer.Option(100, "--iterations", "-i", help="Profiling iterations"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Detailed profiling"),
    cases: Optional[str] = typer.Option(None, "--cases", "-c", help="Test cases"),
    comment: Optional[str] = typer.Option(None, "--comment", help="Snapshot comment"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Snapshot tag"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
    history: Optional[bool] = typer.Option(None, "--history", help="Enable history"),
    no_history: bool = typer.Option(False, "--no-history", help="Disable history"),
):
    """Profile a solution."""
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language or options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.profile(
        language=language or options.language,
        iterations=iterations,
        detailed=detailed,
        cases_arg=cases,
        snapshot_comment=comment,
        snapshot_tag=tag
    )

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
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.analyze_complexity(language=language)

@app.command()
def clean(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Platform"),
    config: Optional[str] = typer.Option(None, "--config", help="Config file"),
    debug: bool = typer.Option(False, "--debug", help="Debug mode"),
):
    """Shutdown all hot containers immediately."""
    setup_options(platform, config, debug)
    from challenge_cli.plugins.docker_utils import shutdown_all_containers
    shutdown_all_containers()
    console.print(f"[green]Shutdown all {options.platform} containers.[/green]")

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
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language or options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.list_history(language=language or options.language, limit=limit)

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
    setup_options(platform, config, debug, history, no_history)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.show_snapshot(snapshot_id)

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
    setup_options(platform, config, debug, history, no_history)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.compare_snapshots(snapshot1, snapshot2)

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
    setup_options(platform, config, debug, history, no_history)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.restore_snapshot(snapshot_id, backup=backup)

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
    setup_options(platform, config, debug, history, no_history, language)
    from challenge_cli.tester import ChallengeTester
    tester = ChallengeTester(
        platform=options.platform,
        challenge_path=challenge_path,
        language=language or options.language,
        problems_dir=options.problems_dir,
        use_history=options.use_history,
        max_snapshots=options.max_snapshots
    )
    tester.visualize_history(language=language or options.language, output_path=output_path, cases_arg=cases)

if __name__ == "__main__":
    app()
