from typing import Optional, List, Dict, Any, Union

from challenge_cli.utils import format_memory, format_relative_time, format_time
from rich import print as rprint
from rich.box import ROUNDED
from rich.columns import Columns
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.markdown import Markdown
from rich.console import Group

# ==============================================================================
# Constants & Global Console
# ==============================================================================

console = Console()

# Define custom styles
SUCCESS_STYLE = Style(color="green", bold=True)
FAIL_STYLE = Style(color="red", bold=True)
WARNING_STYLE = Style(color="yellow", bold=True)
INFO_STYLE = Style(color="blue", bold=True)
BOLD_STYLE = Style(bold=True)
DIM_STYLE = Style(dim=True)
CYAN_STYLE = Style(color="cyan")
YELLOW_STYLE = Style(color="yellow")
MAGENTA_STYLE = Style(color="magenta")
WHITE_STYLE = Style(color="white")

# ==============================================================================
# Private Helper Functions
# ==============================================================================

def _create_panel(
    content: RenderableType,
    title: Optional[str] = None,
    border_style: Union[str, Style] = "blue",
    padding: tuple[int, int] = (1, 2),
    box: Any = ROUNDED,
    **kwargs: Any
) -> Panel:
    """Helper function to create a Rich Panel."""
    return Panel(
        content,
        title=title,
        border_style=border_style,
        padding=padding,
        box=box,
        **kwargs
    )

def _create_table(
    title: Optional[str] = None,
    box: Any = ROUNDED,
    show_header: bool = True,
    header_style: Union[str, Style] = "bold blue",
    **kwargs: Any
) -> Table:
    """Helper function to create a Rich Table."""
    return Table(
        title=title,
        box=box,
        show_header=show_header,
        header_style=header_style,
        **kwargs
    )

def _print_status_message(icon: str, msg: str, style: Union[str, Style]):
    """Helper function to print simple status messages."""
    console.print(f"[{str(style)}]{icon}[/{str(style)}]  [{str(style)}]{msg}[/{str(style)}]")

def _print_stdout_panel(stdout: Optional[str], title: str, border_style: Union[str, Style]):
    """Helper function to print stdout in a panel if it exists."""
    if stdout:
        console.print(_create_panel(
            stdout,
            title=f"[{str(border_style)}]{title}[/]",
            border_style=border_style,
            padding=(0, 1)
        ))

def _print_stdout_sample_panel(stdout: Optional[str], max_lines: int = 5):
    """Helper function to print a sample of stdout in a panel."""
    if stdout:
        lines = stdout.splitlines()
        sample_content = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            sample_content += f"\n[dim]... ({len(lines) - max_lines} more lines)[/dim]"
        
        console.print(_create_panel(
            sample_content,
            title="[magenta]Stdout Sample[/magenta]",
            border_style=MAGENTA_STYLE,
            padding=(0, 1)
        ))

def _print_traceback_panel(traceback_str: Optional[str]):
    """Helper function to print a traceback in a panel if it exists."""
    if traceback_str:
        syntax = Syntax(traceback_str, "python", theme="monokai", line_numbers=True)
        console.print(_create_panel(syntax, title="[red]Traceback[/red]", border_style=FAIL_STYLE))

# ==============================================================================
# General UI Elements
# ==============================================================================

def print_banner():
    """Print a beautiful banner using Rich."""
    banner_content = Text.assemble(
        ("Challenge Testing CLI", BOLD_STYLE + YELLOW_STYLE),
        "\n",
        ("Modern coding challenge testing tool", DIM_STYLE)
    )
    console.print(_create_panel(banner_content, padding=(1, 2)))

def print_divider(title: Optional[str] = None):
    """Print a styled divider with optional title."""
    console.print(Rule(title=title, style=INFO_STYLE))

# ==============================================================================
# Simple Status Messages
# ==============================================================================

def print_info(msg: str):
    """Print an informational message (neutral information)."""
    _print_status_message("ℹ", msg, INFO_STYLE)

def print_warning(msg: str):
    """Print a warning message (caution but not error)."""
    _print_status_message("⚠", msg, WARNING_STYLE)

def print_success(msg: str):
    """Print a success message (operation completed successfully)."""
    _print_status_message("✓", msg, SUCCESS_STYLE)

# Renamed for clarity:
def print_failure(msg: str):
    """Print a failure message (operation failed, but not a code error)."""
    _print_status_message("✗", msg, FAIL_STYLE)

# ==============================================================================
# Test Case Output
# ==============================================================================

