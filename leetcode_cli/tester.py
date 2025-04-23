import importlib.util
import json
import os
import time
import traceback
from contextlib import redirect_stdout
from typing import Any, Dict, Set

from leetcode_cli.utils import format_time, format_memory
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



SOLUTION_TEMPLATE = """class Solution:
    def solve(self, param1, param2):
        \"\"\"
        Replace this with the actual function signature from LeetCode.
        For example:
        def twoSum(self, nums: List[int], target: int) -> List[int]:
            # Your solution here
            pass
        \"\"\"
        pass
"""

TESTCASES_TEMPLATE = """{
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
        self.solution_dir = os.path.join(problems_dir or os.getcwd(), problem_id)
        self.solution_file = os.path.join(self.solution_dir, "solution.py")
        self.testcases_file = os.path.join(self.solution_dir, "testcases.json")
        
    def init_problem(self) -> None:
        """Initialize the problem directory and template files."""
        if os.path.exists(self.solution_dir):
            print(f"Directory for problem {self.problem_id} already exists.")
            return
        
        os.makedirs(self.solution_dir, exist_ok=True)
        
        with open(self.solution_file, "w") as f:
            f.write(SOLUTION_TEMPLATE)
        with open(self.testcases_file, "w") as f:
            f.write(TESTCASES_TEMPLATE)

            
        # Create a complexity.json file for storing complexity analysis results
        complexity_file = os.path.join(self.solution_dir, "complexity.json")
        with open(complexity_file, "w") as f:
            f.write(COMPLEXITY_TEMPLATE)
        
        print(f"Problem {self.problem_id} initialized successfully.")
        print(f"Please edit {self.solution_file} with your solution.")
        print(f"And update {self.testcases_file} with your test cases.")
        
        # Check if psutil is installed
        try:
            import psutil
        except ImportError:
            print("\n⚠️  Warning: psutil is not installed. Memory profiling will be limited.")
            print("   Install with: pip install psutil")
    
    def _get_line_info_from_error(self, error, solution_file):
        """Extract line number and line content from error traceback."""
        if not hasattr(error, '__traceback__'):
            return None, None
        
        tb = error.__traceback__
        while tb.tb_next:
            tb = tb.tb_next
            
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        
        # Try to get the actual file line
        line_content = None
        try:
            with open(solution_file, 'r') as f:
                lines = f.readlines()
                if 0 < lineno <= len(lines):
                    line_content = lines[lineno-1].strip()
        except:
            pass
            
        return lineno, line_content
    
    def load_solution(self) -> Any:
        """Load the solution module."""
        if not os.path.exists(self.solution_file):
            raise FileNotFoundError(f"Solution file not found: {self.solution_file}")
        
        spec = importlib.util.spec_from_file_location("solution", self.solution_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module.Solution()
    
    def load_testcases(self) -> Dict:
        """Load test cases from the testcases file."""
        if not os.path.exists(self.testcases_file):
            raise FileNotFoundError(f"Test cases file not found: {self.testcases_file}")
        
        with open(self.testcases_file, "r") as f:
            return json.load(f)
    
    def _parse_cases_arg(self, cases_arg: str, total_cases: int) -> Set[int]:
        """Parse the --cases argument to determine which test cases to run."""
        if not cases_arg:
            return set(range(1, total_cases + 1))
        
        selected_cases = set()
        parts = cases_arg.split(',')
        
        for part in parts:
            if '-' in part:
                # Handle ranges like "1-3"
                start, end = map(int, part.split('-'))
                selected_cases.update(range(start, end + 1))
            else:
                # Handle single numbers
                selected_cases.add(int(part))
        
        # Ensure all selected cases are valid
        return {case for case in selected_cases if 1 <= case <= total_cases}

    def _compare_results(self, result: Any, expected: Any) -> bool:
        """Compare results with expected output, handling various data types."""
        # Convert expected from string to appropriate type if needed
        if isinstance(expected, str):
            try:
                # Try to parse as JSON
                expected = json.loads(expected)
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass
        
        # Handle lists that may be in different order but have same elements
        if isinstance(result, list) and isinstance(expected, list):
            if len(result) != len(expected):
                return False
            
            # Check if we need to sort (depends on the problem)
            # This is a simplification - for some problems you'd need custom comparison
            if all(isinstance(x, (int, float, str)) for x in result) and \
               all(isinstance(x, (int, float, str)) for x in expected):
                return sorted(result) == sorted(expected)
            
            # For nested structures, we'll compare directly
            return result == expected
        
        return result == expected

    def _format_error_traceback(self, error, solution_file):
        """Format the error traceback to show only relevant parts from the solution file."""
        import traceback
        import os
        
        # Get the full traceback
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        
        # Filter to only show lines from the solution file
        solution_file_name = os.path.basename(solution_file)
        filtered_tb = []
        
        relevant_lines = False
        for line in tb_lines:
            # Start capturing once we see the solution file in the traceback
            if solution_file_name in line:
                relevant_lines = True
                # Extract just the line from the solution file
                filtered_tb.append(line.strip())
                continue
                
            # If we've started capturing relevant lines
            if relevant_lines:
                # If this is an actual code line or error message
                if line.strip().startswith('File '):
                    # We've moved beyond the solution file section
                    break
                filtered_tb.append(line.strip())
        
        # Add the error message if we didn't capture it
        if not filtered_tb:
            filtered_tb = [str(error)]
        
        # Indent each line of the traceback with two spaces
        indented_tb = ["  " + line for line in filtered_tb]
        
        return "\n".join(indented_tb)

    def _run_case(
        self,
        solution_func,
        input_values,
        expected,
        detailed=False,
        profile_iterations=None
    ):
        """
        Run a single test case.
        If profile_iterations is None, run once and return result, time, memory, error.
        If profile_iterations is int, run multiple times and return timing/memory stats.
        """
        import psutil
        import tracemalloc
        import time
        import io
        from contextlib import redirect_stdout

        result = None
        error = None
        timings = []
        memory_stats = []
        stdout_output = ""
        process = psutil.Process(os.getpid())

        if profile_iterations is None:
            # Single run (for testing)
            stdout_capture = io.StringIO()
            try:
                tracemalloc.start()
                mem_before = process.memory_info().rss
                with redirect_stdout(stdout_capture):
                    start_time = time.time()
                    result = solution_func(*input_values)
                    exec_time = time.time() - start_time
                mem_after = process.memory_info().rss
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                stdout_output = stdout_capture.getvalue()
                return {
                    "result": result,
                    "expected": expected,
                    "exec_time": exec_time,
                    "current_mem": current,
                    "peak_mem": peak,
                    "mem_change": mem_after - mem_before,
                    "stdout": stdout_output,
                    "error": None,
                }
            except Exception as e:
                stdout_output = stdout_capture.getvalue()
                return {
                    "result": None,
                    "expected": expected,
                    "exec_time": None,
                    "current_mem": None,
                    "peak_mem": None,
                    "mem_change": None,
                    "stdout": stdout_output,
                    "error": e,
                }
        else:
            # Profiling mode
            # Warmup
            warmup_stdout = io.StringIO()
            try:
                with redirect_stdout(warmup_stdout):
                    solution_func(*input_values)
                warmup_out = warmup_stdout.getvalue()
            except Exception as e:
                warmup_out = warmup_stdout.getvalue()
                return {
                    "profile_error": e,
                    "warmup_stdout": warmup_out,
            }

            tracemalloc.start()
            baseline_memory = process.memory_info().rss
            stdout_capture = io.StringIO()
            for _ in range(profile_iterations):
                try:
                    with redirect_stdout(stdout_capture):
                        current_before = tracemalloc.get_traced_memory()[0]
                        start_time = time.time()
                        solution_func(*input_values)
                        exec_time = time.time() - start_time
                        timings.append(exec_time)
                        current, peak = tracemalloc.get_traced_memory()
                        memory_stats.append((current - current_before, peak))
                except Exception as e:
                    tracemalloc.stop()
                    return {
                        "profile_error": e,
                        "profile_stdout": stdout_capture.getvalue(),
                    }
            tracemalloc.stop()
            final_memory = process.memory_info().rss
            memory_change = final_memory - baseline_memory
            avg_time = sum(timings) / len(timings)
            min_time = min(timings)
            max_time = max(timings)
            avg_current_mem = sum(m[0] for m in memory_stats) / len(memory_stats)
            avg_peak_mem = sum(m[1] for m in memory_stats) / len(memory_stats)
            max_peak_mem = max(m[1] for m in memory_stats)
            return {
                "iterations": profile_iterations,
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "avg_current_mem": avg_current_mem,
                "avg_peak_mem": avg_peak_mem,
                "max_peak_mem": max_peak_mem,
                "memory_change": memory_change,
                "stdout": stdout_capture.getvalue(),
                "warmup_stdout": warmup_out,
                "profile_error": None,
            }

    def run_tests(self, detailed: bool = False, cases_arg: str = None) -> None:
        """Run the solution against the test cases."""
        solution = self.load_solution()
        test_config = self.load_testcases()

        function_name = test_config["function"]
        testcases = test_config["testcases"]

        solution_func = getattr(solution, function_name)

        # Determine which test cases to run
        selected_cases = self._parse_cases_arg(cases_arg, len(testcases))

        print_warning(f"Testing function: {function_name}")

        total_passed = 0
        total_run = 0

        for i, testcase in enumerate(testcases):
            case_num = i + 1
            if case_num not in selected_cases:
                continue

            input_values = testcase["input"]
            expected = testcase["output"]

            result_info = self._run_case(solution_func, input_values, expected, detailed=detailed)

            total_run += 1

            if result_info["error"] is None:
                passed = self._compare_results(result_info["result"], expected)
                if passed:
                    total_passed += 1
                print_test_case_result(
                    case_num=case_num,
                    passed=passed,
                    exec_time=format_time(result_info['exec_time']),
                    memory=format_memory(result_info['peak_mem']),
                    result=result_info['result'],
                    expected=expected,
                    stdout=result_info["stdout"],
                    input_values=input_values if detailed else None,
                    current_mem=format_memory(result_info['current_mem']) if detailed and result_info['current_mem'] is not None else None,
                    mem_change=format_memory(result_info['mem_change']) if detailed and result_info['mem_change'] is not None else None,
                    detailed=detailed
                )
            else:
                lineno, line_content = self._get_line_info_from_error(result_info["error"], self.solution_file)
                error_msg = str(result_info["error"])
                cleaned_traceback = self._format_error_traceback(result_info["error"], self.solution_file)
                print_error(
                    case_num=case_num,
                    error_msg=error_msg,
                    lineno=lineno,
                    line_content=line_content,
                    stdout=result_info["stdout"],
                    detailed=detailed,
                    traceback_str=cleaned_traceback if detailed else None
                )

        print_summary(total_passed, total_run, len(selected_cases), len(testcases))

    def profile(self, iterations: int = 100, detailed: bool = False, cases_arg: str = None) -> None:
        """Profile the solution over multiple iterations."""
        solution = self.load_solution()
        test_config = self.load_testcases()

        function_name = test_config["function"]
        testcases = test_config["testcases"]

        solution_func = getattr(solution, function_name)

        # Determine which test cases to run
        selected_cases = self._parse_cases_arg(cases_arg, len(testcases))

        print_warning(f"Profiling function: {function_name}")

        total_profiled = 0

        for i, testcase in enumerate(testcases):
            case_num = i + 1
            if case_num not in selected_cases:
                continue

            input_values = testcase["input"]

            result_info = self._run_case(
                solution_func, input_values, None, detailed=detailed, profile_iterations=iterations
            )

            if result_info.get("profile_error") is not None:
                error = result_info["profile_error"]
                lineno, line_content = self._get_line_info_from_error(error, self.solution_file)
                error_msg = str(error)
                print_error(
                    case_num=case_num,
                    error_msg=error_msg,
                    lineno=lineno,
                    line_content=line_content,
                    stdout=result_info.get("profile_stdout", ""),
                    detailed=detailed,
                    traceback_str=None
                )
                continue

            total_profiled += 1

            print_profile_result(
                case_num=case_num,
                iterations=iterations,
                avg_time=format_time(result_info['avg_time']),
                min_time=format_time(result_info['min_time']),
                max_time=format_time(result_info['max_time']),
                avg_current_mem=format_memory(result_info['avg_current_mem']),
                avg_peak_mem=format_memory(result_info['avg_peak_mem']),
                max_peak_mem=format_memory(result_info['max_peak_mem']),
                memory_change=format_memory(result_info['memory_change']),
                warmup_stdout=result_info["warmup_stdout"],
                profile_stdout=result_info["stdout"]
            )

        print_profile_summary(total_profiled, len(selected_cases), len(testcases))

    def analyze_complexity(self) -> None:
        """Analyze the time and space complexity of the solution."""
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

            complexity_file = os.path.join(self.solution_dir, "complexity.json")
            with open(complexity_file, "w") as f:
                complexity_data = {
                    "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "methods": complexity_results
                }
                json.dump(complexity_data, f, indent=2)

            print_complexity_footer(complexity_file)

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

