import datetime


def format_time(seconds: float) -> str:
    """
    Format time in the most appropriate unit:
    - <1μs: ns
    - <1ms: μs
    - <1s: ms
    - >=1s: s
    Args:
        seconds: Time in seconds
    Returns:
        Formatted time string with unit
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
    """
    Format an ISO timestamp as relative time.
    Args:
        iso_str: ISO format timestamp string
    Returns:
        Relative time string (e.g., "5m ago")
    """
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
    """
    Format memory size in appropriate units.
    Args:
        bytes_value: Memory size in bytes
    Returns:
        Formatted memory string with unit
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024 or unit == "GB":
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} GB"
