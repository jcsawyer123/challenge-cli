"""Cache management utilities for challenge CLI."""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from challenge_cli.core.config import get_config
from challenge_cli.output.terminal import (
    console,
    print_info,
    print_success,
    print_warning,
)


def get_directory_size(path: Path) -> int:
    """Get the total size of a directory in bytes."""
    total_size = 0
    if path.exists():
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    return total_size


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def show_cache_info():
    """Display cache information."""
    config = get_config()
    cache_dir = config.get_cache_dir()

    if not cache_dir.exists():
        print_warning("No cache directory found")
        return

    total_size = get_directory_size(cache_dir)

    console.print(f"[bold]Cache Location:[/bold] {cache_dir}")
    console.print(f"[bold]Total Size:[/bold] {format_size(total_size)}")
    console.print()

    # Show breakdown by language
    languages = []
    for item in cache_dir.iterdir():
        if item.is_dir():
            lang_size = get_directory_size(item)
            languages.append((item.name, lang_size))

    if languages:
        console.print("[bold]Usage by Language:[/bold]")
        for lang, size in sorted(languages, key=lambda x: x[1], reverse=True):
            console.print(f"  {lang}: {format_size(size)}")


def clear_cache(language: Optional[str] = None):
    """Clear cache directory."""
    config = get_config()
    cache_dir = config.get_cache_dir()

    if not cache_dir.exists():
        print_warning("No cache directory found")
        return

    if language and language != "all":
        # Clear specific language cache
        lang_cache = cache_dir / language
        if lang_cache.exists():
            shutil.rmtree(lang_cache)
            print_success(f"Cleared {language} cache")
        else:
            print_warning(f"No cache found for {language}")
    else:
        # Clear all cache
        for item in cache_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
        print_success("Cleared all cache")


def show_cache_statistics():
    """Show detailed cache statistics."""
    config = get_config()
    cache_dir = config.get_cache_dir()

    if not cache_dir.exists():
        print_warning("No cache directory found")
        return

    stats: Dict[str, Dict] = {}

    for lang_dir in cache_dir.iterdir():
        if not lang_dir.is_dir():
            continue

        lang_stats = {
            "total_size": 0,
            "file_count": 0,
            "file_types": {},
            "oldest_file": None,
            "newest_file": None,
        }

        for root, dirs, files in os.walk(lang_dir):
            for file in files:
                filepath = Path(root) / file
                if filepath.exists():
                    file_stat = filepath.stat()
                    lang_stats["total_size"] += file_stat.st_size
                    lang_stats["file_count"] += 1

                    # Track file types
                    ext = filepath.suffix
                    if ext not in lang_stats["file_types"]:
                        lang_stats["file_types"][ext] = 0
                    lang_stats["file_types"][ext] += 1

                    # Track oldest/newest
                    if (
                        lang_stats["oldest_file"] is None
                        or file_stat.st_mtime < lang_stats["oldest_file"]
                    ):
                        lang_stats["oldest_file"] = file_stat.st_mtime
                    if (
                        lang_stats["newest_file"] is None
                        or file_stat.st_mtime > lang_stats["newest_file"]
                    ):
                        lang_stats["newest_file"] = file_stat.st_mtime

        stats[lang_dir.name] = lang_stats

    # Display statistics
    console.print("[bold]Cache Statistics:[/bold]")
    for lang, lang_stats in stats.items():
        console.print(f"\n[bold cyan]{lang}:[/bold cyan]")
        console.print(f"  Total Size: {format_size(lang_stats['total_size'])}")
        console.print(f"  File Count: {lang_stats['file_count']}")

        if lang_stats["file_types"]:
            console.print("  File Types:")
            for ext, count in sorted(lang_stats["file_types"].items()):
                console.print(f"    {ext or '(no extension)'}: {count}")

        if lang_stats["oldest_file"] and lang_stats["newest_file"]:
            import datetime

            oldest = datetime.datetime.fromtimestamp(lang_stats["oldest_file"])
            newest = datetime.datetime.fromtimestamp(lang_stats["newest_file"])
            console.print(f"  Oldest File: {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"  Newest File: {newest.strftime('%Y-%m-%d %H:%M:%S')}")


def clean_old_cache(days: int = 7):
    """Clean cache files older than specified days."""
    config = get_config()
    cache_dir = config.get_cache_dir()

    if not cache_dir.exists():
        print_warning("No cache directory found")
        return

    import time

    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 60 * 60)

    files_removed = 0
    size_freed = 0

    for root, dirs, files in os.walk(cache_dir):
        for file in files:
            filepath = Path(root) / file
            if filepath.exists():
                file_stat = filepath.stat()
                if file_stat.st_mtime < cutoff_time:
                    size_freed += file_stat.st_size
                    filepath.unlink()
                    files_removed += 1

    if files_removed > 0:
        print_success(f"Removed {files_removed} files older than {days} days")
        print_info(f"Freed {format_size(size_freed)} of disk space")
    else:
        print_info(f"No files older than {days} days found")
