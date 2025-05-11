import os
import json
from .language_plugin import LanguagePlugin
from .docker_utils import (
    ensure_docker_image,
    start_hot_container,
    exec_in_hot_container,
)

# WRAPPER_TEMPLATE for JavaScript:
# - Takes JSON args from process.argv
# - Calls the user's function
# - Measures function-only time and memory
# - Prints LEETCODE_PROFILE marker
# - Prints result as JSON
JS_WRAPPER_TEMPLATE = """
const {{ Solution }} = require('./solution');

// Process CLI arguments as JSON
const args = process.argv.slice(2).map(arg => JSON.parse(arg));
const solution = new Solution();

// Start memory and time profiling
const startMemory = process.memoryUsage().heapUsed;
const startTime = process.hrtime.bigint();

// Call the function
const result = solution.{function_name}(...args);

// End profiling
const endTime = process.hrtime.bigint();
const endMemory = process.memoryUsage().heapUsed;

// Calculate metrics
const timeMs = Number(endTime - startTime) / 1_000_000;
const memBytes = endMemory - startMemory;

// Print profile info and result
console.log(`LEETCODE_PROFILE: ${{JSON.stringify({{
    time_ms: timeMs,
    mem_bytes: memBytes
}})}}`);
console.log(JSON.stringify(result));
"""

# Test driver for batch execution
JS_TEST_DRIVER_TEMPLATE = """
const fs = require('fs');
const {{ Solution }} = require('./solution');

try {{
    // Read inputs from JSON file
    const batchInputs = JSON.parse(fs.readFileSync('inputs.json', 'utf8'));
    const solution = new Solution();
    
    // Process each input set
    for (const args of batchInputs) {{
        try {{
            // Start profiling
            const startMemory = process.memoryUsage().heapUsed;
            const startTime = process.hrtime.bigint();
            
            // Call the solution function
            const result = solution.{function_name}(...args);
            
            // End profiling
            const endTime = process.hrtime.bigint();
            const endMemory = process.memoryUsage().heapUsed;
            
            // Calculate metrics
            const timeMs = Number(endTime - startTime) / 1_000_000;
            const memBytes = endMemory - startMemory;
            
            console.log(JSON.stringify(result));
            console.log(`PROFILE_TIME_MS: ${{timeMs}}`);
            console.log(`PROFILE_MEM_BYTES: ${{memBytes}}`);
        }} catch (error) {{
            console.error(`FUNCTION_ERROR: ${{error.message}}`);
            console.log(JSON.stringify("ERROR_RESULT"));
            console.log(`PROFILE_TIME_MS: 0`);
            console.log(`PROFILE_MEM_BYTES: 0`);
        }}
        console.log("---SEPARATOR---");
    }}
    console.log("---END_OUTPUT---");
}} catch (error) {{
    console.error(`PROFILE_ERROR: ${{error.message}}`);
    console.log("---SEPARATOR---");
    console.log("---END_OUTPUT---");
    process.exit(1);
}}
"""

class JavaScriptPlugin(LanguagePlugin):
    """
    JavaScript language plugin for the LeetCode CLI.
    - Uses a hot Docker container for fast repeated runs.
    - Injects a wrapper for function-only profiling.
    - Parses and returns result, extra stdout, and profile info.
    """

    name = "javascript"
    docker_image = "leetcode-javascript-runner:18"
    dockerfile_path = os.path.join(os.path.dirname(__file__), "dockerfiles", "Dockerfile.javascript")
    solution_filename = "solution.js"

    @staticmethod
    def solution_template(function_name="solve"):
        """
        Returns a template for a new JavaScript solution file.
        """
        return f"""/**
 * @class Solution
 */
class Solution {{
    /**
     * @param {{number[]}} nums
     * @param {{number}} target
     * @return {{number[]}}
     */
    {function_name}(nums, target) {{
        // Example: Two Sum implementation
        const map = new Map();
        
        for (let i = 0; i < nums.length; i++) {{
            const complement = target - nums[i];
            if (map.has(complement)) {{
                return [map.get(complement), i];
            }}
            map.set(nums[i], i);
        }}
        
        return [];
    }}
}}

module.exports = {{ Solution }};
"""

    def ensure_image(self):
        """
        Ensure the Docker image is available (builds if needed).
        """
        ensure_docker_image(self.docker_image, self.dockerfile_path, context_dir=os.path.dirname(self.dockerfile_path))

    def _prepare_workspace(self, workdir, function_name):
        """
        Write the wrapper (main.js) into the workspace.
        Returns the path to the wrapper file.
        """
        wrapper_code = JS_WRAPPER_TEMPLATE.format(function_name=function_name)
        wrapper_path = os.path.join(workdir, "main.js")
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)
        return wrapper_path

    def _container_name(self, workdir):
        return super()._container_name(workdir)

    def run(self, workdir, function_name, input_args, input_data=None):
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        command = ["node", "main.js"] + [json.dumps(arg) for arg in input_args]
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
        
        driver_filename = "test_driver.js"
        driver_code_path = os.path.join(workdir, driver_filename)
        
        final_results = []

        try:
            # 1. Create inputs.json
            inputs_json_str = json.dumps(input_args_list)
            with open(inputs_json_path, "w") as f:
                f.write(inputs_json_str)

            # 2. Create test_driver.js
            driver_code = JS_TEST_DRIVER_TEMPLATE.format(function_name=function_name)
            with open(driver_code_path, "w") as f:
                f.write(driver_code)

            # 3. Execute the driver script
            command = ["node", driver_filename]
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
                stderr_lines = stderr.strip().splitlines()
                function_error_messages = [line for line in stderr_lines if line.startswith("FUNCTION_ERROR:")]

                for i, case_output_str in enumerate(case_outputs_str_list):
                    if not case_output_str.strip():
                        continue
                        
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
                        if lines[0] == '""ERROR_RESULT""' or lines[0] == '"ERROR_RESULT"':
                            parsed_result = "Error in user function"
                            case_exit_code = 1
                            # Try to find a relevant error message
                            if i < len(function_error_messages):
                                case_specific_stderr = function_error_messages[i]
                            elif function_error_messages:
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