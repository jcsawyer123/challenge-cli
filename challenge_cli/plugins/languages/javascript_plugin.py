import json
import os

from ..docker_utils import (
    ensure_docker_image,
    execute_in_container,  # Use new name
    start_hot_container,
)
from ..language_plugin import LanguagePlugin


class JavaScriptPlugin(LanguagePlugin):
    """
    JavaScript language plugin for the Challenge CLI.

    Uses enhanced LanguagePlugin base class with common template functionality.
    """

    name = "javascript"
    aliases = ["js", "node"]
    docker_image = "javascript-runner:18"
    dockerfile_path = os.path.join(
        os.path.dirname(__file__), "dockerfiles", "Dockerfile.javascript"
    )
    solution_filename = "solution.js"

    def ensure_image(self):
        """Ensure the Docker image is available (builds if needed)."""
        ensure_docker_image(
            self.docker_image,
            self.dockerfile_path,
            context_dir=os.path.dirname(self.dockerfile_path),
        )

    @staticmethod
    def solution_template(function_name="solve"):
        """Returns a template for a new JavaScript solution file."""
        return f"""/**
* @class Solution
*/
class Solution {{
    /**
    * @param {{*}} param1
    * @param {{*}} param2
    * @return {{*}}
    */
    {function_name}(param1, param2) {{
        // Your solution here
        return [];
    }}
}}

module.exports = {{ Solution }};
"""

    def generate_wrapper_template(self, function_name: str) -> str:
        """Generate JavaScript wrapper for single test execution."""
        return f"""
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
console.log(`{self.PROFILE_MARKER} ${{JSON.stringify({{
    time_ms: timeMs,
    mem_bytes: memBytes
}})}}`);
console.log(JSON.stringify(result));
"""

    def generate_test_driver_template(self, function_name: str) -> str:
        """Generate JavaScript test driver for batch execution."""
        return f"""
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
            console.error(`{self.FUNCTION_ERROR_MARKER} ${{error.message}}`);
            console.log(JSON.stringify("ERROR_RESULT"));
            console.log(`PROFILE_TIME_MS: 0`);
            console.log(`PROFILE_MEM_BYTES: 0`);
        }}
        console.log("{self.SEPARATOR}");
    }}
    console.log("{self.END_OUTPUT}");
}} catch (error) {{
    console.error(`{self.ERROR_MARKER} ${{error.message}}`);
    console.log("{self.SEPARATOR}");
    console.log("{self.END_OUTPUT}");
    process.exit(1);
}}
"""  # noqa: W293

    def run(
        self, workdir: str, function_name: str, input_args: list, input_data: str = None
    ) -> tuple:
        """Run a single test case."""
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)

        command = ["node", "main.js"] + [json.dumps(arg) for arg in input_args]
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
        driver_path = os.path.join(workdir, "test_driver.js")

        try:
            # Write inputs
            with open(inputs_json_path, "w") as f:
                json.dump(input_args_list, f)

            # Write driver
            driver_code = self.generate_test_driver_template(function_name)
            with open(driver_path, "w") as f:
                f.write(driver_code)

            # Execute
            command = ["node", "test_driver.js"]
            stdout, stderr, exit_code = execute_in_container(
                container_name, command, input_data=None
            )

            # Parse results using common helper
            return self._parse_batch_output(stdout, stderr, exit_code, input_args_list)

        finally:
            self._cleanup_files(inputs_json_path, driver_path)

    def _prepare_workspace(self, workdir: str, function_name: str) -> str:
        """Write the wrapper (main.js) into the workspace."""
        wrapper_code = self.generate_wrapper_template(function_name)
        wrapper_path = os.path.join(workdir, "main.js")
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
        """Parse output for a single test case in batch execution."""
        lines = case_output.splitlines()
        if not lines:
            return (
                "Malformed case output",
                "",
                "Empty output for case",
                1,
                None,
                None,
                None,
            )

        parsed_result = "Error: Malformed case output"
        profile_info = None
        case_specific_stderr = ""
        case_exit_code = 1

        try:
            # Parse result
            if lines[0] in ['""ERROR_RESULT""', '"ERROR_RESULT"']:
                parsed_result = "Error in user function"
                case_exit_code = 1
                # Extract error message from stderr if available
                stderr_lines = stderr.strip().splitlines()
                for err_line in stderr_lines:
                    if err_line.startswith(self.FUNCTION_ERROR_MARKER):
                        case_specific_stderr = err_line
                        break
                if not case_specific_stderr:
                    case_specific_stderr = stderr
            else:
                parsed_result = json.loads(lines[0])
                case_exit_code = 0

            # Parse timing info
            if len(lines) > 1 and lines[1].startswith("PROFILE_TIME_MS:"):
                time_ms = float(lines[1].split(":", 1)[1].strip())
            else:
                time_ms = 0

            # Parse memory info
            if len(lines) > 2 and lines[2].startswith("PROFILE_MEM_BYTES:"):
                mem_bytes = int(lines[2].split(":", 1)[1].strip())
            else:
                mem_bytes = 0

            profile_info = {"time_ms": time_ms, "mem_bytes": mem_bytes}

        except Exception as e:
            parsed_result = f"Error parsing case output: {str(e)}"
            case_specific_stderr = (
                f"Original case output:\n{case_output}\nStderr:\n{stderr}"
            )
            case_exit_code = 1
            profile_info = None

        return (
            parsed_result,
            "",
            case_specific_stderr,
            case_exit_code,
            None,
            None,
            profile_info,
        )
