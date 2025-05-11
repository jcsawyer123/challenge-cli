import json
import os
import time
import traceback
from typing import Any, Dict, Set

from challenge_cli.plugins import get_plugin
from challenge_cli.utils import format_time, format_memory
from challenge_cli.analyzer import ComplexityAnalyzer
from challenge_cli.output import (
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
    def __init__(self, platform: str, challenge_path: str, language: str = None, problems_dir: str = None):
        self.platform = platform
        self.challenge_path = challenge_path
        self.language = language
        self.problems_dir = problems_dir or os.getcwd()
        
        # Full path: problems_dir/platform/challenge_path
        self.challenge_dir = os.path.join(self.problems_dir, self.platform, self.challenge_path)
        self.testcases_file = os.path.join(self.challenge_dir, "testcases.json")

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

    def init_problem(self, language="python", function_name="solve") -> None:
        # Create challenge directory structure
        os.makedirs(self.challenge_dir, exist_ok=True)
        
        plugin = get_plugin(language)
        if not plugin:
            print(f"ERROR: No plugin found for language '{language}'")
            return
        
        language_dir = self._get_language_dir(language)
        os.makedirs(language_dir, exist_ok=True)
        
        solution_path = os.path.join(language_dir, plugin.solution_filename)
        solution_already_exists = os.path.exists(solution_path)
        
        with open(solution_path, "w") as f:
            f.write(plugin.solution_template(function_name=function_name))
        
        testcases_updated = False
        
        if os.path.exists(self.testcases_file):
            try:
                with open(self.testcases_file, "r") as f:
                    testcases = json.load(f)
                
                if "language" in testcases and "function" in testcases:
                    # Convert old format to new format
                    old_language = testcases["language"]
                    old_function = testcases["function"]
                    old_testcases = testcases["testcases"]
                    
                    # If changing languages, move old solution file to language subdirectory
                    if old_language != language and os.path.exists(os.path.join(self.challenge_dir, plugin.solution_filename)):
                        old_plugin = get_plugin(old_language)
                        if old_plugin:
                            old_solution_path = os.path.join(self.challenge_dir, old_plugin.solution_filename)
                            old_language_dir = self._get_language_dir(old_language)
                            os.makedirs(old_language_dir, exist_ok=True)
                            new_old_solution_path = os.path.join(old_language_dir, old_plugin.solution_filename)
                            if os.path.exists(old_solution_path) and not os.path.exists(new_old_solution_path):
                                os.rename(old_solution_path, new_old_solution_path)
                    
                    testcases = {
                        "testcases": old_testcases,
                        "implementations": {
                            old_language: {"function": old_function},
                            language: {"function": function_name}
                        }
                    }
                else:
                    # Already in new format
                    implementations = testcases.get("implementations", {})
                    implementations[language] = {"function": function_name}
                    testcases["implementations"] = implementations
                
                with open(self.testcases_file, "w") as f:
                    json.dump(testcases, f, indent=2)
                
                testcases_updated = True
            except json.JSONDecodeError:
                # If testcases.json exists but is invalid, create a new one
                pass
        
        if not testcases_updated:
            # Create new testcases.json with language implementation
            with open(self.testcases_file, "w") as f:
                f.write(TESTCASES_TEMPLATE % (language, function_name))
        
        complexity_file = os.path.join(self.challenge_dir, "complexity.json")
        if not os.path.exists(complexity_file):
            with open(complexity_file, "w") as f:
                f.write(COMPLEXITY_TEMPLATE)
        
        if solution_already_exists:
            print(f"Updated {language} implementation for {self.platform} challenge: {self.challenge_path}")
        else:
            print(f"Added {language} implementation for {self.platform} challenge: {self.challenge_path}")
        
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
                return sorted(map(str, result)) == sorted(map(str, expected))
            return result == expected
        return result == expected

    def _parse_result(self, stdout):
        try:
            return json.loads(stdout.strip())
        except Exception:
            return stdout.strip()

    def run_tests(self, language=None, detailed: bool = False, cases_arg: str = None) -> None:
        language = language or self.language
        if not language:
            try:
                testcases = self.load_testcases()
                if "language" in testcases:
                    language = testcases["language"]
                elif "implementations" in testcases and testcases["implementations"]:
                    language = next(iter(testcases["implementations"].keys()))
                else:
                    raise ValueError("No language specified and could not infer from testcases.json")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                print_error(
                    case_num="N/A",
                    error_msg=f"No language specified and could not infer: {str(e)}",
                    detailed=True
                )
                return
        
        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return
        
        try:
            testcases = self.load_testcases()
            function_name = self.get_function_name(language)
            testcase_list = testcases["testcases"]
            selected_cases = self._parse_cases_arg(cases_arg, len(testcase_list))
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=str(e),
                detailed=True,
                traceback_str=traceback.format_exc() if detailed else None
            )
            return

        print_warning(f"Testing {language} function: {function_name} ({self.platform}/{self.challenge_path})")

        batch_inputs = []
        batch_expected = []
        batch_case_nums = []
        for i, testcase in enumerate(testcase_list):
            case_num = i + 1
            if case_num not in selected_cases:
                continue
            batch_inputs.append(testcase["input"])
            batch_expected.append(testcase["output"])
            batch_case_nums.append(case_num)

        language_dir = self._get_language_dir(language)
        start_time = time.time()
        results = plugin.run_many(language_dir, function_name, batch_inputs)
        total_time = time.time() - start_time

        total_passed = 0
        total_run = len(batch_case_nums)

        for idx, (result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info) in enumerate(results):
            case_num = batch_case_nums[idx]
            input_values = batch_inputs[idx]
            expected = batch_expected[idx]
            error = None if exit_code == 0 else stderr

            if profile_info and "time_ms" in profile_info:
                time_str = format_time(profile_info['time_ms'] / 1000)
            else:
                time_str = format_time(exec_time) if exec_time is not None else "N/A"

            if profile_info and "mem_bytes" in profile_info:
                mem_bytes = profile_info['mem_bytes']
                mem_str = format_memory(mem_bytes)
            elif max_rss_kb is not None:
                mem_bytes = max_rss_kb * 1024
                mem_str = format_memory(mem_bytes)
            else:
                mem_str = "N/A"

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

        print_summary(total_passed, total_run, len(selected_cases), len(testcase_list))
        if detailed:
            print(f"Total batch time: {format_time(total_time)}")

    def profile(self, language=None, iterations: int = 100, detailed: bool = False, cases_arg: str = None) -> None:
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A",
                error_msg="No language specified",
                detailed=True
            )
            return
        
        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return
        
        try:
            testcases = self.load_testcases()
            function_name = self.get_function_name(language)
            testcase_list = testcases["testcases"]
            selected_cases = self._parse_cases_arg(cases_arg, len(testcase_list))
        except Exception as e:
            print_error(
                case_num="N/A",
                error_msg=str(e),
                detailed=True,
                traceback_str=traceback.format_exc() if detailed else None
            )
            return

        print_warning(f"Profiling {language} function: {function_name} ({self.platform}/{self.challenge_path})")

        language_dir = self._get_language_dir(language)
        total_profiled = 0

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
            for result, extra_stdout, stderr, exit_code, exec_time, max_rss_kb, profile_info in results:
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
                avg_mem_bytes = sum(mems) / len(mems)
                min_mem_bytes = min(mems)
                max_mem_bytes = max(mems)
            else:
                avg_mem_bytes = min_mem_bytes = max_mem_bytes = None

            avg_mem_str = format_memory(int(avg_mem_bytes)) if avg_mem_bytes is not None else "N/A"
            max_mem_str = format_memory(int(max_mem_bytes)) if max_mem_bytes is not None else "N/A"

            print_profile_result(
                case_num=case_num,
                iterations=iterations,
                avg_time=format_time(avg_time / 1000) if avg_time is not None else "N/A",
                min_time=format_time(min_time / 1000) if min_time is not None else "N/A",
                max_time=format_time(max_time / 1000) if max_time is not None else "N/A",
                avg_mem_str=avg_mem_str,
                max_peak_mem_str=max_mem_str, 
                profile_stdout=extra_stdout if extra_stdout else ""
            )

        print_profile_summary(total_profiled, len(selected_cases), len(testcase_list))

    def analyze_complexity(self, language=None) -> None:
        language = language or self.language
        if not language:
            print_error(
                case_num="N/A",
                error_msg="No language specified",
                detailed=True
            )
            return
        
        if language.lower() != "python":
            print_error(
                case_num="N/A",
                error_msg=f"Complexity analysis currently only supports Python. Selected language is '{language}'.",
                detailed=True
            )
            return
        
        plugin = get_plugin(language)
        if not plugin:
            print_error(
                case_num="N/A",
                error_msg=f"No plugin found for language: {language}",
                detailed=True
            )
            return
        
        solution_path = self.get_solution_path(language)
        if not os.path.exists(solution_path):
            print_error(
                case_num="N/A",
                error_msg=f"Solution file not found: {solution_path}",
                detailed=True
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
                    detailed=True
                )
                return

            for method_name, analysis in complexity_results.items():
                print_complexity_method(method_name, analysis)

            complexity_file = os.path.join(self.challenge_dir, f"{language}_complexity.json")
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