import json
import datetime
import os
from typing import Any, Dict, Set, List, Optional, Union

from challenge_cli.core import constants
from challenge_cli.core.config import DEFAULT_FUNCTION_NAME
from challenge_cli.core.constants import LANGUAGE_ALIASES, SOLUTION_TEMPLATES, SUPPORTED_LANGUAGES
from challenge_cli.core.exceptions import ConfigurationError
from challenge_cli.plugins import get_plugin

# --- Formatting ---

def format_time(seconds: float) -> str:
    """
    Format time in the most appropriate unit:
    - <1μs: ns
    - <1ms: μs
    - <1s: ms
    - >=1s: s
    """
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.6f} s"


def format_relative_time(iso_str: str) -> str:
    """Format an ISO timestamp as relative time."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        now = datetime.datetime.now(dt.tzinfo)
        delta = now - dt
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except Exception:
        return "?"


def format_memory(bytes_value: int) -> str:
    """Format memory size in appropriate units."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024 or unit == 'GB':
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} GB"


# --- JSON Handling ---

def load_json(file_path: str, default: Optional[Union[List, Dict]] = None) -> Union[List, Dict]:
    """Load JSON data from a file, returning a default value if it doesn't exist or is invalid."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except json.JSONDecodeError as e:
        # Handle corrupted JSON file
        print(f"Warning: Could not decode JSON from {file_path}: {e}")
        return default if default is not None else {}


def save_json(file_path: str, data: Union[List, Dict]) -> None:
    """Save data to a JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Error: Could not write JSON to {file_path}: {e}")
        raise


# --- Test Case Handling ---

def parse_cases_arg(cases_arg: Optional[str], total_cases: int) -> Set[int]:
    """
    Parse a comma-separated string of numbers/ranges into a set of case indices.
    
    Examples:
        - "1,3,5-7" -> {1, 3, 5, 6, 7}
        - None -> {1, 2, ..., total_cases}
    """
    if not cases_arg:
        return set(range(1, total_cases + 1))
    
    selected_cases = set()
    parts = cases_arg.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        try:
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start <= 0 or end <= 0 or start > end:
                    print(f"Warning: Invalid range '{part}' in cases argument. Skipping.")
                    continue
                selected_cases.update(range(start, end + 1))
            else:
                case_num = int(part)
                if case_num <= 0:
                    print(f"Warning: Invalid case number '{part}' in cases argument. Skipping.")
                    continue
                selected_cases.add(case_num)
        except ValueError:
            print(f"Warning: Invalid format '{part}' in cases argument. Skipping.")
            continue
    
    # Filter out cases that are out of the valid range
    valid_selected_cases = {case for case in selected_cases if 1 <= case <= total_cases}
    if len(valid_selected_cases) != len(selected_cases):
        print(f"Warning: Some specified cases were outside the valid range (1-{total_cases}).")
    
    return valid_selected_cases


def compare_results(result: Any, expected: Any) -> bool:
    """
    Compare actual result with expected result, handling common types.
    
    - For lists, compares without considering order for simple types
    - Attempts to parse JSON strings before comparison
    """
    # Attempt to parse expected if it's a string that looks like JSON
    if isinstance(expected, str):
        try:
            if (expected.startswith('{') and expected.endswith('}')) or \
               (expected.startswith('[') and expected.endswith(']')):
                expected = json.loads(expected)
        except json.JSONDecodeError:
            pass  # Keep original string if not valid JSON
    
    # Attempt to parse result if it's a string that looks like JSON
    if isinstance(result, str):
        try:
            if (result.startswith('{') and result.endswith('}')) or \
               (result.startswith('[') and result.endswith(']')):
                result = json.loads(result)
        except json.JSONDecodeError:
            pass
    
    # Handle list comparison: order might not matter for lists of simple types
    if isinstance(result, list) and isinstance(expected, list):
        if len(result) != len(expected):
            return False
        
        # Check if lists contain only comparable simple types
        try:
            # For sets/lists where order doesn't matter
            # This handles cases like [1, 2] vs [2, 1] correctly
            # Note: This might not be suitable for lists where order *does* matter
            return set(map(str, result)) == set(map(str, expected))
        except TypeError:
            # Fallback to order-sensitive comparison if elements are not hashable
            return result == expected
    
    # General comparison for other types
    return result == expected


def parse_result(stdout: str) -> Any:
    """
    Attempt to parse stdout as JSON, otherwise return stripped string.
    """
    stdout_stripped = stdout.strip()
    try:
        if (stdout_stripped.startswith('{') and stdout_stripped.endswith('}')) or \
           (stdout_stripped.startswith('[') and stdout_stripped.endswith(']')):
            return json.loads(stdout_stripped)
        else:
            return stdout_stripped
    except json.JSONDecodeError:
        return stdout_stripped
