import os
import json
from .language_plugin import LanguagePlugin
from .docker_utils import (
    ensure_docker_image,
    start_hot_container,
    exec_in_hot_container,
)

# WRAPPER_TEMPLATE: Injected into the workspace as main.py.
# - Parses input args as JSON from sys.argv[1:]
# - Calls the user's function/method
# - Measures function-only time and memory (tracemalloc)
# - Prints a marker line: LEETCODE_PROFILE: {"time_ms": float, "mem_bytes": int}
# - Prints the function result as JSON
WRAPPER_TEMPLATE = """
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
    print("LEETCODE_PROFILE: " + json.dumps({{
        "time_ms": (t1-t0)*1000,
        "mem_bytes": peak
    }}))
    print(json.dumps(result))
"""

class PythonPlugin(LanguagePlugin):
    """
    Python language plugin for the LeetCode CLI.
    - Uses a hot Docker container for fast repeated runs.
    - Injects a wrapper for function-only profiling.
    - Parses and returns result, extra stdout, and profile info.
    """

    name = "python"
    docker_image = "leetcode-python-runner:3.12"
    dockerfile_path = os.path.join(os.path.dirname(__file__), "dockerfiles", "Dockerfile.python")
    solution_filename = "solution.py"

    @staticmethod
    def solution_template(function_name="solve"):
        """
        Returns a template for a new Python solution file.
        """
        return f"""class Solution:
    def {function_name}(self, param1, param2):
        \"\"\"
        Replace this with the actual function signature from LeetCode.
        For example:
        def twoSum(self, nums: List[int], target: int) -> List[int]:
            # Your solution here
            pass
        \"\"\"
        pass
"""

    def ensure_image(self):
        """
        Ensure the Docker image is available (builds if needed).
        """
        ensure_docker_image(self.docker_image, self.dockerfile_path, context_dir=os.path.dirname(self.dockerfile_path))

    def _prepare_workspace(self, workdir, function_name):
        """
        Write the wrapper (main.py) into the workspace.
        Returns the path to the wrapper file.
        """
        wrapper_code = WRAPPER_TEMPLATE.format(function_name=function_name)
        wrapper_path = os.path.join(workdir, "main.py")
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)
        return wrapper_path

    def _container_name(self, workdir):
        # Unique container per language and problem directory
        return f"leetcode-hot-python-3.12-{os.path.basename(workdir)}"

    def run(self, workdir, function_name, input_args, input_data=None):
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        command = ["python", "main.py"] + [json.dumps(arg) for arg in input_args]
        stdout, stderr, exit_code = exec_in_hot_container(
            container_name, command, input_data=input_data
        )
        stdout_lines = stdout.rstrip().splitlines()
        profile_info = None
        result_line = ""
        extra_stdout = []
        for line in stdout_lines:
            if line.startswith("LEETCODE_PROFILE:"):
                try:
                    profile_info = json.loads(line.replace("LEETCODE_PROFILE:", "").strip())
                except Exception:
                    profile_info = None
            else:
                result_line = line
                extra_stdout.append(line)
        if extra_stdout and extra_stdout[-1] == result_line:
            extra_stdout = extra_stdout[:-1]
        extra_stdout = "\n".join(extra_stdout)
        try:
            result = json.loads(result_line)
        except Exception:
            result = result_line
        try:
            os.remove(wrapper_path)
        except Exception:
            pass
        return result, extra_stdout, stderr, exit_code, None, None, profile_info

    def run_many(self, workdir, function_name, input_args_list, input_data_list=None):
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        results = []
        try:
            for i, input_args in enumerate(input_args_list):
                input_data = input_data_list[i] if input_data_list else None
                command = ["python", "main.py"] + [json.dumps(arg) for arg in input_args]
                stdout, stderr, exit_code = exec_in_hot_container(
                    container_name, command, input_data=input_data
                )
                stdout_lines = stdout.rstrip().splitlines()
                profile_info = None
                result_line = ""
                extra_stdout = []
                for line in stdout_lines:
                    if line.startswith("LEETCODE_PROFILE:"):
                        try:
                            profile_info = json.loads(line.replace("LEETCODE_PROFILE:", "").strip())
                        except Exception:
                            profile_info = None
                    else:
                        result_line = line
                        extra_stdout.append(line)
                if extra_stdout and extra_stdout[-1] == result_line:
                    extra_stdout = extra_stdout[:-1]
                extra_stdout = "\n".join(extra_stdout)
                try:
                    result = json.loads(result_line)
                except Exception:
                    result = result_line
                results.append((result, extra_stdout, stderr, exit_code, None, None, profile_info))
        finally:
            try:
                os.remove(wrapper_path)
            except Exception:
                pass
        return results