def print_test_case_result(
    case_num: int,
    passed: bool,
    exec_time: str,
    memory: str,
    result: Any,
    expected: Any,
    stdout: Optional[str],
    input_values: Optional[Any] = None,
    detailed: bool = False
):
    """Display test case results in a formatted table or panel."""
    status_icon = "✓" if passed else "✗"
    status_text = Text(f"{status_icon} {'PASSED' if passed else 'FAILED'}",
                       style=SUCCESS_STYLE if passed else FAIL_STYLE)
    
    summary = Text.assemble(
        ("Test Case ", YELLOW_STYLE),
        (str(case_num), YELLOW_STYLE + BOLD_STYLE),
        (": ", "default"),
        status_text,
        (" (", DIM_STYLE),
        (exec_time, CYAN_STYLE),
        (", ", DIM_STYLE),
        (memory, CYAN_STYLE),
        (")", DIM_STYLE)
    )
    
    if detailed or not passed:
        # Create detailed table
        table = _create_table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style=INFO_STYLE, width=12)
        table.add_column("Value")
        
        if input_values is not None:
            table.add_row("Input:", str(input_values))
        table.add_row("Expected:", str(expected))
        table.add_row("Output:", str(result))
        
        # Create panel with summary and table
        content = Group(summary, table)
        panel = _create_panel(
            content,
            border_style=SUCCESS_STYLE if passed else FAIL_STYLE,
            padding=(0, 1)
        )
        console.print(panel)
    else:
        console.print(summary)
    
    _print_stdout_panel(stdout, "Stdout", MAGENTA_STYLE)

def print_test_error(
    case_num: int,
    error_msg: str,
    lineno: Optional[int] = None,
    line_content: Optional[str] = None,
    stdout: Optional[str] = None,
    detailed: bool = False,
    traceback_str: Optional[str] = None
):

    error_content = Text.assemble(
        ("Test Case ", YELLOW_STYLE),
        (str(case_num), YELLOW_STYLE + BOLD_STYLE),
        (": ", "default"),
        ("✗ ERROR", FAIL_STYLE),
        ("\n\n", "default"),
        (error_msg, FAIL_STYLE)
    )
    if lineno and line_content:
        error_content.append(f"\n\nat line {lineno}: ", style=YELLOW_STYLE)
        error_content.append(line_content, style=WHITE_STYLE)

    # Only show traceback if it's present and different from error_msg
    show_traceback = (
        detailed and traceback_str and traceback_str.strip() and
        traceback_str.strip() != error_msg.strip()
    )
    if show_traceback:
        syntax = Syntax(traceback_str, "python", theme="monokai", line_numbers=True, word_wrap=True)
        content = Group(error_content, syntax)
    else:
        content = error_content

    console.print(_create_panel(
        content,
        title="[red]Error[/red]",
        border_style=FAIL_STYLE,
        padding=(1, 2)
    ))

    # Stdout panel
    if stdout:
        lines = stdout.splitlines()
        sample_content = "\n".join(lines[:10])
        if len(lines) > 10:
            sample_content += f"\n[dim]... ({len(lines) - 10} more lines)[/dim]"
        console.print(_create_panel(
            sample_content,
            title="[magenta]Stdout before error[/magenta]",
            border_style=MAGENTA_STYLE,
            padding=(0, 1)
        ))


