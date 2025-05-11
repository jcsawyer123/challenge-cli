import json
import os
import time
import traceback
from typing import Any, Dict, Set

from leetcode_cli.plugins import get_plugin
from leetcode_cli.utils import format_time
from leetcode_cli.analyzer import ComplexityAnalyzer
from leetcode_cli.output import (
    print_complexity_footer,
    print_complexity_header,
    print_complexity_method,
    print_test_case_result,
    print_error,
    print_summary,
    print_profile_result,
    print_profile_summary,
    print_warning,
)

TESTCASES_TEMPLATE = """{
    "language": "python",
    "function": "functionName",
    "testcases": [
        {
            "input": ["param1_value", "param2_value"],
            "output": "expected_output"
        }
    ]
}
"""

COMPLEXITY_TEMPLATE = """{
    "time_complexity": "Not analyzed yet",
    "space_complexity": "Not analyzed yet",
    "explanation": "",
    "last_analyzed": null
}
"""

class LeetCodeTester:
    def __init__(self, problem_id: str, problems_dir: str = None):
        self.problem_id = problem_id
        self.problem_dir = os.path.join(problems_dir or os.getcwd(), problem_id)
        self.testcases_file = os.path.join(self.problem_dir, "testcases.json")

    def init_problem(self, language="python", function_name="solve") -> None:
        if os.path.exists(self.problem_dir):
            print(f"Directory for problem {self.problem_id} already exists.")
            return

        os.makedirs(self.problem_dir, exist_ok=True)
        plugin = get_plugin(language)
        if not plugin:
            print(f"ERROR: No plugin found for language '{language}'")
            return

        solution_path = os.path.join(self.problem_dir, plugin.solution_filename)
        with open(solution_path, "w") as f:
            f.write(plugin.solution_template(function_name=function_name))
        with open(self.testcases_file, "w") as f:
            f.write(TESTCASES_TEMPLATE.replace("functionName", function_name).replace("python", language))

        complexity_file = os.path.join(self.problem_dir, "complexity.json")
        with open(complexity_file, "w") as f:
            f.write(COMPLEXITY_TEMPLATE)

        print(f"Problem {self.problem_id} initialized successfully.")
        print(f"Please edit {solution_path} with your solution.")
        print(f"And update {self.testcases_file} with your test cases.")

    def load_testcases(self) -> Dict:
        if not os.path.exists(self.testcases_file):
            raise FileNotFoundError(f"Test cases file not found: {self.testcases_file}")
        with open(self.testcases_file, "r") as f:
            return json.load(f)
    
    def _parse_cases_arg(self, cases_arg: str, total_cases: int) -> Set[int]:
        if not cases_arg:
            return set(range(1, total_cases + 1))
        selected_cases = set()
        parts = cases_arg.split(',')
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                selected_cases.update(range(start, end + 1))
            else:
                selected_cases.add(int(part))
        return {case for case in selected_cases if 1 <= case <= total_cases}

    def _compare_results(self, result: Any, expected: Any) -> bool:
        if isinstance(expected, str):
            try:
                expected = json.loads(expected)
            except json.JSONDecodeError:
                pass
        if isinstance(result, list) and isinstance(expected, list):
            if len(result) != len(expected):
                return False
            if all(isinstance(x, (int, float, str)) for x in result) and \
               all(isinstance(x, (int, float, str)) for x in expected):
                return sorted(result) == sorted(expected)
            return result == expected
        return result == expected

    def _parse_result(self, stdout):
        try:
            return json.loads(stdout.strip())
        except Exception:
            return stdout.strip()

    def run_tests(self, detailed: bool = False, cases_arg: str = None) -> None:
        test_config = self.load_testcases()
        language = test_config.get("language", "python")
        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return

        function_name = test_config["function"]
        testcases = test_config["testcases"]
        selected_cases = self._parse_cases_arg(cases_arg, len(testcases))

        print_warning(f"Testing function: {function_name} (language: {language})")

        # Prepare batch inputs
        batch_inputs = []
        batch_expected = []
        batch_case_nums = []
        for i, testcase in enumerate(testcases):
            case_num = i + 1
            if case_num not in selected_cases:
                continue
            batch_inputs.append(testcase["input"])
            batch_expected.append(testcase["output"])
            batch_case_nums.append(case_num)

        # Run all selected test cases in a persistent container
        start_time = time.time()
        results = plugin.run_many(self.problem_dir, function_name, batch_inputs)
        total_time = time.time() - start_time

        total_passed = 0
        total_run = len(batch_case_nums)

        for idx, (result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info) in enumerate(results):
            case_num = batch_case_nums[idx]
            input_values = batch_inputs[idx]
            expected = batch_expected[idx]
            error = None if exit_code == 0 else stderr

            # Use function-only timing/memory if available
            if profile_info and "time_ms" in profile_info:
                time_str = format_time(profile_info['time_ms'] / 1000)
            else:
                time_str = format_time(exec_time) if exec_time is not None else "N/A"


            if profile_info and "mem_bytes" in profile_info:
                mem_str = f"{profile_info['mem_bytes']/1024:.2f} KB"
            else:
                mem_str = f"{max_rss_kb/1024:.2f} MB" if max_rss_kb is not None else "N/A"


            if error is None:
                passed = self._compare_results(result, expected)
                if passed:
                    total_passed += 1
                print_test_case_result(
                    case_num=case_num,
                    passed=passed,
                    exec_time=time_str,
                    memory=mem_str,
                    result=result,
                    expected=expected,
                    stdout=extra_stdout if extra_stdout else None,
                    input_values=input_values if detailed else None,
                    detailed=detailed
                )
            else:
                print_error(
                    case_num=case_num,
                    error_msg=error,
                    stdout=extra_stdout if extra_stdout else None,
                    detailed=detailed,
                    traceback_str=stderr if detailed else None
                )


        print_summary(total_passed, total_run, len(selected_cases), len(testcases))
        if detailed:
            print(f"Total batch time: {format_time(total_time)}")

    def profile(self, iterations: int = 100, detailed: bool = False, cases_arg: str = None) -> None:
        test_config = self.load_testcases()
        language = test_config.get("language", "python")
        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return

        function_name = test_config["function"]
        testcases = test_config["testcases"]
        selected_cases = self._parse_cases_arg(cases_arg, len(testcases))

        print_warning(f"Profiling function: {function_name} (language: {language})")

        total_profiled = 0

        for i, testcase in enumerate(testcases):
            case_num = i + 1
            if case_num not in selected_cases:
                continue

            input_values = testcase["input"]

            # Prepare batch input for profiling
            batch_inputs = [input_values] * iterations

            results = plugin.run_many(self.problem_dir, function_name, batch_inputs)
            error = None
            times = []
            mems = []
            for result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info in results:
                if exit_code != 0:
                    error = stderr
                    break
                # Use function-only profile info if available
                if profile_info and "time_ms" in profile_info:
                    times.append(profile_info["time_ms"])
                elif exec_time is not None:
                    times.append(exec_time * 1000)  # convert s to ms
                if profile_info and "mem_bytes" in profile_info:
                    mems.append(profile_info["mem_bytes"] / 1024)  # bytes to KB
                elif max_rss_kb is not None:
                    mems.append(max_rss_kb)

            if error is not None:
                print_error(
                    case_num=case_num,
                    error_msg=error,
                    stdout=extra_stdout,
                    detailed=detailed,
                    traceback_str=stderr if detailed else None
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
                avg_mem = sum(mems) / len(mems)
                min_mem = min(mems)
                max_mem = max(mems)
            else:
                avg_mem = min_mem = max_mem = None

            print_profile_result(
                case_num=case_num,
                iterations=iterations,
                avg_time=format_time(avg_time / 1000) if avg_time is not None else "N/A",
                min_time=format_time(min_time / 1000) if min_time is not None else "N/A",
                max_time=format_time(max_time / 1000) if max_time is not None else "N/A",
                avg_mem_kb=f"{avg_mem:.2f} KB" if avg_mem is not None else "N/A",
                max_peak_mem=f"{max_mem:.2f} KB" if max_mem is not None else "N/A",
                profile_stdout=extra_stdout if extra_stdout else ""
            )

        print_profile_summary(total_profiled, len(selected_cases), len(testcases))


    def analyze_complexity(self) -> None:
        try:
            test_config = self.load_testcases()
        except FileNotFoundError as e:
            print_error(
                case_num="N/A",
                error_msg=str(e),
                detailed=True
            )
            return
        except json.JSONDecodeError as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error decoding test cases file ({self.testcases_file}): {str(e)}",
                detailed=True
            )
            return

        language = test_config.get("language", "python")
        plugin = get_plugin(language)

        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return

        # Check if the language is Python before proceeding with analysis
        if language.lower() != "python":
            print_error(
                case_num="N/A",
                error_msg=f"Complexity analysis currently only supports Python. Problem language is '{language}'.",
                detailed=True
            )
            return

        # Define self.solution_file before it's used by subsequent checks or operations
        self.solution_file = os.path.join(self.problem_dir, plugin.solution_filename)
        if not os.path.exists(self.solution_file):
            print_error(
                case_num="N/A",
                error_msg=f"Solution file not found: {self.solution_file}",
                detailed=True
            )
            return

        print_complexity_header()

        try:
            analyzer = ComplexityAnalyzer()
            complexity_results = analyzer.analyze_file(self.solution_file)

            if "error" in complexity_results:
                print_error(
                    case_num="N/A",
                    error_msg=f"Error during analysis: {complexity_results['error']}",
                    detailed=True
                )
                return

            for method_name, analysis in complexity_results.items():
                print_complexity_method(method_name, analysis)

            complexity_file = os.path.join(self.problem_dir, "complexity.json")
            with open(complexity_file, "w") as f:
                complexity_data = {
                    "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "methods": complexity_results
                }
                json.dump(complexity_data, f, indent=2)

            print_complexity_footer()

        except ImportError:
            print_error(
                case_num="N/A",
                error_msg="The 'ast' module is required for complexity analysis.",
                detailed=True
            )
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=f"Error during complexity analysis: {str(e)}",
                detailed=True,
                traceback_str=traceback.format_exc()
            )
