import os
from abc import ABC, abstractmethod
from typing import List, Tuple


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
    aliases: List[str] = []  # New: language aliases
    docker_image: str = None
    dockerfile_path: str = None
    solution_filename: str = None

    # Common markers used across all languages
    PROFILE_MARKER = "LEETCODE_PROFILE:"
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
    def ensure_image(self):
        """
        Ensure the Docker image for this plugin is available.
        Should build the image if it does not exist.
        """
        pass

    def generate_wrapper_template(self, function_name: str) -> str:
        """
        Generate the wrapper template for single test execution.
        Can be overridden by subclasses for language-specific needs.
        """
        raise NotImplementedError("Subclasses must implement generate_wrapper_template")

    def generate_test_driver_template(self, function_name: str) -> str:
        """
        Generate the test driver template for batch execution.
        Can be overridden by subclasses for language-specific needs.
        """
        raise NotImplementedError(
            "Subclasses must implement generate_test_driver_template"
        )

    @abstractmethod
    def run(self, workdir, function_name, input_args, input_data=None):
        """
        Run a single test case.

        Args:
            workdir (str): Path to the language-specific directory (mounted as /workspace).
            function_name (str): Name of the function/method to call.
            input_args (list): Arguments to pass to the function (JSON-serializable).
            input_data (str, optional): String to pass to stdin (if needed).

        Returns:
            tuple:
                result (any): Parsed return value from the function.
                extra_stdout (str): Any extra stdout (may be empty).
                stderr (str): Stderr from the process.
                exit_code (int): Process exit code.
                exec_time (float or None): Wall time for the run (seconds), or None.
                max_rss_kb (int or None): Max memory used (KB), or None.
                profile_info (dict or None): Function-only profiling info, e.g., {"time_ms": float, "mem_bytes": int}, or None.
        """
        pass

    @abstractmethod
    def run_many(self, workdir, function_name, input_args_list, input_data_list=None):
        """
        Run multiple test cases efficiently (e.g., in a persistent container).

        Args:
            workdir (str): Path to the language-specific directory.
            function_name (str): Name of the function/method to call.
            input_args_list (list of list): Arguments for each test case.
            input_data_list (list of str, optional): Stdin strings for each test case.

        Returns:
            list of tuple: Each tuple as described in `run()`.
        """
        pass

    def _container_name(self, workdir):
        """
        Generate a unique container name for the hot container,
        based on platform, language, image tag, and challenge path.

        Args:
            workdir (str): Path to the language-specific directory.

        Returns:
            str: Unique container name.
        """
        # Extract platform and challenge path from directory structure
        # workdir pattern: problems_dir/platform/challenge_path/language
        language_dir = os.path.abspath(workdir)
        challenge_dir = os.path.dirname(language_dir)
        platform = os.path.basename(os.path.dirname(challenge_dir))
        challenge_path = os.path.basename(challenge_dir)

        # Clean up image tag to make it a valid container name
        image_tag = self.docker_image.replace(":", "-").replace("/", "-")

        # Make challenge path safe for use in container name
        safe_challenge = challenge_path.replace("/", "-").replace("\\", "-")

        return f"challenge-{platform}-{safe_challenge}-{self.name}-{image_tag}"

    # Common helper methods that can be used by subclasses

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

    def _parse_batch_output(
        self, stdout: str, stderr: str, exit_code: int, batch_inputs: list
    ) -> List[Tuple]:
        """
        Common batch output parsing logic.
        Can be overridden by subclasses for language-specific needs.
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

        if self.END_OUTPUT not in stdout:
            error_message = "Execution failed or malformed output (missing end marker)"
            if stdout.strip():
                error_message += f"\nStdout: {stdout}"
            if stderr.strip():
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

    @abstractmethod
    def _parse_single_case_output(
        self, case_output: str, stderr: str, exit_code: int, case_index: int
    ) -> Tuple:
        """
        Parse output for a single test case in batch execution.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement _parse_single_case_output")
