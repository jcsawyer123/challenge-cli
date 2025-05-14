"""
Autocompletion functions for Challenge CLI.
"""

import os
from typing import List

from challenge_cli.core.config import HISTORY_DIR_NAME, load_config_file


class Completions:
    """Autocompletion provider for Challenge CLI."""

    @staticmethod
    def challenges(incomplete: str) -> List[str]:
        """Complete challenge paths."""
        config = load_config_file()
        problems_dir = config.get("problems_dir", os.getcwd())
        platform = config.get("default_platform", "leetcode")

        platform_dir = os.path.join(problems_dir, platform)
        if not os.path.exists(platform_dir):
            return []

        challenges = []
        for root, dirs, _ in os.walk(platform_dir):
            if HISTORY_DIR_NAME in root or "/." in root or "/__pycache__" in root:
                continue
            rel_path = os.path.relpath(root, platform_dir)
            if rel_path != "." and not any(
                lang in rel_path.split(os.sep)
                for lang in ["python", "go", "javascript"]
            ):
                challenges.append(rel_path)
            else:
                challenges.extend(d for d in dirs if not d.startswith("."))

        return [c for c in sorted(set(challenges)) if c.startswith(incomplete)]

    @staticmethod
    def languages(incomplete: str) -> List[str]:
        """Complete language options."""
        langs = ["python", "py", "javascript", "js", "go", "golang"]
        return [lang for lang in langs if lang.startswith(incomplete.lower())]

    @staticmethod
    def snapshots(ctx, incomplete: str) -> List[str]:
        """Complete snapshot IDs."""
        challenge_path = ctx.params.get("challenge_path", "")
        if not challenge_path:
            return []

        config = load_config_file()
        problems_dir = config.get("problems_dir", os.getcwd())
        platform = ctx.params.get("platform") or config.get(
            "default_platform", "leetcode"
        )

        history_dir = os.path.join(
            problems_dir, platform, challenge_path, HISTORY_DIR_NAME
        )
        snapshots_dir = os.path.join(history_dir, "snapshots")
        if not os.path.exists(snapshots_dir):
            return []

        return sorted(
            [
                item
                for item in os.listdir(snapshots_dir)
                if incomplete.lower() in item.lower()
            ]
        )
