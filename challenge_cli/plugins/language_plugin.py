import json
import os
from abc import ABC, abstractmethod
from typing import List, Tuple

from challenge_cli.core.config import ChallengeConfig, get_config
from challenge_cli.plugins.docker_utils import (
    ensure_docker_image,
    execute_in_container,
    start_hot_container,
)


class LanguagePlugin(ABC):
    """
    Base class for all language plugins with common template functionality.

    Each plugin must implement or override the following:

    Attributes:
        name (str): Unique string identifier for the language (e.g., "python").
        docker_image (str): The Docker image tag to use for this language.
        dockerfile_path (str): Path to the Dockerfile for this language.
        solution_filename (str): The expected filename for the user's solution (e.g., "solution.py").
    """

    name: str = "base"
    aliases: List[str] = []  # Language aliases
    docker_image: str = None
    dockerfile_path: str = None
    solution_filename: str = None

    # Common markers used across all languages
    ERROR_MARKER = "PROFILE_ERROR:"
    FUNCTION_ERROR_MARKER = "FUNCTION_ERROR:"
    SEPARATOR = "---SEPARATOR---"
    END_OUTPUT = "---END_OUTPUT---"

    @staticmethod
    @abstractmethod
    def solution_template(function_name="solve"):
        """
        Return a string with the default solution template for this language.

        Args:
            function_name (str): The function/method name to use in the template.

        Returns:
            str: The code template as a string.
        """
        pass

    @abstractmethod
    def generate_test_driver_template(self, function_name: str) -> str:
        """
        Generate the test driver template for batch execution.
        Must be implemented by subclasses for language-specific needs.

        Args:
            function_name: Name of the function to test

        Returns:
            String containing the test driver code
        """
        pass

    @abstractmethod
    def _parse_single_case_output(
        self, case_output: str, stderr: str, exit_code: int, case_index: int
    ) -> Tuple:
        """
        Parse output for a single test case in batch execution.
        Must be implemented by subclasses.

        Args:
            case_output: Output for a single test case
            stderr: Error output for the entire batch
            exit_code: Exit code of the process
            case_index: Index of the test case in the batch

        Returns:
            Tuple of (result, stdout, stderr, exit_code, exec_time,
                     max_rss_kb, profile_info)
        """
        pass

    def ensure_image(self):
        """
        Ensure the Docker image for this plugin is available.
        Builds the image if it does not exist.
        """
        ensure_docker_image(
            self.docker_image,
            self.dockerfile_path,
            context_dir=os.path.dirname(self.dockerfile_path),
        )

    def run_many(
        self,
        workdir: str,
        function_name: str,
        input_args_list: list,
    ) -> list:
        """
        Template method: Run multiple test cases efficiently.

        Args:
            workdir (str): Path to the language-specific directory.
            function_name (str): Name of the function/method to call.
            input_args_list (list of list): Arguments for each test case.

        Returns:
            list of tuple: Each tuple contains:
                result (any): Parsed return value from the function.
                extra_stdout (str): Any extra stdout (may be empty).
                stderr (str): Stderr from the process.
                exit_code (int): Process exit code.
                exec_time (float or None): Wall time for the run (seconds), or None.
                max_rss_kb (int or None): Max memory used (KB), or None.
                profile_info (dict or None): Function-only profiling info.
        """
        self.ensure_image()

        # Get configuration
        config = get_config()

        # Prepare paths
        container_name = self._container_name(workdir)
        problems_dir = self._get_problems_dir(workdir)
        cache_dir = str(config.get_cache_dir())

        # Start container
        start_hot_container(
            self.docker_image,
            workdir,
            container_name,
            problems_dir=problems_dir,
            cache_dir=cache_dir,
        )

        # Handle dependencies - Hook method (optional)
        self._handle_dependencies(workdir, container_name, config)

        inputs_json_path = os.path.join(workdir, "inputs.json")
        driver_path = os.path.join(workdir, self._get_driver_filename())

        try:
            # Write inputs
            with open(inputs_json_path, "w") as f:
                json.dump(input_args_list, f)

            # Write driver
            driver_code = self.generate_test_driver_template(function_name)
            with open(driver_path, "w") as f:
                f.write(driver_code)

            # Execute
            container_workdir = self._get_container_workdir(workdir)
            command = self._get_batch_command(driver_path)
            stdout, stderr, exit_code = execute_in_container(
                container_name, command, working_dir=container_workdir, input_data=None
            )

            # Parse results using common helper
            return self._parse_batch_output(stdout, stderr, exit_code, input_args_list)

        finally:
            self._cleanup_files(inputs_json_path, driver_path)

    def _handle_dependencies(
        self, workdir: str, container_name: str, config: ChallengeConfig
    ) -> None:
        """
        Handle language-specific dependencies. Default is no-op.
        Override in subclasses if needed.

        Args:
            workdir: Path to language-specific directory
            container_name: Name of the Docker container
            config: Configuration object
        """
        pass  # Default implementation does nothing

    @abstractmethod
    def _get_batch_command(self, driver_path: str) -> list:
        """
        Get the command to run for batch testing.
        Must be implemented by subclasses.

        Args:
            driver_path: Path to the driver file

        Returns:
            List of command arguments
        """
        pass

    @abstractmethod
    def _get_driver_filename(self) -> str:
        """
        Get the filename for the test driver file.

        Returns:
            String with the driver filename
        """
        pass

    def _parse_batch_output(
        self, stdout: str, stderr: str, exit_code: int, batch_inputs: list
    ) -> List[Tuple]:
        """
        Common batch output parsing logic.

        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
            batch_inputs: List of batch inputs

        Returns:
            List of result tuples, each containing:
            (result, stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info)
        """
        final_results = []

        # Check for critical errors
        if exit_code != 0 and self.ERROR_MARKER in stderr:
            final_results.append(
                (
                    "Batch execution failed due to driver error",
                    "",
                    stderr,
                    exit_code,
                    None,
                    None,
                    None,
                )
            )
            return final_results

        if not stdout or self.END_OUTPUT not in stdout:
            error_message = "Execution failed or malformed output (missing end marker)"
            if stdout and stdout.strip():
                error_message += f"\nStdout: {stdout}"
            if stderr and stderr.strip():
                error_message += f"\nStderr: {stderr}"
            final_results.append(
                (error_message, "", stderr, exit_code, None, None, None)
            )
            return final_results

        # Extract main output
        main_output = stdout.split(self.END_OUTPUT)[0].strip()
        case_outputs = main_output.split(self.SEPARATOR)

        # Parse each case
        for i, case_output in enumerate(case_outputs):
            if not case_output.strip():
                continue

            if i >= len(batch_inputs):
                break

            result = self._parse_single_case_output(
                case_output.strip(), stderr, exit_code, i
            )
            final_results.append(result)

        # Fill in missing results
        while len(final_results) < len(batch_inputs):
            final_results.append(
                (
                    "Test case did not run or produce output",
                    "",
                    stderr,
                    exit_code,
                    None,
                    None,
                    None,
                )
            )

        return final_results[: len(batch_inputs)]

    def _container_name(self, workdir):
        """Generate a container name based on language and configuration."""
        config = get_config()

        if config.docker.container_sharing == "per-language":
            # Shared container for all challenges in this language
            return f"challenge-cli-{self.name}"
        else:
            # Per-challenge container (legacy behavior)
            language_dir = os.path.abspath(workdir)
            challenge_dir = os.path.dirname(language_dir)
            platform = os.path.basename(os.path.dirname(challenge_dir))
            challenge_path = os.path.basename(challenge_dir)

            # Make challenge path safe for use in container name
            safe_challenge = challenge_path.replace("/", "-").replace("\\", "-")

            return f"challenge-cli-{platform}-{safe_challenge}-{self.name}"

    def _get_problems_dir(self, workdir: str) -> str:
        """Get the problems directory root."""
        # workdir is language-specific dir, go up to problems root
        language_dir = os.path.abspath(workdir)
        challenge_dir = os.path.dirname(language_dir)
        platform_dir = os.path.dirname(challenge_dir)
        problems_dir = os.path.dirname(platform_dir)
        return problems_dir

    def _to_container_path(self, host_path: str, problems_dir: str) -> str:
        """Convert host path to container path."""
        abs_path = os.path.abspath(host_path)
        abs_problems = os.path.abspath(problems_dir)

        if abs_path.startswith(abs_problems):
            rel_path = os.path.relpath(abs_path, abs_problems)
            return f"/workspace/{rel_path}"
        else:
            # Path is outside problems directory
            return abs_path

    def _get_container_workdir(self, workdir: str) -> str:
        """Get the working directory path inside the container."""
        problems_dir = self._get_problems_dir(workdir)
        return self._to_container_path(workdir, problems_dir)

    def _cleanup_files(self, *file_paths):
        """Remove temporary files, ignoring errors."""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass

    def _create_error_results(
        self, num_inputs: int, stdout: str, stderr: str, exit_code: int
    ) -> List[Tuple]:
        """Create error results for all inputs when batch execution fails."""
        return [
            (None, stdout, stderr, exit_code, None, None, None)
            for _ in range(num_inputs)
        ]

    def get_cache_key(self, workdir: str) -> str:
        """Get a cache key for this solution."""
        # Default implementation - subclasses can override
        solution_path = os.path.join(workdir, self.solution_filename)
        if os.path.exists(solution_path):
            stat = os.stat(solution_path)
            return f"{self.name}_{stat.st_mtime}_{stat.st_size}"
        return f"{self.name}_nocache"
