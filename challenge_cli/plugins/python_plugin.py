import os
import json
from .language_plugin import LanguagePlugin
from .docker_utils import (
    ensure_docker_image,
    start_hot_container,
    exec_in_hot_container,
)

# WRAPPER_TEMPLATE: Injected into the workspace as main.py.
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
    
    Uses a hot Docker container for fast repeated runs, injects a wrapper
    for function-only profiling, and parses results with performance metrics.
    
    The wrapper template:
    - Parses input args as JSON from sys.argv[1:]
    - Calls the user's function/method
    - Measures function-only time and memory (tracemalloc)
    - Prints a marker line: LEETCODE_PROFILE: {"time_ms": float, "mem_bytes": int}
    - Prints the function result as JSON
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

    def test_driver_template(self, function_name, solution_filename):
        solution_module_name = solution_filename.split('.')[0]
        return f"""
import sys
import json
import time
import tracemalloc
from {solution_module_name} import Solution

if __name__ == "__main__":
    batch_inputs = []
    try:
        with open("inputs.json", "r") as f:
            batch_inputs_json = f.read()
        batch_inputs = json.loads(batch_inputs_json)
    except Exception as e:
        print(f"PROFILE_ERROR:Error loading or parsing inputs.json: {{e}}", file=sys.stderr)
        print("---SEPARATOR---", file=sys.stdout)
        print("---END_OUTPUT---", file=sys.stdout)
        sys.exit(1)

    sol = Solution()
    results_output = []

    for i, args_for_call in enumerate(batch_inputs):
        case_stdout_lines = []
        try:
            tracemalloc.start()
            t0 = time.perf_counter()
            
            result = sol.{function_name}(*args_for_call)
            
            t1 = time.perf_counter()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            case_stdout_lines.append(json.dumps(result))
            case_stdout_lines.append(f"PROFILE_TIME_MS: {{(t1 - t0) * 1000}}")
            case_stdout_lines.append(f"PROFILE_MEM_BYTES: {{peak}}")

        except Exception as call_e:
            # Ensure tracemalloc is stopped if it was started
            if tracemalloc.is_tracing():
                tracemalloc.stop()
            print(f"FUNCTION_ERROR: Test case {{i}}: {{call_e}}", file=sys.stderr)
            case_stdout_lines.append(json.dumps("ERROR_RESULT")) # Standardized error result
            case_stdout_lines.append(f"PROFILE_TIME_MS: 0")
            case_stdout_lines.append(f"PROFILE_MEM_BYTES: 0")
        
        results_output.append("\\n".join(case_stdout_lines))

    print("\\n---SEPARATOR---\\n".join(results_output))
    print("---END_OUTPUT---")
"""

    def _container_name(self, workdir):
        return super()._container_name(workdir)

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
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)

        inputs_json_filename = "inputs.json"
        inputs_json_path = os.path.join(workdir, inputs_json_filename)
        
        driver_filename = "test_driver.py"
        driver_code_path = os.path.join(workdir, driver_filename)
        
        final_results = []

        try:
            # 1. Create inputs.json
            inputs_json_str = json.dumps(input_args_list)
            with open(inputs_json_path, "w") as f:
                f.write(inputs_json_str)

            # 2. Create test_driver.py
            driver_code = self.test_driver_template(function_name, self.solution_filename)
            with open(driver_code_path, "w") as f:
                f.write(driver_code)

            # 3. Execute the driver script
            # solution_code_path is os.path.join(workdir, self.solution_filename)
            # All necessary files (solution.py, test_driver.py, inputs.json) are in workdir.
            command = ["python", driver_filename]
            stdout, stderr, exit_code = exec_in_hot_container(
                container_name, command, input_data=None
            )

            # 4. Parse output
            if exit_code != 0 and "PROFILE_ERROR:" in stderr:
                # Driver failed to load inputs or other critical setup error
                final_results.append(("Batch execution failed due to driver error", "", stderr, exit_code, None, None, None))
            elif "---END_OUTPUT---" not in stdout:
                # Malformed output, missing END_OUTPUT marker
                error_message = "Execution failed or malformed output (missing ---END_OUTPUT---)"
                if stdout.strip(): error_message += f"\nStdout: {stdout}"
                if stderr.strip(): error_message += f"\nStderr: {stderr}"
                final_results.append((error_message, "", stderr, exit_code, None, None, None))
            else:
                main_output_block = stdout.split("---END_OUTPUT---")[0].strip()
                case_outputs_str_list = main_output_block.split("---SEPARATOR---")
                
                # Correlate stderr FUNCTION_ERROR messages if any
                # This is a simple correlation; complex scenarios might need more robust parsing.
                stderr_lines = stderr.strip().splitlines()
                function_error_messages = [line for line in stderr_lines if line.startswith("FUNCTION_ERROR:")]

                for i, case_output_str in enumerate(case_outputs_str_list):
                    lines = case_output_str.strip().splitlines()
                    if not lines:
                        if i < len(input_args_list): # Avoid adding result if there are no more inputs
                             final_results.append(("Malformed case output", "", "Empty output for case", 1, None, None, None))
                        continue

                    parsed_result = "Error: Malformed case output"
                    profile_info = None
                    case_specific_stderr = ""
                    case_exit_code = 1 # Default to error for the case

                    try:
                        # Line 0: result_json or "ERROR_RESULT"
                        if lines[0] == '""ERROR_RESULT""' or lines[0] == '"ERROR_RESULT"': # Handle potential extra quotes from json.dumps("ERROR_RESULT")
                            parsed_result = "Error in user function"
                            case_exit_code = 1
                            # Try to find a relevant error message
                            if i < len(function_error_messages):
                                case_specific_stderr = function_error_messages[i]
                            elif function_error_messages: # If fewer errors than cases, assign last one or general stderr
                                case_specific_stderr = stderr # Fallback to global stderr
                        else:
                            parsed_result = json.loads(lines[0])
                            case_exit_code = 0
                        
                        # Line 1: PROFILE_TIME_MS
                        time_ms_str = lines[1].split("PROFILE_TIME_MS:", 1)[1].strip()
                        time_ms = float(time_ms_str)
                        
                        # Line 2: PROFILE_MEM_BYTES
                        mem_bytes_str = lines[2].split("PROFILE_MEM_BYTES:", 1)[1].strip()
                        mem_bytes = int(mem_bytes_str)
                        
                        profile_info = {"time_ms": time_ms, "mem_bytes": mem_bytes}
                    except Exception as e:
                        # Parsing this specific case output failed.
                        parsed_result = f"Error parsing case output: {str(e)}"
                        case_specific_stderr = f"Original case output:\n{case_output_str}\nStderr:\n{stderr}"
                        case_exit_code = 1
                        profile_info = None # Ensure profile_info is None if parsing fails

                    final_results.append((parsed_result, "", case_specific_stderr, case_exit_code, None, None, profile_info))
                
                # If there are more inputs than results, it implies later test cases failed to produce output.
                # This can happen if the driver script exits prematurely after some successful cases.
                # The global exit_code and stderr would be important here.
                if len(input_args_list) > len(final_results) and exit_code != 0:
                    num_missing = len(input_args_list) - len(final_results)
                    for _ in range(num_missing):
                        final_results.append(
                            ("Test case did not run or produce output (driver may have exited prematurely)",
                             "", stderr, exit_code, None, None, None)
                        )

        finally:
            if os.path.exists(inputs_json_path):
                try:
                    os.remove(inputs_json_path)
                except Exception:
                    pass
            if os.path.exists(driver_code_path):
                try:
                    os.remove(driver_code_path)
                except Exception:
                    pass
        
        return final_results