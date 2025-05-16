import json
import os

from ..language_plugin import LanguagePlugin


class PythonPlugin(LanguagePlugin):
    """Python language plugin for the Challenge CLI."""

    name = "python"
    aliases = ["py"]
    docker_image = "python-runner:3.12"
    dockerfile_path = os.path.join(
        os.path.dirname(__file__), "dockerfiles", "Dockerfile.python"
    )
    solution_filename = "solution.py"

    def _get_driver_filename(self) -> str:
        """Get the filename for the test driver file."""
        return "test_driver.py"

    def _get_batch_command(self, driver_path: str) -> list:
        """Get the command to run for batch testing."""
        return ["python", "test_driver.py"]

    @staticmethod
    def solution_template(function_name="solve"):
        """Returns a template for a new Python solution file."""
        return f"""class Solution:
    def {function_name}(self, param1, param2):
        \"\"\"
        Replace this with the actual function signature.
        \"\"\"
        pass
    """

    def generate_test_driver_template(self, function_name: str) -> str:
        """Generate Python test driver for batch execution."""
        solution_module = self.solution_filename.split(".")[0]
        return f"""
import sys
import json
import time
import tracemalloc
import io
import contextlib
from {solution_module} import Solution

if __name__ == "__main__":
    batch_inputs = []
    try:
        with open("inputs.json", "r") as f:
            batch_inputs_json = f.read()
        batch_inputs = json.loads(batch_inputs_json)
    except Exception as e:
        print(f"{self.ERROR_MARKER}Error loading or parsing inputs.json: {{e}}", file=sys.stderr)
        print("{self.SEPARATOR}", file=sys.stdout)
        print("{self.END_OUTPUT}", file=sys.stdout)
        sys.exit(1)

    sol = Solution()
    results_output = []

    for i, args_for_call in enumerate(batch_inputs):
        case_stdout = io.StringIO()
        try:
            tracemalloc.start()
            t0 = time.perf_counter()
            with contextlib.redirect_stdout(case_stdout):
                result = sol.{function_name}(*args_for_call)
            t1 = time.perf_counter()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Compose output for this case
            case_result = {{
                "result": result,
                "stdout": case_stdout.getvalue(),
                "time_ms": (t1 - t0) * 1000,
                "mem_bytes": peak,
                "error": None
            }}
        except Exception as call_e:
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            case_result = {{
                "result": "ERROR_RESULT",
                "stdout": case_stdout.getvalue(),
                "time_ms": 0,
                "mem_bytes": 0,
                "error": str(call_e)
            }}
            print(f"{self.FUNCTION_ERROR_MARKER} Test case {{i}}: {{call_e}}", file=sys.stderr)
        results_output.append(json.dumps(case_result))

    print("\\n{self.SEPARATOR}\\n".join(results_output))
    print("{self.END_OUTPUT}")
"""

    def _parse_single_case_output(
        self, case_output: str, stderr: str, exit_code: int, case_index: int
    ) -> tuple:
        """Parse output for a single test case in batch execution."""
        try:
            data = json.loads(case_output)
            parsed_result = data.get("result")
            case_stdout = data.get("stdout", "")
            time_ms = data.get("time_ms", 0)
            mem_bytes = data.get("mem_bytes", 0)
            profile_info = {"time_ms": time_ms, "mem_bytes": mem_bytes}
            error = data.get("error")
            case_specific_stderr = ""
            case_exit_code = 1 if error else 0
            if error:
                # Try to extract error marker from stderr
                stderr_lines = stderr.strip().splitlines()
                for err_line in stderr_lines:
                    if (
                        err_line.startswith(self.FUNCTION_ERROR_MARKER)
                        and f"Test case {case_index}" in err_line
                    ):
                        case_specific_stderr = err_line
                        break
                if not case_specific_stderr:
                    case_specific_stderr = error
            return (
                parsed_result,
                case_stdout,
                case_specific_stderr,
                case_exit_code,
                None,
                None,
                profile_info,
            )
        except Exception as e:
            return (
                None,
                "",
                f"Failed to parse output for case {case_index}: {e}",
                1,
                None,
                None,
                None,
            )
