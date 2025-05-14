"""Core test execution logic."""

from typing import Any, Dict, List, Tuple

from challenge_cli.core.data_utils import compare_results
from challenge_cli.plugins import get_plugin


class TestRunner:
    """Handles test execution."""

    def __init__(self, language_dir: str, language: str):
        """
        Initialize test runner.

        Args:
            language_dir: Directory containing language-specific files
            language: Programming language
        """
        self.language_dir = language_dir
        self.language = language
        self.plugin = get_plugin(language)

        if not self.plugin:
            raise ValueError(f"No plugin found for language: {language}")

    def run_batch_tests(
        self, function_name: str, test_inputs: List[List[Any]]
    ) -> List[Tuple]:
        """
        Run multiple test cases in batch.

        Args:
            function_name: Name of the function to test
            test_inputs: List of input arguments for each test

        Returns:
            List of result tuples for each test
        """
        return self.plugin.run_many(self.language_dir, function_name, test_inputs)

    def process_test_result(
        self,
        result_data: Tuple,
        case_num: int,
        input_values: List[Any],
        expected: Any,
    ) -> Dict[str, Any]:
        """
        Process a single test result.

        Args:
            result_data: Raw result from plugin
            case_num: Test case number
            input_values: Input values for the test
            expected: Expected output

        Returns:
            Processed test result dictionary
        """
        result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info = (
            result_data
        )

        error = None if exit_code == 0 else stderr
        passed = False
        time_ms = None
        mem_bytes = None

        # Determine time
        if profile_info and "time_ms" in profile_info:
            time_ms = profile_info["time_ms"]
        elif exec_time is not None:
            time_ms = exec_time * 1000

        # Determine memory
        if profile_info and "mem_bytes" in profile_info:
            mem_bytes = profile_info["mem_bytes"]
        elif max_rss_kb is not None:
            mem_bytes = max_rss_kb * 1024

        # Prepare result record
        test_result = {
            "case_num": case_num,
            "passed": False,
            "error": bool(error),
            "exec_time_ms": time_ms,
            "mem_bytes": mem_bytes,
            "result": result,
            "expected": expected,
            "error_message": error if error else None,
            "traceback_str": stderr if error else None,
            "stdout": extra_stdout if extra_stdout else None,
            "input_values": input_values,
        }

        # Determine pass/fail
        if error is None:
            passed = compare_results(result, expected)
            test_result["passed"] = passed

        return test_result
