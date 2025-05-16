import json
import os

from challenge_cli.plugins.docker_utils import execute_in_container

from ..language_plugin import LanguagePlugin


class JavaScriptPlugin(LanguagePlugin):
    """JavaScript language plugin for the Challenge CLI."""

    name = "javascript"
    aliases = ["js", "node"]
    docker_image = "javascript-runner:18"
    dockerfile_path = os.path.join(
        os.path.dirname(__file__), "dockerfiles", "Dockerfile.javascript"
    )
    solution_filename = "solution.js"

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

    def _get_driver_filename(self) -> str:
        """Get the filename for the test driver file."""
        return "test_driver.js"

    def _get_batch_command(self, driver_path: str) -> list:
        """Get the command to run for batch testing."""
        return ["node", "test_driver.js"]

    def _handle_dependencies(self, workdir: str, container_name: str, config) -> None:
        """Handle npm dependencies if package.json exists."""
        if not config.cache.dependency_cache:
            return

        package_json = os.path.join(workdir, "package.json")
        if os.path.exists(package_json):
            container_workdir = self._get_container_workdir(workdir)

            # Install dependencies using cached node_modules
            install_cmd = [
                "npm",
                "install",
                "--no-save",  # Don't modify package.json
                "--prefer-offline",  # Use cache when possible
            ]

            execute_in_container(
                container_name, install_cmd, working_dir=container_workdir
            )

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
