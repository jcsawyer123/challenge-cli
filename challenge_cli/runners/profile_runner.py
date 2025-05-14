"""Performance profiling for solutions."""

from typing import Any, Dict, List

from challenge_cli.plugins import get_plugin


class ProfileRunner:
    """Handles performance profiling."""

    def __init__(self, language_dir: str, language: str):
        """
        Initialize profile runner.

        Args:
            language_dir: Directory containing language-specific files
            language: Programming language
        """
        self.language_dir = language_dir
        self.language = language
        self.plugin = get_plugin(language)

        if not self.plugin:
            raise ValueError(f"No plugin found for language: {language}")

    def profile_test_case(
        self,
        function_name: str,
        input_values: List[Any],
        iterations: int = 100,
    ) -> Dict[str, Any]:
        """
        Profile a single test case.

        Args:
            function_name: Name of the function to profile
            input_values: Input values for the test
            iterations: Number of iterations to run

        Returns:
            Profile results dictionary
        """
        # Run multiple iterations
        batch_inputs = [input_values] * iterations
        results = self.plugin.run_many(self.language_dir, function_name, batch_inputs)

        # Extract metrics
        times = []
        mems = []
        error = None
        extra_stdout = ""

        for (
            result,
            stdout,
            stderr,
            exit_code,
            exec_time,
            max_rss_kb,
            profile_info,
        ) in results:
            if exit_code != 0:
                error = stderr
                break
            extra_stdout = stdout  # Keep last stdout

            # Extract timing
            if profile_info and "time_ms" in profile_info:
                times.append(profile_info["time_ms"])
            elif exec_time is not None:
                times.append(exec_time * 1000)

            # Extract memory
            if profile_info and "mem_bytes" in profile_info:
                mems.append(profile_info["mem_bytes"])
            elif max_rss_kb is not None:
                mems.append(max_rss_kb * 1024)

        # Calculate statistics
        result = {
            "error": error,
            "stdout": extra_stdout,
            "iterations": iterations,
        }

        if times:
            result.update(
                {
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                }
            )

        if mems:
            result.update(
                {
                    "avg_mem_bytes": sum(mems) / len(mems),
                    "min_mem_bytes": min(mems),
                    "max_mem_bytes": max(mems),
                }
            )

        return result
