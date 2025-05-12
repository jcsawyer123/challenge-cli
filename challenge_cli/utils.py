import os
import json
from typing import Any, Dict, Set, List, Optional, Union
import datetime

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

# --- JSON Handling (from history_manager.py) ---

def load_json(file_path: str, default: Optional[Union[List, Dict]] = None) -> Union[List, Dict]:
    """Load JSON data from a file, returning a default value if it doesn't exist or is invalid."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except json.JSONDecodeError as e:
        # Handle corrupted JSON file - Consider logging this error
        print(f"Warning: Could not decode JSON from {file_path}: {e}")
        return default if default is not None else {}

def save_json(file_path: str, data: Union[List, Dict]) -> None:
    """Save data to a JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        # Handle potential write errors - Consider logging this error and potentially raising it
        print(f"Error: Could not write JSON to {file_path}: {e}")
        # Or raise a custom exception: raise UtilsError(f"Failed to save JSON to {file_path}") from e

# --- Test Case Handling (from tester.py) ---

def parse_cases_arg(cases_arg: Optional[str], total_cases: int) -> Set[int]:
    """Parse a comma-separated string of numbers/ranges into a set of case indices."""
    if not cases_arg:
        return set(range(1, total_cases + 1))
    selected_cases = set()
    parts = cases_arg.split(',')
    for part in parts:
        part = part.strip() # Handle potential whitespace
        if not part: continue # Skip empty parts
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
             continue # Skip parts that are not valid numbers or ranges

    # Filter out cases that are out of the valid range [1, total_cases]
    valid_selected_cases = {case for case in selected_cases if 1 <= case <= total_cases}
    if len(valid_selected_cases) != len(selected_cases):
         print(f"Warning: Some specified cases were outside the valid range (1-{total_cases}).")

    return valid_selected_cases


def compare_results(result: Any, expected: Any) -> bool:
    """Compare actual result with expected result, handling common types."""
    # Attempt to parse expected if it's a string that looks like JSON
    if isinstance(expected, str):
        try:
            # More robust check: does it start/end with {} or []?
            if (expected.startswith('{') and expected.endswith('}')) or \
               (expected.startswith('[') and expected.endswith(']')):
                parsed_expected = json.loads(expected)
                # Use parsed version only if successful
                expected = parsed_expected
        except json.JSONDecodeError:
            pass # Keep original string if not valid JSON

    # Handle list comparison: order might not matter for lists of simple types
    if isinstance(result, list) and isinstance(expected, list):
        if len(result) != len(expected):
            return False
        # Check if lists contain only comparable simple types (int, float, str, bool, None)
        # Using sets for order-insensitive comparison of simple types
        try:
            # Convert elements to a comparable form (e.g., str) if mixed types exist
            # This handles cases like [1, 2] vs [2, 1] correctly
            # Note: This might not be suitable for lists where order *does* matter
            # or lists containing complex nested structures.
            # Consider adding a flag or more sophisticated comparison if needed.
            return set(map(str, result)) == set(map(str, expected))
        except TypeError:
             # Fallback to order-sensitive comparison if elements are not hashable/comparable for sets
             return result == expected
    # General comparison for other types
    return result == expected


def parse_result(stdout: str) -> Any:
    """Attempt to parse stdout as JSON, otherwise return stripped string."""
    stdout_stripped = stdout.strip()
    try:
        # More robust check: does it start/end with {} or []?
        if (stdout_stripped.startswith('{') and stdout_stripped.endswith('}')) or \
           (stdout_stripped.startswith('[') and stdout_stripped.endswith(']')):
            return json.loads(stdout_stripped)
        else:
             # Return the stripped string if it doesn't look like JSON
             return stdout_stripped
    except json.JSONDecodeError:
        # Return the stripped string if JSON parsing fails
        return stdout_stripped

# --- Config & Language Handling (from cli.py) ---

def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from standard locations or a specified path."""
    config_paths = [
        config_path, # Explicit path first
        os.path.join(os.getcwd(), "challenge_cli_config.json"), # CWD
        os.path.expanduser("~/.challenge_cli_config.json"), # Home dir
    ]
    for path in config_paths:
        if path and os.path.exists(path):
            try:
                # Use the robust load_json helper
                config_data = load_json(path)
                if isinstance(config_data, dict): # Ensure it loaded as a dictionary
                    return config_data
                else:
                     print(f"Warning: Config file '{path}' did not contain a valid JSON object. Skipping.")
                     continue # Try next path
            except Exception as e: # Catch potential errors during file access/parsing beyond load_json's handling
                 print(f"Warning: Error loading config file '{path}': {e}. Skipping.")
                 continue # Try next path
    return {} # Return empty dict if no valid config found


def resolve_language_shorthand(lang: Optional[str]) -> Optional[str]:
    """Resolve common language shorthands (py, js, golang) to standard names."""
    if not lang:
        return None
    mapping = {
        "python": "python", "py": "python",
        "go": "go", "golang": "go",
        "javascript": "javascript", "js": "javascript", "node": "javascript"
    }
    # Return the mapped value or the lowercased original if not in mapping
    return mapping.get(lang.lower(), lang.lower())
