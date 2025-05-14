import datetime
import difflib
import json
import os
import time
import traceback
from typing import Any, Dict, List, Optional

from rich.box import ROUNDED
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from challenge_cli.analyzer import ComplexityAnalyzer
from challenge_cli.history_manager import HistoryManager
from challenge_cli.output import (
    console,
    get_progress_context,
    print_complexity_footer,
    print_complexity_header,
    print_complexity_method,
    print_error,
    print_info,
    print_performance_comparison,
    print_profile_summary,
    print_profile_summary_table,
    print_snapshot_comparison,
    # Add the new functions
    print_snapshot_list,
    print_success,
    print_summary,
    print_test_case_result,
    print_visualization_generated,
    print_warning,
)
from challenge_cli.plugins import get_plugin

# Import the consolidated utils
from challenge_cli.utils import (
    compare_results,
    format_memory,
    format_time,
    load_json,  # May need this if loading complexity.json directly
    parse_cases_arg,  # May need this if saving complexity.json directly
)
from challenge_cli.visualization import HistoryVisualizer

TESTCASES_TEMPLATE = """{
    "testcases": [
        {
            "input": ["param1_value", "param2_value"],
            "output": "expected_output"
        }
    ],
    "implementations": {
        "%s": {
            "function": "%s"
        }
    }
}
"""

COMPLEXITY_TEMPLATE = """{
    "time_complexity": "Not analyzed yet",
    "space_complexity": "Not analyzed yet",
    "explanation": "",
    "last_analyzed": null
}
"""


