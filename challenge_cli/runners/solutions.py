"""Solution file management for challenges."""

import os
import shutil

from challenge_cli.output.terminal import print_info, print_success, print_warning
from challenge_cli.plugins import get_plugin

COMPLEXITY_TEMPLATE = """{
    "time_complexity": "Not analyzed yet",
    "space_complexity": "Not analyzed yet",
    "explanation": "",
    "last_analyzed": null
}
"""


class SolutionManager:
    """Manages solution files and initialization."""

    def __init__(self, challenge_dir: str, platform: str, challenge_path: str):
        """
        Initialize solution manager.

        Args:
            challenge_dir: Path to the challenge directory
            platform: Challenge platform (leetcode, aoc, etc.)
            challenge_path: Challenge identifier
        """
        self.challenge_dir = challenge_dir
        self.platform = platform
        self.challenge_path = challenge_path

    def get_language_dir(self, language: str) -> str:
        """Get the directory for a specific language."""
        return os.path.join(self.challenge_dir, language)

    def get_solution_path(self, language: str) -> str:
        """
        Get the path to the solution file for a language.

        Args:
            language: Programming language

        Returns:
            Path to the solution file

        Raises:
            ValueError: If no plugin found for language
        """
        plugin = get_plugin(language)
        if not plugin:
            raise ValueError(f"No plugin found for language: {language}")

        language_dir = self.get_language_dir(language)
        return os.path.join(language_dir, plugin.solution_filename)

    def initialize_solution(self, language: str, function_name: str = "solve") -> None:
        """
        Initialize a solution file for a language.

        Args:
            language: Programming language
            function_name: Name of the function to create
        """
        plugin = get_plugin(language)
        if not plugin:
            raise ValueError(f"No plugin found for language: {language}")

        language_dir = self.get_language_dir(language)
        os.makedirs(language_dir, exist_ok=True)

        solution_path = os.path.join(language_dir, plugin.solution_filename)
        solution_already_exists = os.path.exists(solution_path)

        # Write solution template
        with open(solution_path, "w") as f:
            f.write(plugin.solution_template(function_name=function_name))

        # Initialize complexity file if it doesn't exist
        complexity_file = os.path.join(self.challenge_dir, "complexity.json")
        if not os.path.exists(complexity_file):
            with open(complexity_file, "w") as f:
                f.write(COMPLEXITY_TEMPLATE)

        # Log success
        if solution_already_exists:
            print_success(
                f"Updated {language} implementation for {self.platform}/{self.challenge_path}"
            )
        else:
            print_success(
                f"Added {language} implementation for {self.platform}/{self.challenge_path}"
            )

        print_info(f"-> Solution file: {solution_path}")

    def move_old_solution(self, old_language: str, old_plugin) -> None:
        """
        Move an old solution file to its proper language directory.

        Args:
            old_language: The old language
            old_plugin: Plugin for the old language
        """
        try:
            old_solution_path_in_root = os.path.join(
                self.challenge_dir, old_plugin.solution_filename
            )
            if os.path.exists(old_solution_path_in_root):
                old_language_dir = self.get_language_dir(old_language)
                os.makedirs(old_language_dir, exist_ok=True)
                new_location = os.path.join(
                    old_language_dir, old_plugin.solution_filename
                )

                if not os.path.exists(new_location):
                    shutil.move(old_solution_path_in_root, new_location)
                    print_info(
                        f"Moved existing {old_language} solution to its language directory."
                    )
        except Exception as e:
            print_warning(f"Could not move old solution file for {old_language}: {e}")
