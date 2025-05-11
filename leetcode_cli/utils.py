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


def format_memory(bytes_value: int) -> str:
    """Format memory size in appropriate units."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024 or unit == 'GB':
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
