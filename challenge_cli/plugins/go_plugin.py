import os
import json
from .language_plugin import LanguagePlugin
from .docker_utils import (
    ensure_docker_image,
    start_hot_container,
    execute_in_container,  # Use new name
)
from challenge_cli.config import DOCKER_IMAGES, SOLUTION_TEMPLATES


class GoPlugin(LanguagePlugin):
    """
    Go language plugin for the Challenge CLI.
    
    Uses enhanced LanguagePlugin base class with common template functionality.
    Note: Go requires compilation before execution.
    """
    
    name = "go"
    docker_image = DOCKER_IMAGES.get('go', 'leetcode-go-runner:1.22')
    dockerfile_path = os.path.join(os.path.dirname(__file__), "dockerfiles", "Dockerfile.go")
    solution_filename = "solution.go"
    
    @staticmethod
    def solution_template(function_name="solve"):
        """Returns a template for a new Go solution file."""
        template = SOLUTION_TEMPLATES.get('go', '''package main

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
''')
        return template.format(function_name=function_name)
    
    def ensure_image(self):
        """Ensure the Docker image is available (builds if needed)."""
        ensure_docker_image(self.docker_image, self.dockerfile_path, context_dir=os.path.dirname(self.dockerfile_path))
    
    def generate_wrapper_template(self, function_name: str) -> str:
        """Generate Go wrapper for single test execution."""
        return f"""
package main

import (
    "encoding/json"
    "fmt"
    "os"
    "time"
    "runtime"
    "runtime/debug"
)

func main() {{
    // Parse input args (as JSON)
    args := os.Args[1:]
    var param1, param2 interface{{}}
    json.Unmarshal([]byte(args[0]), &param1)
    json.Unmarshal([]byte(args[1]), &param2)

    // Start memory and time profiling
    debug.FreeOSMemory()
    var mStart, mEnd runtime.MemStats
    runtime.ReadMemStats(&mStart)
    t0 := time.Now()

    // Call the function
    result := {function_name}(param1, param2)

    t1 := time.Now()
    runtime.ReadMemStats(&mEnd)
    peakMem := mEnd.Alloc - mStart.Alloc

    // Print profile info
    fmt.Printf("{self.PROFILE_MARKER} %s\\n", toJson(map[string]interface{{}}{{
        "time_ms": float64(t1.Sub(t0).Microseconds()) / 1000.0,
        "mem_bytes": peakMem,
    }}))

    // Print result as JSON
    fmt.Println(toJson(result))
}}

func toJson(v interface{{}}) string {{
    b, _ := json.Marshal(v)
    return string(b)
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
"""
    
    def run(self, workdir: str, function_name: str, input_args: list, input_data: str = None) -> tuple:
        """Run a single test case. Go requires compilation first."""
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        
        # Build the Go binary
        build_cmd = ["go", "build", "-o", "solution_bin", "main.go", self.solution_filename]
        _, build_stderr, build_exit = execute_in_container(container_name, build_cmd)
        
        if build_exit != 0:
            self._cleanup_files(wrapper_path)
            return None, "", build_stderr, build_exit, None, None, None
        
        # Run the binary
        command = ["./solution_bin"] + [json.dumps(arg) for arg in input_args]
        stdout, stderr, exit_code = execute_in_container(
            container_name, command, input_data=input_data
        )
        
        stdout_lines = stdout.rstrip().splitlines()
        result, extra_stdout, profile_info = self._parse_profile_output(stdout_lines)
        
        # Clean up
        self._cleanup_files(wrapper_path, os.path.join(workdir, "solution_bin"))
        
        return result, extra_stdout, stderr, exit_code, None, None, profile_info
    
    def run_many(self, workdir: str, function_name: str, input_args_list: list, input_data_list: list = None) -> list:
        """Run multiple test cases efficiently. Go requires compilation first."""
        self.ensure_image()
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        
        inputs_json_path = os.path.join(workdir, 'inputs.json')
        driver_path = os.path.join(workdir, 'main.go')
        solution_bin_path = os.path.join(workdir, 'solution_bin')
        
        try:
            # Write inputs
            with open(inputs_json_path, 'w') as f:
                json.dump(input_args_list, f)
            
            # Write driver
            driver_code = self.generate_test_driver_template(function_name)
            with open(driver_path, 'w') as f:
                f.write(driver_code)
            
            # Build
            build_cmd = ["go", "build", "-o", "solution_bin", "main.go", self.solution_filename]
            _, build_stderr, build_exit = execute_in_container(container_name, build_cmd)
            
            if build_exit != 0:
                return self._create_error_results(len(input_args_list), "", build_stderr, build_exit)
            
            # Execute
            command = ["./solution_bin"]
            stdout, stderr, exit_code = execute_in_container(container_name, command)
            
            # Parse results using common helper
            return self._parse_batch_output(stdout, stderr, exit_code, input_args_list)
            
        finally:
            self._cleanup_files(inputs_json_path, driver_path, solution_bin_path)
    
    def _prepare_workspace(self, workdir: str, function_name: str) -> str:
        """Write the wrapper (main.go) into the workspace."""
        wrapper_code = self.generate_wrapper_template(function_name)
        wrapper_path = os.path.join(workdir, "main.go")
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
    
    def _parse_single_case_output(self, case_output: str, stderr: str, exit_code: int, case_index: int) -> tuple:
        """Parse output for a single test case in batch execution."""
        lines = case_output.splitlines()
        if not lines:
            return ("Malformed case output", "", "Empty output for case", 1, None, None, None)
        
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
            case_specific_stderr = f"Original case output:\n{case_output}\nStderr:\n{stderr}"
            case_exit_code = 1
            profile_info = None
        
        return (parsed_result, "", case_specific_stderr, case_exit_code, None, None, profile_info)