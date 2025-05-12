# output.py - Enhanced version using Rich
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree
from rich.text import Text
from rich.style import Style
from rich.rule import Rule
from rich.columns import Columns
from rich.box import ROUNDED
from rich import print as rprint
from typing import Optional, List, Dict

console = Console()

# Define custom styles
SUCCESS_STYLE = Style(color="green", bold=True)
FAIL_STYLE = Style(color="red", bold=True)
WARNING_STYLE = Style(color="yellow", bold=True)
INFO_STYLE = Style(color="blue", bold=True)
BOLD_STYLE = Style(bold=True)

def print_banner():
    """Print a beautiful banner using Rich."""
    banner = Panel.fit(
        "[bold yellow]Challenge Testing CLI[/bold yellow]\n[dim]Modern coding challenge testing tool[/dim]",
        border_style="blue",
        padding=(1, 2),
        box=ROUNDED
    )
    console.print(banner)

def print_divider(title: Optional[str] = None):
    """Print a styled divider with optional title."""
    if title:
        console.print(Rule(title, style="blue"))
    else:
        console.print(Rule(style="blue"))

def print_test_case_result(
    case_num,
    passed,
    exec_time,
    memory,
    result,
    expected,
    stdout,
    input_values=None,
    detailed=False
):
    """Display test case results in a formatted table or panel."""
    status_icon = "✓" if passed else "✗"
    status_text = Text(f"{status_icon} {'PASSED' if passed else 'FAILED'}", 
                      style="green bold" if passed else "red bold")
    
    # Create summary panel
    summary = Text.assemble(
        ("Test Case ", "yellow"),
        (str(case_num), "yellow bold"),
        (": ", "default"),
        status_text,
        (" (", "dim"),
        (exec_time, "cyan"),
        (", ", "dim"),
        (memory, "cyan"),
        (")", "dim")
    )
    
    if detailed or not passed:
        # Create detailed table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="blue", width=12)
        table.add_column("Value")
        
        if input_values is not None:
            table.add_row("Input:", str(input_values))
        table.add_row("Expected:", str(expected))
        table.add_row("Output:", str(result))
        
        # Create panel with summary and table
        content = summary + "\n\n" + table
        panel = Panel(
            content,
            border_style="green" if passed else "red",
            padding=(0, 1)
        )
        console.print(panel)
    else:
        console.print(summary)
    
    if stdout:
        console.print(Panel(
            stdout,
            title="[magenta]Stdout[/magenta]",
            border_style="magenta",
            padding=(0, 1)
        ))

def print_error(
    case_num,
    error_msg,
    lineno=None,
    line_content=None,
    stdout=None,
    detailed=False,
    traceback_str=None
):
    """Display error information in a formatted panel."""
    error_content = Text.assemble(
        ("Test Case ", "yellow"),
        (str(case_num), "yellow bold"),
        (": ", "default"),
        ("✗ ERROR", "red bold"),
        ("\n\n", "default"),
        (error_msg, "red")
    )
    
    if lineno and line_content:
        error_content.append(f"\n\nat line {lineno}: ", style="yellow")
        error_content.append(line_content, style="white")
    
    panel = Panel(
        error_content,
        title="[red]Error[/red]",
        border_style="red",
        padding=(1, 2)
    )
    console.print(panel)
    
    if detailed and traceback_str:
        syntax = Syntax(traceback_str, "python", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[red]Traceback[/red]", border_style="red"))
    
    if stdout:
        console.print(Panel(
            stdout,
            title="[magenta]Stdout before error[/magenta]",
            border_style="magenta",
            padding=(0, 1)
        ))

def print_profile_result(
    case_num,
    iterations,
    avg_time,
    min_time,
    max_time,
    avg_mem_str,
    max_peak_mem_str,
    profile_stdout
):
    """Display profiling results in a formatted table."""
    table = Table(
        title=f"[bold]Test Case {case_num}: {iterations} iterations[/bold]",
        box=ROUNDED,
        show_header=True,
        header_style="bold blue"
    )
    
    table.add_column("Metric", style="cyan", width=20)
    table.add_column("Value", style="green")
    
    table.add_row("Average Time", avg_time)
    table.add_row("Min Time", min_time)
    table.add_row("Max Time", max_time)
    table.add_row("Average Memory", avg_mem_str)
    table.add_row("Max Peak Memory", max_peak_mem_str)
    
    console.print(table)
    
    if profile_stdout:
        lines = profile_stdout.splitlines()
        sample_content = "\n".join(lines[:5])
        if len(lines) > 5:
            sample_content += f"\n[dim]... ({len(lines) - 5} more lines)[/dim]"
        
        console.print(Panel(
            sample_content,
            title="[magenta]Stdout Sample[/magenta]",
            border_style="magenta",
            padding=(0, 1)
        ))

def print_summary(total_passed, total_run, selected, total):
    """Display test summary with progress visualization."""
    # Create progress bar visualization
    progress_bar = Progress(
        TextColumn("[bold]{task.description}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )
    
    with progress_bar:
        task = progress_bar.add_task(
            f"Tests Passed",
            total=total_run,
            completed=total_passed
        )
    
    # Create summary panel
    summary_content = Text.assemble(
        ("Summary: ", "bold yellow"),
        ("Passed ", "default"),
        (str(total_passed), "green bold"),
        ("/", "default"),
        (str(total_run), "blue bold"),
        (" test cases ", "default"),
        ("(out of ", "dim"),
        (str(selected), "blue"),
        (" selected, ", "dim"),
        (str(total), "blue"),
        (" total)", "dim")
    )
    
    panel = Panel(
        summary_content,
        border_style="green" if total_passed == total_run else "yellow",
        padding=(1, 2),
        box=ROUNDED
    )
    console.print(panel)

def print_profile_summary(total_profiled, selected, total):
    """Display profiling summary in a panel."""
    summary_content = Text.assemble(
        ("Profiled: ", "bold yellow"),
        (str(total_profiled), "blue bold"),
        (" of ", "default"),
        (str(selected), "blue bold"),
        (" selected test cases ", "default"),
        ("(", "dim"),
        (str(total), "blue"),
        (" total)", "dim")
    )
    
    panel = Panel(
        summary_content,
        border_style="blue",
        padding=(1, 2),
        box=ROUNDED
    )
    console.print(panel)

def print_info(msg):
    """Print an informational message."""
    console.print(f"[blue]ℹ[/blue]  {msg}")

def print_warning(msg):
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow]  [yellow]{msg}[/yellow]")

def print_success(msg):
    """Print a success message."""
    console.print(f"[green]✓[/green]  [green]{msg}[/green]")

def print_fail(msg):
    """Print a failure message."""
    console.print(f"[red]✗[/red]  [red]{msg}[/red]")

def print_complexity_header():
    """Print complexity analysis header."""
    console.print()
    console.print(Panel.fit(
        "[bold]COMPLEXITY ANALYSIS RESULTS[/bold]",
        border_style="blue",
        box=ROUNDED
    ))

def print_complexity_method(method_name, analysis):
    """Display complexity analysis for a method."""
    tree = Tree(f"[bold blue]Method: {method_name}[/bold blue]")
    
    time_branch = tree.add(f"[cyan]Time Complexity: {analysis['time_complexity']}[/cyan]")
    space_branch = tree.add(f"[cyan]Space Complexity: {analysis['space_complexity']}[/cyan]")
    
    console.print(Panel(tree, border_style="blue", padding=(1, 2)))
    
    if analysis['explanation']:
        console.print(Panel(
            analysis['explanation'],
            title="[blue]Explanation[/blue]",
            border_style="blue",
            padding=(1, 2)
        ))

def print_complexity_footer():
    """Print complexity analysis footer."""
    console.print(Rule(style="blue"))

# NEW: Additional fancy output functions

def print_snapshot_list(snapshots: List[Dict], language: str, challenge_path: str):
    """Display a list of snapshots in a table."""
    table = Table(
        title=f"[bold]Solution History: {challenge_path} ({language})[/bold]",
        box=ROUNDED,
        show_header=True,
        header_style="bold blue"
    )
    
    table.add_column("Snapshot ID", style="cyan", width=25)
    table.add_column("Created", style="green", width=20)
    table.add_column("Tag", style="yellow", width=15)
    table.add_column("Comment", style="white", width=40)
    
    for snapshot in snapshots:
        table.add_row(
            snapshot['id'],
            snapshot['created_at'],
            snapshot.get('tag', ''),
            snapshot.get('comment', '')
        )
    
    console.print(table)

def print_snapshot_comparison(snapshot1_info: Dict, snapshot2_info: Dict, diff_lines: List[str]):
    """Display a comparison between two snapshots."""
    # Create header with snapshot info
    header_columns = Columns([
        Panel(
            f"[bold]Snapshot 1[/bold]\n{snapshot1_info['id']}\n{snapshot1_info['created_at']}",
            border_style="blue"
        ),
        Panel(
            f"[bold]Snapshot 2[/bold]\n{snapshot2_info['id']}\n{snapshot2_info['created_at']}",
            border_style="blue"
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
        console.print(Panel(
            syntax,
            title="[bold]Differences[/bold]",
            border_style="yellow",
            padding=(1, 1)
        ))
    else:
        console.print(Panel(
            "[green]No differences found between the snapshots.[/green]",
            border_style="green"
        ))

def print_performance_comparison(performance_data: Dict):
    """Display performance comparison between snapshots."""
    table = Table(
        title="[bold]Performance Comparison[/bold]",
        box=ROUNDED,
        show_header=True,
        header_style="bold blue"
    )
    
    table.add_column("Case", style="cyan", width=8)
    table.add_column("Snapshot 1 Time", style="green", width=15)
    table.add_column("Snapshot 2 Time", style="green", width=15)
    table.add_column("Diff %", style="yellow", width=10)
    table.add_column("Snapshot 1 Mem", style="blue", width=15)
    table.add_column("Snapshot 2 Mem", style="blue", width=15)
    table.add_column("Diff %", style="yellow", width=10)
    
    for case_num, data in performance_data.items():
        time_diff_color = "green" if data['time_diff_pct'] < 0 else "red" if data['time_diff_pct'] > 0 else "white"
        mem_diff_color = "green" if data['mem_diff_pct'] < 0 else "red" if data['mem_diff_pct'] > 0 else "white"
        
        table.add_row(
            str(case_num),
            data['time1_str'],
            data['time2_str'],
            f"[{time_diff_color}]{data['time_diff_str']}[/{time_diff_color}]",
            data['mem1_str'],
            data['mem2_str'],
            f"[{mem_diff_color}]{data['mem_diff_str']}[/{mem_diff_color}]"
        )
    
    console.print(table)

def print_visualization_generated(path: str):
    """Display success message for visualization generation."""
    console.print(Panel(
        f"[green]✓[/green] Visualization generated successfully!\n\n[blue]File:[/blue] {path}\n\n[dim]The visualization has been opened in your default browser.[/dim]",
        title="[green]Success[/green]",
        border_style="green",
        padding=(1, 2)
    ))

# Progress context manager for long-running operations
def get_progress_context(description: str):
    """Get a progress context manager for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    )