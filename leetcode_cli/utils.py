def format_time(seconds: float) -> str:
    """Format time in appropriate units (ms or s)."""
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.6f} s"

def format_memory(bytes_value: int) -> str:
    """Format memory size in appropriate units."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024 or unit == 'GB':
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