class ChallengeTester:
    def __init__(
        self,
        platform: str,
        challenge_path: str,
        language: str = None,
        problems_dir: str = None,
        use_history: bool = True,
        max_snapshots: int = 50,
    ):
        self.platform = platform
        self.challenge_path = challenge_path
        self.language = language
        self.problems_dir = problems_dir or os.getcwd()
        self.use_history = use_history
        self.max_snapshots = max_snapshots

        # Full path: problems_dir/platform/challenge_path
        self.challenge_dir = os.path.join(
            self.problems_dir, self.platform, self.challenge_path
        )
        # Ensure the base challenge directory exists before further operations (like HistoryManager init)
        os.makedirs(self.challenge_dir, exist_ok=True)
        self.testcases_file = os.path.join(self.challenge_dir, "testcases.json")

        # Initialize history manager if history is enabled
        self.history_manager = None
        if self.use_history and self.language:
            self.history_manager = HistoryManager(
                challenge_dir=self.challenge_dir,
                language=self.language,
                max_snapshots=self.max_snapshots,
            )

    def _get_language_dir(self, language=None):
        language = language or self.language
        if not language:
            raise ValueError("Language not specified")
        return os.path.join(self.challenge_dir, language)

    def get_solution_path(self, language=None):
        language = language or self.language
        if not language:
            raise ValueError("Language not specified")

        plugin = get_plugin(language)
        if not plugin:
            raise ValueError(f"No plugin found for language: {language}")

        language_dir = self._get_language_dir(language)
        return os.path.join(language_dir, plugin.solution_filename)

    def get_function_name(self, language=None):
        language = language or self.language
        if not language:
            raise ValueError("Language not specified")

        testcases = self.load_testcases()
        implementations = testcases.get("implementations", {})

        if language in implementations:
            return implementations[language]["function"]

        if "language" in testcases and testcases["language"] == language:
            return testcases.get("function", "solve")

        raise ValueError(f"No implementation found for language: {language}")

    def _initialize_history_manager(self, language=None):
        """Initialize or update the history manager if history is enabled."""
        if not self.use_history:
            return None

        language = language or self.language
        if not language:
            return None

        # If language changed or manager not initialized
        if self.history_manager is None or self.history_manager.language != language:
            self.history_manager = HistoryManager(
                challenge_dir=self.challenge_dir,
                language=language,
                max_snapshots=self.max_snapshots,
            )

        return self.history_manager

    def _initialize_or_update_testcases_file(
        self, language: str, function_name: str
    ) -> None:
        """
        Initializes or updates the testcases.json file for the challenge.
        Handles creation, adding/updating language implementations, and
        converting from the old single-language format if necessary.
        """
        testcases_updated = False
        if os.path.exists(self.testcases_file):
            try:
                with open(self.testcases_file, "r") as f:
                    testcases = json.load(f)

                # Check for old format (single language/function at top level)
                if "language" in testcases and "function" in testcases:
                    old_language = testcases["language"]
                    old_function = testcases["function"]
                    old_testcases_list = testcases.get(
                        "testcases", []
                    )  # Get existing testcases

                    # Prepare new structure
                    new_testcases_data = {
                        "testcases": old_testcases_list,
                        "implementations": {
                            old_language: {"function": old_function},
                            # Add the new language being initialized
                            language: {"function": function_name},
                        },
                    }

                    # Attempt to move the old solution file if language is changing
                    # Note: This relies on the plugin for the *new* language being passed in
                    # This might be fragile if init_problem is called without a valid plugin for the *old* language
                    if old_language != language:
                        try:
                            old_plugin = get_plugin(old_language)
                            if old_plugin:
                                old_solution_path_in_root = os.path.join(
                                    self.challenge_dir, old_plugin.solution_filename
                                )
                                if os.path.exists(old_solution_path_in_root):
                                    old_language_dir = self._get_language_dir(
                                        old_language
                                    )
                                    os.makedirs(old_language_dir, exist_ok=True)
                                    new_location_for_old_solution = os.path.join(
                                        old_language_dir, old_plugin.solution_filename
                                    )
                                    if not os.path.exists(
                                        new_location_for_old_solution
                                    ):
                                        os.rename(
                                            old_solution_path_in_root,
                                            new_location_for_old_solution,
                                        )
                                        print_info(
                                            f"Moved existing {old_language} solution to its language directory."
                                        )
                        except Exception as move_err:
                            print_warning(
                                f"Could not move old solution file for {old_language}: {move_err}"
                            )

                    testcases = new_testcases_data  # Overwrite with new structure
                    print_info("Converted testcases.json from old format.")

                else:
                    # Already in new format (or empty/invalid), just add/update implementation
                    implementations = testcases.get("implementations", {})
                    implementations[language] = {"function": function_name}
                    testcases["implementations"] = implementations

                # Write the updated data back to the file
                with open(self.testcases_file, "w") as f:
                    json.dump(testcases, f, indent=2)
                testcases_updated = True

            except json.JSONDecodeError:
                print_warning(
                    f"Existing '{self.testcases_file}' is invalid JSON. Overwriting."
                )
                # Fall through to create a new file below
            except Exception as e:
                print_warning(
                    f"Error processing existing testcases file: {e}. Will attempt to create anew."
                )
                # Fall through

        if not testcases_updated:
            # Create a new testcases.json file from the template
            try:
                with open(self.testcases_file, "w") as f:
                    # Ensure the template uses the correct language and function name
                    f.write(TESTCASES_TEMPLATE % (language, function_name))
                print_info(f"Created new testcases file: {self.testcases_file}")
            except IOError as e:
                print_error(
                    "N/A", f"Failed to write initial testcases file: {e}", detailed=True
                )
                # This is a more critical error, maybe raise? For now, just print.

    def init_problem(self, language="python", function_name="solve") -> None:
        """Initializes the directory structure and necessary files for a new challenge."""
        # Base challenge directory is now created in __init__

        try:
            plugin = get_plugin(language)
        except ValueError as e:  # Catch specific error from get_plugin
            print_error("N/A", str(e), detailed=True)
            return

        if not plugin:  # Should be caught by ValueError, but double-check
            print_error(
                "N/A", f"No plugin found for language '{language}'", detailed=True
            )
            return

        language_dir = self._get_language_dir(language)
        os.makedirs(language_dir, exist_ok=True)

        solution_path = os.path.join(language_dir, plugin.solution_filename)
        solution_already_exists = os.path.exists(solution_path)

        # Write solution template
        try:
            with open(solution_path, "w") as f:
                f.write(plugin.solution_template(function_name=function_name))
        except IOError as e:
            print_error("N/A", f"Failed to write solution template: {e}", detailed=True)
            return  # Cannot proceed without solution file

        # Initialize or update testcases file using the helper
        self._initialize_or_update_testcases_file(language, function_name)

        # Initialize complexity file (simple creation if not exists)
        complexity_file = os.path.join(
            self.challenge_dir, "complexity.json"
        )  # Keep generic name for now
        if not os.path.exists(complexity_file):
            with open(complexity_file, "w") as f:
                f.write(COMPLEXITY_TEMPLATE)

        if not os.path.exists(complexity_file):
            try:
                with open(complexity_file, "w") as f:
                    f.write(COMPLEXITY_TEMPLATE)
            except IOError as e:
                print_warning(
                    f"Failed to write complexity file: {e}"
                )  # Less critical, maybe just warn

        # Initialize history tracking and create initial snapshot
        history_manager = self._initialize_history_manager(language)
        if self.use_history and history_manager:
            # Use the helper for snapshot creation
            self._create_snapshot_if_enabled(
                history_manager=history_manager,
                language=language,
                function_name=function_name,
                tag="initial",
                comment="Initial solution template",
                detailed=False,  # Don't need detailed output for initial snapshot
            )
            # Note: _create_snapshot_if_enabled handles print_info/print_warning internally

        # Final success messages
        if solution_already_exists:
            print_success(
                f"Updated {language} implementation for {self.platform}/{self.challenge_path}"
            )
        else:
            print_success(
                f"Added {language} implementation for {self.platform}/{self.challenge_path}"
            )

        print_info(f"-> Solution file: {solution_path}")
        print_info(f"-> Test cases file: {self.testcases_file}")

    def load_testcases(self) -> Dict:
        if not os.path.exists(self.testcases_file):
            raise FileNotFoundError(f"Test cases file not found: {self.testcases_file}")
        with open(self.testcases_file, "r"):
            # Use the utility function for loading JSON
            return load_json(self.testcases_file)

    # _parse_cases_arg, _compare_results, _parse_result removed. Using versions from utils.py

    def _prepare_execution_context(self, language: Optional[str]) -> Dict[str, Any]:
        """
        Prepares the context needed for running tests, profiling, or analysis.

        Handles language inference, plugin loading, testcase loading,
        function name retrieval, and history manager initialization.

        Returns:
            A dictionary containing: 'language', 'plugin', 'testcases',
            'function_name', 'history_manager'.
        Raises:
            ValueError: If language cannot be determined or plugin is not found.
            FileNotFoundError: If testcases.json is missing.
            Exception: For other errors during loading or initialization.
        """
        resolved_language = language or self.language
        if not resolved_language:
            try:
                testcases_data = self.load_testcases()
                if "language" in testcases_data:  # Check old format first
                    resolved_language = testcases_data["language"]
                elif (
                    "implementations" in testcases_data
                    and testcases_data["implementations"]
                ):
                    resolved_language = next(
                        iter(testcases_data["implementations"].keys())
                    )
                else:
                    raise ValueError(
                        "No language specified and could not infer from testcases.json"
                    )
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"No language specified and could not infer: {str(e)}"
                ) from e

        plugin = get_plugin(resolved_language)
        if not plugin:
            raise ValueError(f"No plugin found for language: {resolved_language}")

        history_manager = self._initialize_history_manager(resolved_language)

        # Load testcases and function name after resolving language and plugin
        try:
            testcases_data = self.load_testcases()
            function_name = self.get_function_name(
                resolved_language
            )  # Use resolved language
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            # Wrap potential errors from load_testcases/get_function_name
            raise Exception(
                f"Error loading test context for {resolved_language}: {str(e)}"
            ) from e

        return {
            "language": resolved_language,
            "plugin": plugin,
            "testcases": testcases_data,
            "function_name": function_name,
            "history_manager": history_manager,
        }

    def _create_snapshot_if_enabled(
        self,
        history_manager: Optional[HistoryManager],
        language: str,
        function_name: str,
        tag: Optional[str],
        comment: Optional[str],
        detailed: bool,
    ) -> Optional[str]:
        """Creates a history snapshot if history is enabled."""
        snapshot_id = None
        if self.use_history and history_manager:
            try:
                solution_path = self.get_solution_path(language)
                if os.path.exists(solution_path):
                    snapshot_id = history_manager.create_snapshot(
                        solution_file_path=solution_path,
                        function_name=function_name,
                        tag=tag or "test",  # Default tag for tests
                        comment=comment,
                    )
                    if detailed:
                        print_info(f"Created snapshot: {snapshot_id}")
                else:
                    if detailed:
                        print_warning(
                            f"Solution file not found, skipping snapshot: {solution_path}"
                        )
            except Exception as e:
                print_warning(f"Failed to create history snapshot: {e}")
        return snapshot_id

    def _process_test_result(
        self,
        result_data: tuple,
        case_num: int,
        input_values: List[Any],
        expected: Any,
        history_manager: Optional[Any],
        snapshot_id: Optional[str],
        detailed: bool,
    ) -> Dict[str, Any]:
        """
        Processes a single test case result and returns a result record.
        Does NOT print anything.
        """
        result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info = (
            result_data
        )
        error = None if exit_code == 0 else stderr
        passed = False
        time_ms = None
        mem_bytes = None

        # --- Determine Time ---
        if profile_info and "time_ms" in profile_info:
            time_ms = profile_info["time_ms"]
        elif exec_time is not None:
            time_ms = exec_time * 1000  # Approximate if only exec_time available

        # --- Determine Memory ---
        if profile_info and "mem_bytes" in profile_info:
            mem_bytes = profile_info["mem_bytes"]
        elif max_rss_kb is not None:
            mem_bytes = max_rss_kb * 1024

        # --- Prepare Result Record ---
        test_result_record = {
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

        # --- Determine Pass/Fail ---
        if error is None:
            # Use utility function for comparison
            passed = compare_results(result, expected)
            test_result_record["passed"] = passed

        # --- Record Performance History ---
        if self.use_history and history_manager and not error and time_ms is not None:
            try:
                history_manager.add_performance_record(
                    case_num=case_num,
                    metrics={
                        "time_ms": time_ms,
                        "mem_bytes": mem_bytes if mem_bytes is not None else 0,
                    },
                    snapshot_id=snapshot_id,
                )
            except Exception:
                pass  # Don't print here

        return test_result_record

    def run_tests(
        self,
        language: Optional[str] = None,
        detailed: bool = False,
        cases_arg: Optional[str] = None,
        snapshot_comment: Optional[str] = None,
        snapshot_tag: Optional[str] = None,
    ) -> None:
        """Runs test cases against the specified language implementation."""

        def print_detailed_results(results):
            for result in results:
                print_test_case_result(
                    case_num=result["case_num"],
                    passed=result["passed"],
                    exec_time=(
                        format_time(result["exec_time_ms"] / 1000)
                        if result["exec_time_ms"]
                        else "N/A"
                    ),
                    memory=(
                        format_memory(result["mem_bytes"])
                        if result["mem_bytes"]
                        else "N/A"
                    ),
                    result=result["result"],
                    expected=result["expected"],
                    stdout=result.get("stdout", None),
                    input_values=result.get("input_values", None),
                    detailed=True,
                )

        def print_errors(results):
            for result in results:
                if result.get("error", False):
                    print_error(
                        case_num=result["case_num"],
                        error_msg=result.get("error_message", "Unknown error"),
                        stdout=result.get("stdout", None),
                        detailed=True,
                        traceback_str=result.get("traceback_str", None),
                    )

        def print_failed(results):
            for result in results:
                if not result["passed"] and not result.get("error", False):
                    print_test_case_result(
                        case_num=result["case_num"],
                        passed=result["passed"],
                        exec_time=(
                            format_time(result["exec_time_ms"] / 1000)
                            if result["exec_time_ms"]
                            else "N/A"
                        ),
                        memory=(
                            format_memory(result["mem_bytes"])
                            if result["mem_bytes"]
                            else "N/A"
                        ),
                        result=result["result"],
                        expected=result["expected"],
                        stdout=result.get("stdout", None),
                        input_values=result.get("input_values", None),
                        detailed=True,
                    )

        # --- Prepare context and test cases ---
        try:
            context = self._prepare_execution_context(language)
            lang = context["language"]
            plugin = context["plugin"]
            testcases_data = context["testcases"]
            function_name = context["function_name"]
            history_manager = context["history_manager"]

            testcase_list = testcases_data["testcases"]
            selected_cases = parse_cases_arg(cases_arg, len(testcase_list))
        except (ValueError, FileNotFoundError, Exception) as e:
            print_error(
                case_num="N/A",
                error_msg=str(e),
                detailed=True,
                traceback_str=traceback.format_exc() if detailed else None,
            )
            return

        print_warning(
            f"Testing {lang} function: {function_name} "
            f"({self.platform}/{self.challenge_path})"
        )

        snapshot_id = self._create_snapshot_if_enabled(
            history_manager,
            lang,
            function_name,
            snapshot_tag,
            snapshot_comment,
            detailed,
        )

        # --- Prepare batch inputs ---
        batch_inputs, batch_expected, batch_case_nums = [], [], []
        for i, testcase in enumerate(testcase_list):
            case_num = i + 1
            if case_num in selected_cases:
                batch_inputs.append(testcase["input"])
                batch_expected.append(testcase["output"])
                batch_case_nums.append(case_num)

        if not batch_inputs:
            print_warning("No test cases selected or found.")
            print_summary(0, 0, 0, len(testcase_list))
            return

        language_dir = self._get_language_dir(lang)
        total_passed = 0
        all_test_results_records = []

        # --- Execute tests ---
        with get_progress_context("Running tests...") as progress:
            task = progress.add_task(
                f"Testing {len(batch_inputs)} cases...", total=len(batch_inputs)
            )
            start_time = time.time()
            try:
                results = plugin.run_many(language_dir, function_name, batch_inputs)
            except Exception as e:
                print_error(
                    case_num="Batch",
                    error_msg=f"Error during batch execution: {e}",
                    detailed=True,
                    traceback_str=traceback.format_exc() if detailed else None,
                )
                return
            total_time = time.time() - start_time

            # Process results
            for idx, result_data in enumerate(results):
                progress.update(task, advance=1)
                case_num = batch_case_nums[idx]
                test_result_record = self._process_test_result(
                    result_data=result_data,
                    case_num=case_num,
                    input_values=batch_inputs[idx],
                    expected=batch_expected[idx],
                    history_manager=history_manager,
                    snapshot_id=snapshot_id,
                    detailed=False,
                )
                all_test_results_records.append(test_result_record)
                if test_result_record["passed"]:
                    total_passed += 1

        # --- Record results in history ---
        if self.use_history and history_manager:
            try:
                history_manager.add_test_results(
                    results=all_test_results_records, snapshot_id=snapshot_id
                )
                if detailed:
                    print_info("Overall test results recorded in history")
            except Exception as e:
                print_warning(f"Failed to record overall test results: {e}")

        # --- Print summary table ---
        from challenge_cli.output import print_test_summary_table

        print_test_summary_table(all_test_results_records)

        # --- Print detailed or error/failure results ---
        if detailed:
            print_detailed_results(all_test_results_records)
        else:
            print_errors(all_test_results_records)
            print_failed(all_test_results_records)

        # --- Print summary panel with emoji ---
        print_summary(
            total_passed, len(batch_case_nums), len(selected_cases), len(testcase_list)
        )
        if total_passed == len(batch_case_nums):
            print_success("All test cases passed! 🎉")
        if detailed:
            print_info(f"Total batch execution time: {format_time(total_time)}")

    def profile(
        self,
        language: Optional[str] = None,
        iterations: int = 100,
        detailed: bool = False,
        cases_arg: str = None,
        snapshot_comment: str = None,
        snapshot_tag: str = None,
    ) -> None:
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        # Update history manager for this language
        history_manager = self._initialize_history_manager(language)

        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True,
            )
            return

        try:
            testcases = self.load_testcases()
            function_name = self.get_function_name(language)
            testcase_list = testcases["testcases"]
            selected_cases = parse_cases_arg(cases_arg, len(testcase_list))
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=str(e),
                detailed=True,
                traceback_str=traceback.format_exc() if detailed else None,
            )
            return

        print_warning(
            f"Profiling {language} function: {function_name} ({self.platform}/{self.challenge_path})"
        )

        # Create a snapshot of the current solution if history is enabled
        snapshot_id = None
        if self.use_history and history_manager:
            try:
                solution_path = self.get_solution_path(language)
                if os.path.exists(solution_path):
                    snapshot_id = history_manager.create_snapshot(
                        solution_file_path=solution_path,
                        function_name=function_name,
                        tag=snapshot_tag or "profile",
                        comment=snapshot_comment,
                    )
                    if detailed:
                        print_info(f"Created snapshot: {snapshot_id}")
            except Exception as e:
                print_warning(f"Failed to create history snapshot: {e}")

        language_dir = self._get_language_dir(language)
        total_profiled = 0
        profiled_results = []

        for i, testcase in enumerate(testcase_list):
            case_num = i + 1
            if case_num not in selected_cases:
                continue

            input_values = testcase["input"]
            batch_inputs = [input_values] * iterations

            results = plugin.run_many(language_dir, function_name, batch_inputs)
            error = None
            times = []
            mems = []
            extra_stdout = ""
            for (
                result,
                extra_stdout,
                stderr,
                exit_code,
                exec_time,
                max_rss_kb,
                profile_info,
            ) in results:
                if exit_code != 0:
                    error = stderr
                    break
                if profile_info and "time_ms" in profile_info:
                    times.append(profile_info["time_ms"])
                elif exec_time is not None:
                    times.append(exec_time * 1000)
                if profile_info and "mem_bytes" in profile_info:
                    mems.append(profile_info["mem_bytes"])
                elif max_rss_kb is not None:
                    mems.append(max_rss_kb * 1024)

            if error is not None:
                print_error(
                    case_num=case_num,
                    error_msg=error,
                    stdout=extra_stdout if "extra_stdout" in locals() else None,
                    detailed=detailed,
                    traceback_str=stderr if detailed else None,
                )
                continue

            total_profiled += 1

            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
            else:
                avg_time = min_time = max_time = None

            if mems:
                avg_mem_bytes = sum(mems) / len(mems)
                min_mem_bytes = min(mems)
                max_mem_bytes = max(mems)
            else:
                avg_mem_bytes = min_mem_bytes = max_mem_bytes = None

            # Collect for summary table
            profiled_results.append(
                {
                    "case_num": case_num,
                    "iterations": iterations,
                    "avg_time": avg_time,
                    "min_time": min_time,
                    "max_time": max_time,
                    "avg_mem_bytes": avg_mem_bytes,
                    "max_mem_bytes": max_mem_bytes,
                }
            )

            # Record performance in history
            if self.use_history and history_manager and avg_time is not None:
                try:
                    history_manager.add_performance_record(
                        case_num=case_num,
                        metrics={
                            "time_ms": avg_time,
                            "mem_bytes": (
                                int(avg_mem_bytes) if avg_mem_bytes is not None else 0
                            ),
                            "min_time_ms": min_time,
                            "max_time_ms": max_time,
                            "min_mem_bytes": (
                                int(min_mem_bytes) if min_mem_bytes is not None else 0
                            ),
                            "max_mem_bytes": (
                                int(max_mem_bytes) if max_mem_bytes is not None else 0
                            ),
                            "iterations": iterations,
                        },
                        snapshot_id=snapshot_id,
                    )
                except Exception as e:
                    if detailed:
                        print_warning(f"Failed to record performance: {e}")

        # Print the condensed summary table
        if profiled_results:
            print_profile_summary_table(profiled_results)

        print_profile_summary(total_profiled, len(selected_cases), len(testcase_list))

    def analyze_complexity(self, language=None) -> None:
        try:
            context = self._prepare_execution_context(language)
            resolved_language = context["language"]
            # plugin = context["plugin"] # Not needed for complexity analysis itself
        except (ValueError, FileNotFoundError, Exception) as e:
            print_error(
                "N/A",
                f"Failed to prepare context for complexity analysis: {e}",
                detailed=True,
            )
            return

        # Check language after context is prepared
        if resolved_language.lower() != "python":
            print_error(
                case_num="N/A",
                error_msg=f"Complexity analysis currently only supports Python. Selected language is '{resolved_language}'.",
                detailed=True,
            )
            return

        # plugin = get_plugin(resolved_language) # Already available in context if needed
        # if not plugin: ... # Already checked in context helper

        solution_path = self.get_solution_path(
            resolved_language
        )  # Use resolved language
        if not os.path.exists(solution_path):
            print_error(
                case_num="N/A",
                error_msg=f"Solution file not found: {solution_path}",
                detailed=True,
            )
            return

        print_complexity_header()

        try:
            analyzer = ComplexityAnalyzer()
            complexity_results = analyzer.analyze_file(solution_path)

            if "error" in complexity_results:
                print_error(
                    case_num="N/A",
                    error_msg=f"Error during analysis: {complexity_results['error']}",
                    detailed=True,
                )
                return

            for method_name, analysis in complexity_results.items():
                print_complexity_method(method_name, analysis)

            complexity_file = os.path.join(
                self.challenge_dir, f"{resolved_language}_complexity.json"
            )
            with open(complexity_file, "w") as f:
                complexity_data = {
                    "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "methods": complexity_results,
                }
                json.dump(complexity_data, f, indent=2)

            print_complexity_footer()

        except ImportError:
            print_error(
                case_num="N/A",
                error_msg="The 'ast' module is required for complexity analysis.",
                detailed=True,
            )
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error during complexity analysis: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def list_history(self, language=None, limit=10):
        """
        List solution snapshots.

        Args:
            language: Language to filter by
            limit: Maximum number of snapshots to display
        """
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        # Update history manager for this language
        history_manager = self._initialize_history_manager(language)
        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Get the snapshots
            snapshots = history_manager._get_language_snapshot_ids(limit=limit)
            if not snapshots:
                print_warning(
                    f"No snapshots found for {language} in {self.platform}/{self.challenge_path}"
                )
                return

            # Prepare snapshot data for the fancy table
            snapshot_data = []
            for snapshot_id in snapshots:
                snapshot_info = history_manager.get_snapshot_info(snapshot_id)
                if not snapshot_info:
                    continue

                created_at = snapshot_info.get("created_at", "Unknown")
                tag = snapshot_info.get("tag", "")
                comment = snapshot_info.get("comment", "")
                function_name = snapshot_info.get("function_name", "")

                # Format timestamp
                try:
                    dt = datetime.datetime.fromisoformat(created_at)
                    created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

                snapshot_data.append(
                    {
                        "id": snapshot_id,
                        "created_at": created_at,
                        "tag": tag,
                        "comment": comment,
                        "function_name": function_name,
                    }
                )

            # Use the new fancy output function
            print_snapshot_list(
                snapshot_data, language, f"{self.platform}/{self.challenge_path}"
            )

            console.print()  # Empty line
            print_info(
                f"Use 'challenge-cli history show -c {self.challenge_path} -s <snapshot_id>' to view a snapshot"
            )
            print_info(
                f"Use 'challenge-cli history compare -c {self.challenge_path} -1 <id1> -2 <id2>' to compare snapshots"
            )

        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error listing history: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def show_snapshot(self, snapshot_id):
        """
        Show the details of a specific snapshot.

        Args:
            snapshot_id: ID of the snapshot to show
        """
        # Initialize history manager
        language = snapshot_id.split("_")[-1]  # Extract language from snapshot_id
        history_manager = self._initialize_history_manager(language)
        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Get snapshot info and solution
            snapshot_info = history_manager.get_snapshot_info(snapshot_id)
            if not snapshot_info:
                print_error(
                    case_num="N/A",
                    error_msg=f"Snapshot not found: {snapshot_id}",
                    detailed=True,
                )
                return

            solution_code = history_manager.get_snapshot_solution(snapshot_id)
            if not solution_code:
                print_error(
                    case_num="N/A",
                    error_msg=f"Solution code not found for snapshot: {snapshot_id}",
                    detailed=True,
                )
                return

            # Display snapshot information
            created_at = snapshot_info.get("created_at", "Unknown")
            tag = snapshot_info.get("tag", "")
            comment = snapshot_info.get("comment", "")
            function_name = snapshot_info.get("function_name", "")

            # Format timestamp
            try:
                dt = datetime.datetime.fromisoformat(created_at)
                created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            # Snapshot info panel
            info_content = f"""[bold]Snapshot:[/bold] {snapshot_id}
    [bold]Created:[/bold] {created_at}"""
            if tag:
                info_content += f"\n[bold]Tag:[/bold] [yellow]{tag}[/yellow]"
            if comment:
                info_content += f"\n[bold]Comment:[/bold] {comment}"
            if function_name:
                info_content += f"\n[bold]Function:[/bold] {function_name}"

            console.print(
                Panel(
                    info_content,
                    title="[bold blue]Snapshot Details[/bold blue]",
                    border_style="blue",
                )
            )

            # Solution code with syntax highlighting
            syntax = Syntax(solution_code, "python", theme="monokai", line_numbers=True)
            console.print(
                Panel(
                    syntax,
                    title="[bold blue]Solution Code[/bold blue]",
                    border_style="blue",
                )
            )

            # Get performance history for this snapshot
            performance_history = history_manager.get_performance_history()
            snapshot_performance = [
                p for p in performance_history if p.get("snapshot_id") == snapshot_id
            ]

            if snapshot_performance:

                perf_table = Table(
                    title="[bold]Performance Metrics[/bold]", box=ROUNDED
                )
                perf_table.add_column("Case", style="cyan", width=8)
                perf_table.add_column("Time", style="green", width=15)
                perf_table.add_column("Memory", style="blue", width=15)

                for record in snapshot_performance:
                    case_num = record.get("case_num", "Unknown")
                    metrics = record.get("metrics", {})
                    time_ms = metrics.get("time_ms")
                    mem_bytes = metrics.get("mem_bytes")

                    time_str = (
                        format_time(time_ms / 1000) if time_ms is not None else "N/A"
                    )
                    mem_str = (
                        format_memory(mem_bytes) if mem_bytes is not None else "N/A"
                    )

                    perf_table.add_row(str(case_num), time_str, mem_str)

                console.print(perf_table)

            # Get test results for this snapshot
            test_history = history_manager.get_test_history()
            snapshot_tests = [
                t for t in test_history if t.get("snapshot_id") == snapshot_id
            ]

            if snapshot_tests:
                console.print()
                console.print(Panel("[bold]Test Results[/bold]", border_style="blue"))

                for record in snapshot_tests:
                    results = record.get("results", [])
                    summary = record.get("summary", {})
                    total = summary.get("total", 0)
                    passed = summary.get("passed", 0)


                    progress = Progress(
                        TextColumn("[bold]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=console,
                    )

                    with progress:
                        progress.add_task(
                            f"Passed {passed}/{total} test cases",
                            total=total,
                            completed=passed,
                        )

                    # Individual test results
                    test_table = Table(show_header=False, box=None)
                    test_table.add_column("Case", style="cyan", width=10)
                    test_table.add_column("Status", width=20)

                    for result in results:
                        case_num = result.get("case_num", "Unknown")
                        passed = result.get("passed", False)
                        error = result.get("error", False)

                        if error:
                            status = "[red]✗ ERROR[/red]"
                        elif passed:
                            status = "[green]✓ PASSED[/green]"
                        else:
                            status = "[red]✗ FAILED[/red]"

                        test_table.add_row(f"Case {case_num}", status)

                    console.print(test_table)

        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error showing snapshot: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def compare_snapshots(self, snapshot_id1, snapshot_id2):
        """
        Compare two snapshots.

        Args:
            snapshot_id1: ID of first snapshot
            snapshot_id2: ID of second snapshot
        """
        # Initialize history manager for first snapshot
        language1 = snapshot_id1.split("_")[-1]
        history_manager1 = self._initialize_history_manager(language1)

        # Initialize history manager for second snapshot
        language2 = snapshot_id2.split("_")[-1]
        if language1 != language2:
            history_manager2 = self._initialize_history_manager(language2)
        else:
            history_manager2 = history_manager1

        if not history_manager1 or not history_manager2:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Get solutions
            solution1 = history_manager1.get_snapshot_solution(snapshot_id1)
            if not solution1:
                print_error(
                    case_num="N/A",
                    error_msg=f"Solution not found for snapshot: {snapshot_id1}",
                    detailed=True,
                )
                return

            solution2 = history_manager2.get_snapshot_solution(snapshot_id2)
            if not solution2:
                print_error(
                    case_num="N/A",
                    error_msg=f"Solution not found for snapshot: {snapshot_id2}",
                    detailed=True,
                )
                return

            # Get snapshot info
            info1 = history_manager1.get_snapshot_info(snapshot_id1)
            info2 = history_manager2.get_snapshot_info(snapshot_id2)

            # Format dates
            created1 = info1.get("created_at", "Unknown")
            created2 = info2.get("created_at", "Unknown")

            try:
                dt1 = datetime.datetime.fromisoformat(created1)
                created1 = dt1.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            try:
                dt2 = datetime.datetime.fromisoformat(created2)
                created2 = dt2.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            # Generate diff
            lines1 = solution1.splitlines()
            lines2 = solution2.splitlines()

            diff = list(
                difflib.unified_diff(
                    lines1,
                    lines2,
                    fromfile=f"snapshot1 ({snapshot_id1})",
                    tofile=f"snapshot2 ({snapshot_id2})",
                    lineterm="",
                )
            )

            # Use the new fancy comparison display
            print_snapshot_comparison(
                {
                    "id": snapshot_id1,
                    "created_at": created1,
                    "tag": info1.get("tag", ""),
                    "comment": info1.get("comment", ""),
                },
                {
                    "id": snapshot_id2,
                    "created_at": created2,
                    "tag": info2.get("tag", ""),
                    "comment": info2.get("comment", ""),
                },
                diff,
            )

            # Compare performance if same language
            if language1 == language2:
                performance_history = history_manager1.get_performance_history()
                perf1 = [
                    p
                    for p in performance_history
                    if p.get("snapshot_id") == snapshot_id1
                ]
                perf2 = [
                    p
                    for p in performance_history
                    if p.get("snapshot_id") == snapshot_id2
                ]

                if perf1 and perf2:
                    # Get most recent performance record for each case
                    perf1_dict = {}
                    for p in perf1:
                        case_num = p.get("case_num")
                        if case_num not in perf1_dict:
                            perf1_dict[case_num] = p

                    perf2_dict = {}
                    for p in perf2:
                        case_num = p.get("case_num")
                        if case_num not in perf2_dict:
                            perf2_dict[case_num] = p

                    # Compare performance for shared test cases
                    shared_cases = set(perf1_dict.keys()) & set(perf2_dict.keys())
                    if shared_cases:
                        performance_comparison_data = {}

                        for case_num in sorted(shared_cases):
                            metrics1 = perf1_dict[case_num].get("metrics", {})
                            metrics2 = perf2_dict[case_num].get("metrics", {})

                            time1 = metrics1.get("time_ms")
                            time2 = metrics2.get("time_ms")
                            mem1 = metrics1.get("mem_bytes")
                            mem2 = metrics2.get("mem_bytes")

                            time1_str = (
                                format_time(time1 / 1000)
                                if time1 is not None
                                else "N/A"
                            )
                            time2_str = (
                                format_time(time2 / 1000)
                                if time2 is not None
                                else "N/A"
                            )
                            mem1_str = (
                                format_memory(mem1) if mem1 is not None else "N/A"
                            )
                            mem2_str = (
                                format_memory(mem2) if mem2 is not None else "N/A"
                            )

                            # Calculate percentage differences
                            if time1 and time2:
                                time_diff_pct = ((time2 - time1) / time1) * 100
                                time_diff_str = f"{time_diff_pct:+.2f}%"
                            else:
                                time_diff_str = "N/A"
                                time_diff_pct = 0

                            if mem1 and mem2:
                                mem_diff_pct = ((mem2 - mem1) / mem1) * 100
                                mem_diff_str = f"{mem_diff_pct:+.2f}%"
                            else:
                                mem_diff_str = "N/A"
                                mem_diff_pct = 0

                            performance_comparison_data[case_num] = {
                                "time1_str": time1_str,
                                "time2_str": time2_str,
                                "time_diff_str": time_diff_str,
                                "time_diff_pct": time_diff_pct,
                                "mem1_str": mem1_str,
                                "mem2_str": mem2_str,
                                "mem_diff_str": mem_diff_str,
                                "mem_diff_pct": mem_diff_pct,
                            }

                        print_performance_comparison(performance_comparison_data)

        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error comparing snapshots: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def restore_snapshot(self, snapshot_id, backup=False):
        """
        Restore solution from a snapshot.

        Args:
            snapshot_id: ID of the snapshot to restore
            backup: Whether to create a backup of the current solution
        """
        # Get language from metadata
        temp_history_manager = HistoryManager(
            self.challenge_dir, language="temp", max_snapshots=self.max_snapshots
        )
        language = temp_history_manager.get_snapshot_language(snapshot_id)

        if not language:
            print_error(
                case_num="N/A",
                error_msg=f"Could not determine language for snapshot: {snapshot_id}",
                detailed=True,
            )
            return

        # Initialize the proper history manager with the determined language
        history_manager = self._initialize_history_manager(language)

        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Get snapshot solution
            solution_code = history_manager.get_snapshot_solution(snapshot_id)
            if not solution_code:
                print_error(
                    case_num="N/A",
                    error_msg=f"Solution not found for snapshot: {snapshot_id}",
                    detailed=True,
                )
                return

            # Get current solution path
            solution_path = self.get_solution_path(language)

            # Create backup if requested
            if backup and os.path.exists(solution_path):
                backup_snapshot_id = None
                try:
                    function_name = self.get_function_name(language)
                    backup_snapshot_id = history_manager.create_snapshot(
                        solution_file=solution_path,
                        function_name=function_name,
                        tag="backup",
                        comment=f"Backup before restoring {snapshot_id}",
                    )
                    print_info(f"Created backup snapshot: {backup_snapshot_id}")
                except Exception as e:
                    print_warning(f"Failed to create backup snapshot: {e}")
                    return

            # Restore the solution
            with open(solution_path, "w") as f:
                f.write(solution_code)

            print_success(f"Restored solution from snapshot: {snapshot_id}")

            # Get snapshot info
            snapshot_info = history_manager.get_snapshot_info(snapshot_id)
            if snapshot_info:
                created_at = snapshot_info.get("created_at", "Unknown")
                try:
                    dt = datetime.datetime.fromisoformat(created_at)
                    created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

                tag = snapshot_info.get("tag", "")
                comment = snapshot_info.get("comment", "")

                if tag:
                    print_info(f"Tag: {tag}")
                if comment:
                    print_info(f"Comment: {comment}")
                print_info(f"Created: {created_at}")

        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error restoring snapshot: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def visualize_history(self, language=None, output_path=None, cases_arg=None):
        """
        Visualize performance and test history.

        Args:
            language: Programming language to visualize
            output_path: Path to save the visualization HTML file (optional)
            cases_arg: Filter specific test cases (e.g., '1,2,5-7')
        """
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        # Initialize history manager for this language
        history_manager = self._initialize_history_manager(language)
        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Use progress indicator for long operations
            with get_progress_context("Generating visualization...") as progress:
                task = progress.add_task("Processing history data...", total=3)

                # Parse cases filter if provided
                cases_filter = None
                if cases_arg:
                    testcases = self.load_testcases()
                    total_cases = len(testcases["testcases"])
                    # Use the utility function for parsing cases argument
                    selected_cases = parse_cases_arg(cases_arg, total_cases)
                    # TODO: Use cases_filter in visualization
                    cases_filter = list(selected_cases)  # noqa: F841

                progress.update(
                    task, advance=1, description="Initializing visualizer..."
                )

                # Initialize visualizer
                visualizer = HistoryVisualizer(
                    challenge_dir=self.challenge_dir, language=language
                )

                progress.update(
                    task, advance=1, description="Creating HTML visualization..."
                )

                # Generate and open visualization

                # TODO: Use the title
                title = f"{self.platform} - {self.challenge_path} - {language} Performance History"  # noqa: F841
                html_path = visualizer.visualize(output_path=output_path)

                progress.update(task, advance=1, description="Done!")

            print_visualization_generated(html_path)

        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error generating visualization: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )
