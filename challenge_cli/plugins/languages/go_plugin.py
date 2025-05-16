import json
import os

from challenge_cli.plugins.docker_utils import execute_in_container

from ..language_plugin import LanguagePlugin


class GoPlugin(LanguagePlugin):
    """Go language plugin for the Challenge CLI."""

    name = "go"
    aliases = ["golang"]
    docker_image = "go-runner:1.22"
    dockerfile_path = os.path.join(
        os.path.dirname(__file__), "dockerfiles", "Dockerfile.go"
    )
    solution_filename = "solution.go"

    @staticmethod
    def solution_template(function_name="solve"):
        """Returns a template for a new Go solution file."""
        return f"""package main

    // {function_name} receives LeetCode-style JSON input as interface{{}}.
    // Use the conversion code below to get concrete types.
    func {function_name}(param1 interface{{}}, param2 interface{{}}) interface{{}} {{
        // Example: Convert param1 to []int, param2 to int
        numsIface, ok1 := param1.([]interface{{}})
        targetFloat, ok2 := param2.(float64)
        if !ok1 || !ok2 {{
            return []int{{}}
        }}
        nums := make([]int, len(numsIface))
        for i, v := range numsIface {{
            nums[i] = int(v.(float64))
        }}
        target := int(targetFloat)

        // Your solution here
        // Example: two sum
        seen := make(map[int]int)
        for i, num := range nums {{
            complement := target - num
            if idx, found := seen[complement]; found {{
                return []int{{idx, i}}
            }}
            seen[num] = i
        }}
        return []int{{}}
    }}
"""

    def generate_test_driver_template(self, function_name: str) -> str:
        """Generate Go test driver for batch execution."""
        return f"""package main

import (
    "encoding/json"
    "fmt"
    "os"
    "runtime"
    "runtime/debug"
    "time"
)

// User's function {function_name}(param1 interface{{}}, param2 interface{{}}) interface{{}}
// is expected to be defined in the accompanying solution.go file.

func main() {{
    inputData, err := os.ReadFile("inputs.json")
    if err != nil {{
        fmt.Fprintf(os.Stderr, "{self.ERROR_MARKER}Error reading inputs.json: %v\\n", err)
        fmt.Println("{self.SEPARATOR}")
        fmt.Println("{self.END_OUTPUT}")
        os.Exit(1)
    }}

    var batchInputs [][]interface{{}}
    err = json.Unmarshal(inputData, &batchInputs)
    if err != nil {{
        fmt.Fprintf(os.Stderr, "{self.ERROR_MARKER}Error unmarshalling inputs.json: %v\\n", err)
        fmt.Println("{self.SEPARATOR}")
        fmt.Println("{self.END_OUTPUT}")
        os.Exit(1)
    }}

    for _, singleCallArgs := range batchInputs {{
        if len(singleCallArgs) != 2 {{
            fmt.Fprintf(os.Stderr, "{self.ERROR_MARKER}Incorrect number of arguments for {function_name}. Expected 2, got %d\\n", len(singleCallArgs))
            fmt.Printf("PROFILE_TIME_MS: %.3f\\n", 0.0)
            fmt.Printf("PROFILE_MEM_BYTES: %d\\n", 0)
            errorResult := map[string]string{{"error": fmt.Sprintf("Incorrect number of arguments. Expected 2, got %d", len(singleCallArgs))}}
            fmt.Println(toJson(errorResult))
            fmt.Println("{self.SEPARATOR}")
            continue
        }}

        param1 := singleCallArgs[0]
        param2 := singleCallArgs[1]

        debug.FreeOSMemory()
        var mStart, mEnd runtime.MemStats
        runtime.ReadMemStats(&mStart)
        t0 := time.Now()

        result := {function_name}(param1, param2)

        t1 := time.Now()
        runtime.ReadMemStats(&mEnd)
        
        memUsed := mEnd.Alloc - mStart.Alloc
        if memUsed < 0 {{
            memUsed = 0
        }}

        fmt.Printf("PROFILE_TIME_MS: %.3f\\n", float64(t1.Sub(t0).Microseconds()) / 1000.0)
        fmt.Printf("PROFILE_MEM_BYTES: %d\\n", memUsed)
        fmt.Println(toJson(result))
        fmt.Println("{self.SEPARATOR}")
    }}

    fmt.Println("{self.END_OUTPUT}")
}}

func toJson(v interface{{}}) string {{
    b, err := json.Marshal(v)
    if err != nil {{
        errorMsg := fmt.Sprintf("{{\\"error\\": \\"Failed to marshal result to JSON: %s\\"}}", err.Error())
        return errorMsg
    }}
    return string(b)
}}
"""  # noqa: W293

    def _get_driver_filename(self) -> str:
        """Get the filename for the test driver file."""
        return "main.go"  # For Go, we use the same filename

    def _get_batch_command(self, driver_path: str) -> list:
        """Get the command to run for batch testing."""
        # For Go, we need to build the binary first
        problems_dir = self._get_problems_dir(os.path.dirname(driver_path))
        workdir = os.path.dirname(driver_path)
        container_workdir = self._get_container_workdir(workdir)

        # Prepare cache directory
        cache_dir_path = os.path.join(workdir, ".cache")
        os.makedirs(cache_dir_path, exist_ok=True)

        output_path = self._to_container_path(
            os.path.join(cache_dir_path, "batch_solution.bin"), problems_dir
        )

        container_name = self._container_name(workdir)

        # Build
        build_cmd = [
            "go",
            "build",
            "-o",
            output_path,
            "main.go",
            self.solution_filename,
        ]

        _, build_stderr, build_exit = execute_in_container(
            container_name, build_cmd, working_dir=container_workdir
        )

        if build_exit != 0:
            raise RuntimeError(f"Build failed: {build_stderr}")

        return [output_path]

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
            # Go outputs start with PROFILE lines
            if len(lines) < 3:
                raise ValueError("Output too short")

            # Parse timing info (first line)
            if lines[0].startswith("PROFILE_TIME_MS:"):
                time_ms = float(lines[0].split(":", 1)[1].strip())
            else:
                raise ValueError("Missing PROFILE_TIME_MS")

            # Parse memory info (second line)
            if lines[1].startswith("PROFILE_MEM_BYTES:"):
                mem_bytes = int(lines[1].split(":", 1)[1].strip())
            else:
                raise ValueError("Missing PROFILE_MEM_BYTES")

            # Parse result (remaining lines)
            result_json = "\n".join(lines[2:])
            parsed_result = json.loads(result_json)
            case_exit_code = 0

            profile_info = {"time_ms": time_ms, "mem_bytes": mem_bytes}

        except (ValueError, json.JSONDecodeError) as e:
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
