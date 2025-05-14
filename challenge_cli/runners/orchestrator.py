"""High-level orchestration for challenge testing and profiling."""

import datetime
import json
import os
import time
import traceback
from typing import Any, Dict, List, Optional

from challenge_cli.analysis.complexity import ComplexityAnalyzer
from challenge_cli.analysis.visualization import HistoryVisualizer
from challenge_cli.core.data_utils import parse_cases_arg
from challenge_cli.core.formatting import format_memory, format_time
from challenge_cli.history.manager import HistoryManager
from challenge_cli.output.terminal import (
    console,
    get_progress_context,
    print_complexity_footer,
    print_complexity_header,
    print_complexity_method,
    print_error,
    print_info,
    print_profile_summary,
    print_profile_summary_table,
    print_snapshot_list,
    print_success,
    print_summary,
    print_test_case_result,
    print_test_summary_table,
    print_visualization_generated,
    print_warning,
)
from challenge_cli.plugins import get_plugin
from challenge_cli.runners.profile_runner import ProfileRunner
from challenge_cli.runners.solutions import SolutionManager
from challenge_cli.runners.test_data import TestDataManager
from challenge_cli.runners.test_runner import TestRunner


class ChallengeTester:
    """Main orchestrator for challenge testing and management."""

    def __init__(
        self,
        platform: str,
        challenge_path: str,
        language: str = None,
        problems_dir: str = None,
        use_history: bool = True,
        max_snapshots: int = 50,
    ):
        """
        Initialize the challenge tester.

        Args:
            platform: Challenge platform (leetcode, aoc, etc.)
            challenge_path: Path to the specific challenge
            language: Programming language
            problems_dir: Base directory for problems
            use_history: Whether to track history
            max_snapshots: Maximum number of history snapshots
        """
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

        # Ensure the base challenge directory exists
        os.makedirs(self.challenge_dir, exist_ok=True)

        # Initialize managers
        self.test_data_manager = TestDataManager(self.challenge_dir)
        self.solution_manager = SolutionManager(
            self.challenge_dir, self.platform, self.challenge_path
        )

        # Initialize history manager if history is enabled
        self.history_manager = None
        if self.use_history and self.language:
            self.history_manager = HistoryManager(
                challenge_dir=self.challenge_dir,
                language=self.language,
                max_snapshots=self.max_snapshots,
            )

    def _initialize_history_manager(
        self, language: Optional[str] = None
    ) -> Optional[HistoryManager]:
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

    def _prepare_execution_context(self, language: Optional[str]) -> Dict[str, Any]:
        """Prepare the context needed for running tests, profiling, or analysis."""
        resolved_language = language or self.language

        if not resolved_language:
            try:
                testcases_data = self.test_data_manager.load_testcases()
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

        # Load testcases and function name
        try:
            testcases_data = self.test_data_manager.load_testcases()
            function_name = self.test_data_manager.get_function_name(resolved_language)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
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
                solution_path = self.solution_manager.get_solution_path(language)
                if os.path.exists(solution_path):
                    snapshot_id = history_manager.create_snapshot(
                        solution_file_path=solution_path,
                        function_name=function_name,
                        tag=tag or "test",
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

    def init_problem(
        self, language: str = "python", function_name: str = "solve"
    ) -> None:
        """Initialize the directory structure and necessary files for a new challenge."""
        try:
            plugin = get_plugin(language)
        except ValueError as e:
            print_error("N/A", str(e), detailed=True)
            return

        if not plugin:
            print_error(
                "N/A", f"No plugin found for language '{language}'", detailed=True
            )
            return

        # Initialize solution file
        self.solution_manager.initialize_solution(language, function_name)

        # Initialize test cases file
        self.test_data_manager.initialize_testcases_file(language, function_name)

        # Initialize history tracking
        history_manager = self._initialize_history_manager(language)
        if self.use_history and history_manager:
            self._create_snapshot_if_enabled(
                history_manager=history_manager,
                language=language,
                function_name=function_name,
                tag="initial",
                comment="Initial solution template",
                detailed=False,
            )

        print_info(f"-> Test cases file: {self.test_data_manager.testcases_file}")

    def run_tests(
        self,
        language: Optional[str] = None,
        detailed: bool = False,
        cases_arg: Optional[str] = None,
        snapshot_comment: Optional[str] = None,
        snapshot_tag: Optional[str] = None,
    ) -> None:
        """Run test cases against the specified language implementation."""
        try:
            context = self._prepare_execution_context(language)
            lang = context["language"]
            _plugin = context["plugin"]
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

        # Prepare batch inputs
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

        # Initialize test runner
        language_dir = self.solution_manager.get_language_dir(lang)
        test_runner = TestRunner(language_dir, lang)

        total_passed = 0
        all_test_results_records = []

        # Execute tests
        with get_progress_context("Running tests...") as progress:
            task = progress.add_task(
                f"Testing {len(batch_inputs)} cases...", total=len(batch_inputs)
            )
            start_time = time.time()

            try:
                results = test_runner.run_batch_tests(function_name, batch_inputs)
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

                test_result_record = test_runner.process_test_result(
                    result_data=result_data,
                    case_num=case_num,
                    input_values=batch_inputs[idx],
                    expected=batch_expected[idx],
                )

                # Record performance in history
                if (
                    self.use_history
                    and history_manager
                    and not test_result_record["error"]
                ):
                    time_ms = test_result_record.get("exec_time_ms")
                    mem_bytes = test_result_record.get("mem_bytes")
                    if time_ms is not None:
                        try:
                            history_manager.add_performance_record(
                                case_num=case_num,
                                metrics={
                                    "time_ms": time_ms,
                                    "mem_bytes": (
                                        mem_bytes if mem_bytes is not None else 0
                                    ),
                                },
                                snapshot_id=snapshot_id,
                            )
                        except Exception:
                            pass

                all_test_results_records.append(test_result_record)
                if test_result_record["passed"]:
                    total_passed += 1

        # Record results in history
        if self.use_history and history_manager:
            try:
                history_manager.add_test_results(
                    results=all_test_results_records, snapshot_id=snapshot_id
                )
                if detailed:
                    print_info("Overall test results recorded in history")
            except Exception as e:
                print_warning(f"Failed to record overall test results: {e}")

        # Display results
        print_test_summary_table(all_test_results_records)

        if detailed:
            self._print_detailed_results(all_test_results_records)
        else:
            self._print_errors(all_test_results_records)
            self._print_failed(all_test_results_records)

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
        cases_arg: Optional[str] = None,
        snapshot_comment: Optional[str] = None,
        snapshot_tag: Optional[str] = None,
    ) -> None:
        """Profile the performance of the solution."""
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        try:
            context = self._prepare_execution_context(language)
            function_name = context["function_name"]
            testcases_data = context["testcases"]
            history_manager = context["history_manager"]

            testcase_list = testcases_data["testcases"]
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

        # Create snapshot if enabled
        snapshot_id = self._create_snapshot_if_enabled(
            history_manager,
            language,
            function_name,
            snapshot_tag,
            snapshot_comment,
            detailed,
        )

        # Initialize profile runner
        language_dir = self.solution_manager.get_language_dir(language)
        profile_runner = ProfileRunner(language_dir, language)

        total_profiled = 0
        profiled_results = []

        for i, testcase in enumerate(testcase_list):
            case_num = i + 1
            if case_num not in selected_cases:
                continue

            # Profile the test case
            profile_result = profile_runner.profile_test_case(
                function_name, testcase["input"], iterations
            )

            if profile_result.get("error"):
                print_error(
                    case_num=case_num,
                    error_msg=profile_result["error"],
                    stdout=profile_result.get("stdout"),
                    detailed=detailed,
                )
                continue

            total_profiled += 1

            # Collect results for summary
            profiled_results.append(
                {
                    "case_num": case_num,
                    "iterations": iterations,
                    "avg_time": profile_result.get("avg_time"),
                    "min_time": profile_result.get("min_time"),
                    "max_time": profile_result.get("max_time"),
                    "avg_mem_bytes": profile_result.get("avg_mem_bytes"),
                    "max_mem_bytes": profile_result.get("max_mem_bytes"),
                }
            )

            # Record performance in history
            if (
                self.use_history
                and history_manager
                and profile_result.get("avg_time") is not None
            ):
                try:
                    history_manager.add_performance_record(
                        case_num=case_num,
                        metrics={
                            "time_ms": profile_result["avg_time"],
                            "mem_bytes": int(profile_result.get("avg_mem_bytes", 0)),
                            "min_time_ms": profile_result.get("min_time"),
                            "max_time_ms": profile_result.get("max_time"),
                            "min_mem_bytes": int(
                                profile_result.get("min_mem_bytes", 0)
                            ),
                            "max_mem_bytes": int(
                                profile_result.get("max_mem_bytes", 0)
                            ),
                            "iterations": iterations,
                        },
                        snapshot_id=snapshot_id,
                    )
                except Exception as e:
                    if detailed:
                        print_warning(f"Failed to record performance: {e}")

        # Display results
        if profiled_results:
            print_profile_summary_table(profiled_results)

        print_profile_summary(total_profiled, len(selected_cases), len(testcase_list))

    def analyze_complexity(self, language: Optional[str] = None) -> None:
        """Analyze the complexity of the solution."""
        try:
            context = self._prepare_execution_context(language)
            resolved_language = context["language"]
        except (ValueError, FileNotFoundError, Exception) as e:
            print_error(
                "N/A",
                f"Failed to prepare context for complexity analysis: {e}",
                detailed=True,
            )
            return

        if resolved_language.lower() != "python":
            print_error(
                case_num="N/A",
                error_msg=f"Complexity analysis currently only supports Python. Selected language is '{resolved_language}'.",
                detailed=True,
            )
            return

        solution_path = self.solution_manager.get_solution_path(resolved_language)
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

            # Save complexity results
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

    def list_history(self, language: Optional[str] = None, limit: int = 10) -> None:
        """List solution snapshots."""
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        history_manager = self._initialize_history_manager(language)
        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            snapshots = history_manager._get_language_snapshot_ids(limit=limit)
            if not snapshots:
                print_warning(
                    f"No snapshots found for {language} in {self.platform}/{self.challenge_path}"
                )
                return

            snapshot_data = []
            for snapshot_id in snapshots:
                snapshot_info = history_manager.get_snapshot_info(snapshot_id)
                if not snapshot_info:
                    continue

                created_at = snapshot_info.get("created_at", "Unknown")
                try:
                    dt = datetime.datetime.fromisoformat(created_at)
                    created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

                snapshot_data.append(
                    {
                        "id": snapshot_id,
                        "created_at": created_at,
                        "tag": snapshot_info.get("tag", ""),
                        "comment": snapshot_info.get("comment", ""),
                        "function_name": snapshot_info.get("function_name", ""),
                    }
                )

            print_snapshot_list(
                snapshot_data, language, f"{self.platform}/{self.challenge_path}"
            )

            console.print()
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

    def show_snapshot(self, snapshot_id: str) -> None:
        """Show the details of a specific snapshot."""
        # Extract language from snapshot_id
        language = snapshot_id.split("_")[-1]
        history_manager = self._initialize_history_manager(language)

        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Implementation details would go here - omitted for brevity
            # This would display snapshot info, solution code, performance history, etc.
            pass
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error showing snapshot: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def compare_snapshots(self, snapshot_id1: str, snapshot_id2: str) -> None:
        """Compare two snapshots."""
        # Initialize history managers for both snapshots
        language1 = snapshot_id1.split("_")[-1]
        language2 = snapshot_id2.split("_")[-1]

        history_manager1 = self._initialize_history_manager(language1)
        history_manager2 = (
            history_manager1
            if language1 == language2
            else self._initialize_history_manager(language2)
        )

        if not history_manager1 or not history_manager2:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Implementation details would go here - omitted for brevity
            # This would compare solutions, performance metrics, etc.
            pass
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error comparing snapshots: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def restore_snapshot(self, snapshot_id: str, backup: bool = False) -> None:
        """Restore solution from a snapshot."""
        # Determine language from snapshot metadata
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

        history_manager = self._initialize_history_manager(language)

        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            # Implementation details would go here - omitted for brevity
            # This would restore the solution from the snapshot
            pass
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error restoring snapshot: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc(),
            )

    def visualize_history(
        self,
        language: Optional[str] = None,
        output_path: Optional[str] = None,
        cases_arg: Optional[str] = None,
    ) -> None:
        """Visualize performance and test history."""
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A", error_msg="No language specified", detailed=True
            )
            return

        history_manager = self._initialize_history_manager(language)
        if not history_manager:
            print_error(
                case_num="N/A",
                error_msg="History tracking is not enabled.",
                detailed=True,
            )
            return

        try:
            with get_progress_context("Generating visualization...") as progress:
                task = progress.add_task("Processing history data...", total=3)

                # Parse cases filter if provided
                cases_filter = None
                if cases_arg:
                    total_cases = len(
                        self.test_data_manager.load_testcases()["testcases"]
                    )
                    selected_cases = parse_cases_arg(cases_arg, total_cases)
                    # TODO: Use cases_filter
                    cases_filter = list(selected_cases)  # noqa: F841

                progress.update(
                    task, advance=1, description="Initializing visualizer..."
                )

                visualizer = HistoryVisualizer(
                    challenge_dir=self.challenge_dir, language=language
                )

                progress.update(
                    task, advance=1, description="Creating HTML visualization..."
                )

                # TODO: Use title
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

    # Helper methods
    def _print_detailed_results(self, results: List[Dict[str, Any]]) -> None:
        """Print detailed test results."""
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
                    format_memory(result["mem_bytes"]) if result["mem_bytes"] else "N/A"
                ),
                result=result["result"],
                expected=result["expected"],
                stdout=result.get("stdout"),
                input_values=result.get("input_values"),
                detailed=True,
            )

    def _print_errors(self, results: List[Dict[str, Any]]) -> None:
        """Print error results."""
        for result in results:
            if result.get("error", False):
                print_error(
                    case_num=result["case_num"],
                    error_msg=result.get("error_message", "Unknown error"),
                    stdout=result.get("stdout"),
                    detailed=True,
                    traceback_str=result.get("traceback_str"),
                )

    def _print_failed(self, results: List[Dict[str, Any]]) -> None:
        """Print failed test results."""
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
                    stdout=result.get("stdout"),
                    input_values=result.get("input_values"),
                    detailed=True,
                )
