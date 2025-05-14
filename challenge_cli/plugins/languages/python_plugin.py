import json
import os

from ..docker_utils import (
    ensure_docker_image,
    execute_in_container,  # Use new name
    start_hot_container,
)
from ..language_plugin import LanguagePlugin


class PythonPlugin(LanguagePlugin):
    """
    Python language plugin for the Challenge CLI.

    Uses enhanced LanguagePlugin base class with common template functionality.
    """

    name = "python"
    aliases = ["py"]
    docker_image = "python-runner:3.12"
    dockerfile_path = os.path.join(
        os.path.dirname(__file__), "dockerfiles", "Dockerfile.python"
    )
    solution_filename = "solution.py"

    def ensure_image(self):
        """Ensure the Docker image is available (builds if needed)."""
        ensure_docker_image(
            self.docker_image,
            self.dockerfile_path,
            context_dir=os.path.dirname(self.dockerfile_path),
        )

    @staticmethod
    def solution_template(function_name="solve"):
        print(function_name)
        """Returns a template for a new Python solution file."""
        return f'''class Solution:
    def {function_name}(self, param1, param2):
        """
        Replace this with the actual function signature.
        """
        pass
    '''

    def generate_wrapper_template(self, function_name: str) -> str:
        """Generate Python wrapper for single test execution."""
        return f"""
import sys
import json
import time
import tracemalloc
from solution import Solution

if __name__ == "__main__":
    args = [json.loads(arg) for arg in sys.argv[1:]]
    sol = Solution()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = sol.{function_name}(*args)
    t1 = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print("{self.PROFILE_MARKER} " + json.dumps({{
        "time_ms": (t1-t0)*1000,
        "mem_bytes": peak
    }}))
    print(json.dumps(result))
"""

    def generate_test_driver_template(self, function_name: str) -> str:
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

    def run(
        self, workdir: str, function_name: str, input_args: list, input_data: str = None
    ) -> tuple:
        """Run a single test case."""
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)

        command = ["python", "main.py"] + [json.dumps(arg) for arg in input_args]
        stdout, stderr, exit_code = execute_in_container(
            container_name, command, input_data=input_data
        )

        stdout_lines = stdout.rstrip().splitlines()
        result, extra_stdout, profile_info = self._parse_profile_output(stdout_lines)

        self._cleanup_files(wrapper_path)

        return result, extra_stdout, stderr, exit_code, None, None, profile_info

    def run_many(
        self,
        workdir: str,
        function_name: str,
        input_args_list: list,
        input_data_list: list = None,
    ) -> list:
        """Run multiple test cases efficiently."""
        self.ensure_image()
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)

        inputs_json_path = os.path.join(workdir, "inputs.json")
        driver_path = os.path.join(workdir, "test_driver.py")

        try:
            # Write inputs
            with open(inputs_json_path, "w") as f:
                json.dump(input_args_list, f)

            # Write driver
            driver_code = self.generate_test_driver_template(function_name)
            with open(driver_path, "w") as f:
                f.write(driver_code)

            # Execute
            command = ["python", "test_driver.py"]
            stdout, stderr, exit_code = execute_in_container(
                container_name, command, input_data=None
            )

            # Parse results using common helper
            return self._parse_batch_output(stdout, stderr, exit_code, input_args_list)

        finally:
            self._cleanup_files(inputs_json_path, driver_path)

    def _prepare_workspace(self, workdir: str, function_name: str) -> str:
        """Write the wrapper (main.py) into the workspace."""
        wrapper_code = self.generate_wrapper_template(function_name)
        wrapper_path = os.path.join(workdir, "main.py")
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)
        return wrapper_path

    def _parse_profile_output(self, stdout_lines: list) -> tuple:
        """Parse stdout to extract result and profile info."""
        profile_info = None
        result_line = ""
        extra_stdout = []

        for line in stdout_lines:
            if line.startswith(self.PROFILE_MARKER):
                try:
                    profile_json = line.replace(self.PROFILE_MARKER, "").strip()
                    profile_info = json.loads(profile_json)
                except Exception:
                    profile_info = None
            else:
                result_line = line
                extra_stdout.append(line)

        # Remove the result line from extra stdout if it's the last line
        if extra_stdout and extra_stdout[-1] == result_line:
            extra_stdout = extra_stdout[:-1]

        extra_stdout_str = "\n".join(extra_stdout)

        # Parse result
        try:
            result = json.loads(result_line)
        except Exception:
            result = result_line

        return result, extra_stdout_str, profile_info

    def _parse_single_case_output(
        self, case_output: str, stderr: str, exit_code: int, case_index: int
    ) -> tuple:
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