def print_summary(total_passed: int, total_run: int, selected: int, total: int):
    """Display test summary with progress visualization."""
    # Create progress bar visualization
    progress_bar = Progress(
        TextColumn("[bold]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )
    progress_bar.add_task(
        f"Tests Passed",
        total=total_run,
        completed=total_passed
    )
    console.print(progress_bar)

    # Create summary panel
    summary_content = Text.assemble(
        ("Summary: ", BOLD_STYLE + YELLOW_STYLE),
        ("Passed ", "default"),
        (str(total_passed), SUCCESS_STYLE),
        ("/", "default"),
        (str(total_run), INFO_STYLE + BOLD_STYLE),
        (" test cases ", "default"),
        ("(out of ", DIM_STYLE),
        (str(selected), INFO_STYLE),
        (" selected, ", DIM_STYLE),
        (str(total), INFO_STYLE),
        (" total)", DIM_STYLE)
    )
    
    panel = _create_panel(
        summary_content,
        border_style=SUCCESS_STYLE if total_passed == total_run else WARNING_STYLE,
        padding=(1, 2)
    )
    console.print(panel)

def print_test_summary_table(test_results: List[Dict[str, Any]]):
    table = Table(title="[bold]Test Results Summary[/bold]", box=ROUNDED)
    table.add_column("Case", style="cyan", width=8)
    table.add_column("Status", style="bold", width=10)
    table.add_column("Time", style="green", width=10)
    table.add_column("Memory", style="blue", width=10)

    for result in test_results:
        status = (
            "[green]✓ PASSED[/green]" if result["passed"]
            else "[red]✗ FAILED[/red]" if not result.get("error", False)
            else "[red]✗ ERROR[/red]"
        )
        time_str = format_time(result["exec_time_ms"] / 1000) if result["exec_time_ms"] else "N/A"
        mem_str = format_memory(result["mem_bytes"]) if result["mem_bytes"] else "N/A"
        table.add_row(
            str(result["case_num"]),
            status,
            time_str,
            mem_str
        )
    console.print(table)


# ==============================================================================
# Profiling Output
# ==============================================================================

def print_profile_result(
    case_num: int,
    iterations: int,
    avg_time: str,
    min_time: str,
    max_time: str,
    avg_mem_str: str,
    max_peak_mem_str: str,
    profile_stdout: Optional[str]
):
    """Display profiling results in a formatted table."""
    table = _create_table(
        title=f"[bold]Test Case {case_num}: {iterations} iterations[/bold]"
    )
    
    table.add_column("Metric", style=CYAN_STYLE, width=20)
    table.add_column("Value", style=SUCCESS_STYLE)
    
    table.add_row("Average Time", avg_time)
    table.add_row("Min Time", min_time)
    table.add_row("Max Time", max_time)
    table.add_row("Average Memory", avg_mem_str)
    table.add_row("Max Peak Memory", max_peak_mem_str)
    
    console.print(table)
    _print_stdout_sample_panel(profile_stdout)

def print_profile_summary(total_profiled: int, selected: int, total: int):
    """Display profiling summary in a panel."""
    summary_content = Text.assemble(
        ("Profiled: ", BOLD_STYLE + YELLOW_STYLE),
        (str(total_profiled), INFO_STYLE + BOLD_STYLE),
        (" of ", "default"),
        (str(selected), INFO_STYLE + BOLD_STYLE),
        (" selected test cases ", "default"),
        ("(", DIM_STYLE),
        (str(total), INFO_STYLE),
        (" total)", DIM_STYLE)
    )
    
    console.print(_create_panel(summary_content, padding=(1, 2)))

def print_profile_summary_table(profiled_results: List[Dict[str, Any]]):
    table = Table(title="[bold]Profiling Summary[/bold]", box=ROUNDED)
    table.add_column("Case", style="cyan", width=8)
    table.add_column("Avg Time", style="green", width=15)
    table.add_column("Min Time", style="green", width=15)
    table.add_column("Max Time", style="green", width=15)
    table.add_column("Avg Mem", style="blue", width=15)
    table.add_column("Max Mem", style="blue", width=15)
    table.add_column("Iterations", style="magenta", width=10)

    for result in profiled_results:
        table.add_row(
            str(result["case_num"]),
            format_time(result["avg_time"] / 1000) if result["avg_time"] is not None else "N/A",
            format_time(result["min_time"] / 1000) if result["min_time"] is not None else "N/A",
            format_time(result["max_time"] / 1000) if result["max_time"] is not None else "N/A",
            format_memory(int(result["avg_mem_bytes"])) if result["avg_mem_bytes"] is not None else "N/A",
            format_memory(int(result["max_mem_bytes"])) if result["max_mem_bytes"] is not None else "N/A",
            str(result["iterations"]),
        )
    console.print(table)


# ==============================================================================
# Complexity Analysis Output
# ==============================================================================

def print_complexity_header():
    """Print complexity analysis header."""
    console.print()
    console.print(_create_panel(
        "[bold]COMPLEXITY ANALYSIS RESULTS[/bold]",
    ))

def print_complexity_method(method_name: str, analysis: Dict[str, Any]):
    """Display complexity analysis for a method."""
    tree = Tree(f"[bold blue]Method: {method_name}[/bold blue]")
    
    tree.add(f"[cyan]Time Complexity: {analysis['time_complexity']}[/cyan]")
    tree.add(f"[cyan]Space Complexity: {analysis['space_complexity']}[/cyan]")
    
    console.print(_create_panel(tree, padding=(1, 2)))
    
    if analysis.get('explanation'):
        console.print(_create_panel(
            analysis['explanation'],
            title="[blue]Explanation[/blue]",
            padding=(1, 2)
        ))

def print_complexity_footer():
    """Print complexity analysis footer."""
    console.print(Rule(style=INFO_STYLE))

# Rest of the functions remain the same...

# ==============================================================================
# Snapshot / History Output
# ==============================================================================

def print_snapshot_list(snapshots: List[Dict[str, Any]], language: str, challenge_path: str):
    """Display a list of snapshots in a table."""
    table = _create_table(
        title=f"[bold]Solution History: {challenge_path} ({language})[/bold]"
    )
    table.add_column("Snapshot ID", style=CYAN_STYLE, width=12)
    table.add_column("Age", style=INFO_STYLE, width=10)
    table.add_column("Tag", style=YELLOW_STYLE, width=12)
    table.add_column("Comment", style=WHITE_STYLE, width=40, overflow="fold")
    
    for snapshot in snapshots:
        created_at = snapshot['created_at']
        table.add_row(
            snapshot['id'],
            format_relative_time(created_at),
            snapshot.get('tag', ''),
            snapshot.get('comment', '')
        )
    console.print(table)

def print_snapshot_comparison(snapshot1_info: Dict[str, Any], snapshot2_info: Dict[str, Any], diff_lines: List[str]):
    """Display a comparison between two snapshots."""
    # Create header with snapshot info
    header_columns = Columns([
        _create_panel(
            f"[bold]Snapshot 1[/bold]\n{snapshot1_info['id']}\n{snapshot1_info['created_at']}"
        ),
        _create_panel(
            f"[bold]Snapshot 2[/bold]\n{snapshot2_info['id']}\n{snapshot2_info['created_at']}"
        )
    ])
    console.print(header_columns)
    
    # Display diff
    if diff_lines:
        syntax = Syntax(
            "\n".join(diff_lines),
            "diff",
            theme="monokai",
            line_numbers=True
        )
        console.print(_create_panel(
            syntax,
            title="[bold]Differences[/bold]",
            border_style=YELLOW_STYLE,
            padding=(1, 1)
        ))
    else:
        console.print(_create_panel(
            "[green]No differences found between the snapshots.[/green]",
            border_style=SUCCESS_STYLE
        ))

def print_performance_comparison(performance_data: Dict[int, Dict[str, Any]]):
    """Display performance comparison between snapshots."""
    table = _create_table(title="[bold]Performance Comparison[/bold]")
    
    table.add_column("Case", style=CYAN_STYLE, width=8)
    table.add_column("Snap 1 Time", style=SUCCESS_STYLE, width=15)
    table.add_column("Snap 2 Time", style=SUCCESS_STYLE, width=15)
    table.add_column("Time Diff %", style=YELLOW_STYLE, width=12)
    table.add_column("Snap 1 Mem", style=INFO_STYLE, width=15)
    table.add_column("Snap 2 Mem", style=INFO_STYLE, width=15)
    table.add_column("Mem Diff %", style=YELLOW_STYLE, width=12)
    
    for case_num, data in performance_data.items():
        time_diff_pct = data.get('time_diff_pct', 0)
        mem_diff_pct = data.get('mem_diff_pct', 0)
        
        time_diff_color = "green" if time_diff_pct < 0 else "red" if time_diff_pct > 0 else "white"
        mem_diff_color = "green" if mem_diff_pct < 0 else "red" if mem_diff_pct > 0 else "white"
        
        table.add_row(
            str(case_num),
            data.get('time1_str', 'N/A'),
            data.get('time2_str', 'N/A'),
            f"[{time_diff_color}]{data.get('time_diff_str', 'N/A')}[/{time_diff_color}]",
            data.get('mem1_str', 'N/A'),
            data.get('mem2_str', 'N/A'),
            f"[{mem_diff_color}]{data.get('mem_diff_str', 'N/A')}[/{mem_diff_color}]"
        )
    
    console.print(table)

# ==============================================================================
# Visualization Output
# ==============================================================================

def print_visualization_generated(path: str):
    """Display success message for visualization generation."""
    content = Text.assemble(
        ("✓", SUCCESS_STYLE),
        " Visualization generated successfully!\n\n",
        ("File: ", INFO_STYLE), f"{path}\n\n",
        ("The visualization has been opened in your default browser.", DIM_STYLE)
    )
    console.print(_create_panel(
        content,
        title="[green]Success[/green]",
        border_style=SUCCESS_STYLE,
        padding=(1, 2)
    ))

# ==============================================================================
# Backwards Compatibility
# ==============================================================================

# Deprecated: Use print_failure for operation failures, print_test_error for test errors
print_fail = print_failure
print_error = print_test_error  # This is what tester.py imports

# ==============================================================================
# Progress Indicator
# ==============================================================================

def get_progress_context(description: str) -> Progress:
    """Get a Rich Progress context manager for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    )