import os
import json
import shutil
from .language_plugin import LanguagePlugin
from .docker_utils import (
    ensure_docker_image,
    start_hot_container,
    exec_in_hot_container,
)

# WRAPPER_TEMPLATE for Go:
# - Reads args as JSON from os.Args[1:]
# - Calls the user's function
# - Measures function-only time and memory
# - Prints LEETCODE_PROFILE: {...}
# - Prints the result as JSON
GO_WRAPPER_TEMPLATE = """
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
    fmt.Printf("LEETCODE_PROFILE: %s\\n", toJson(map[string]interface{{}}{{
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

class GoPlugin(LanguagePlugin):
    """
    Go language plugin for the LeetCode CLI.
    - Uses a hot Docker container for fast repeated runs.
    - Injects a wrapper for function-only profiling.
    - Parses and returns result, extra stdout, and profile info.
    """

    name = "go"
    docker_image = "leetcode-go-runner:1.22"
    dockerfile_path = os.path.join(os.path.dirname(__file__), "dockerfiles", "Dockerfile.go")
    solution_filename = "solution.go"

    @staticmethod
    def solution_template(function_name="solve"):
        return f"""package main

    import "fmt"

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

    def test_driver_template(self, function_name):
        # Go driver that reads inputs from inputs.json, runs the user's function for each,
        # and prints profile info and results in a structured format.
        # Uses os.ReadFile (Go 1.16+)
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
        fmt.Fprintf(os.Stderr, "PROFILE_ERROR:Error reading inputs.json: %v\\n", err)
        fmt.Println("---SEPARATOR---") // To stdout for parser
        fmt.Println("---END_OUTPUT---")  // To stdout for parser
        os.Exit(1)
    }}

    var batchInputs [][]interface{{}}
    err = json.Unmarshal(inputData, &batchInputs)
    if err != nil {{
        fmt.Fprintf(os.Stderr, "PROFILE_ERROR:Error unmarshalling inputs.json: %v\\n", err)
        fmt.Println("---SEPARATOR---") // To stdout for parser
        fmt.Println("---END_OUTPUT---")  // To stdout for parser
        os.Exit(1)
    }}

    for _, singleCallArgs := range batchInputs {{
        if len(singleCallArgs) != 2 {{ // Assuming 2 parameters based on solution_template
            fmt.Fprintf(os.Stderr, "PROFILE_ERROR:Incorrect number of arguments for {function_name}. Expected 2, got %d\\n", len(singleCallArgs))
            fmt.Printf("PROFILE_TIME_MS: %.3f\\n", 0.0)
            fmt.Printf("PROFILE_MEM_BYTES: %d\\n", 0)
            errorResult := map[string]string{{"error": fmt.Sprintf("Incorrect number of arguments. Expected 2, got %d", len(singleCallArgs))}}
            fmt.Println(toJson(errorResult))
            fmt.Println("---SEPARATOR---")
            continue
        }}

        param1 := singleCallArgs[0]
        param2 := singleCallArgs[1]

        debug.FreeOSMemory()
        var mStart, mEnd runtime.MemStats
        runtime.ReadMemStats(&mStart)
        t0 := time.Now()

        result := {function_name}(param1, param2) // Direct call to user's function

        t1 := time.Now()
        runtime.ReadMemStats(&mEnd)
        
        memUsed := mEnd.Alloc - mStart.Alloc
        if memUsed < 0 {{ // Ensure memUsed is not negative
            memUsed = 0
        }}

        fmt.Printf("PROFILE_TIME_MS: %.3f\\n", float64(t1.Sub(t0).Microseconds()) / 1000.0)
        fmt.Printf("PROFILE_MEM_BYTES: %d\\n", memUsed)
        fmt.Println(toJson(result))
        fmt.Println("---SEPARATOR---")
    }}

    fmt.Println("---END_OUTPUT---")
}}

func toJson(v interface{{}}) string {{
    b, err := json.Marshal(v)
    if err != nil {{
        // Create a JSON-formatted error string
        errorMsg := fmt.Sprintf("{{\\"error\\": \\"Failed to marshal result to JSON: %s\\"}}", err.Error())
        return errorMsg
    }}
    return string(b)
}}
"""

    def ensure_image(self):
        # Ensures the Docker image is available (builds if needed).
        ensure_docker_image(self.docker_image, self.dockerfile_path, context_dir=os.path.dirname(self.dockerfile_path))

    def _prepare_workspace(self, workdir, function_name):
        # Writes the wrapper (main.go) into the workspace.
        wrapper_code = GO_WRAPPER_TEMPLATE.format(function_name=function_name)
        wrapper_path = os.path.join(workdir, "main.go")
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)
        return wrapper_path

    def _container_name(self, workdir):
        return f"leetcode-hot-go-1.22-{os.path.basename(workdir)}"

    def run(self, workdir, function_name, input_args, input_data=None):
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        build_cmd = ["go", "build", "-o", "solution_bin", "main.go", self.solution_filename]
        _, build_stderr, build_exit = exec_in_hot_container(container_name, build_cmd)
        if build_exit != 0:
            try:
                os.remove(wrapper_path)
            except Exception:
                pass
            return None, "", build_stderr, build_exit, None, None, None
        command = ["./solution_bin"] + [json.dumps(arg) for arg in input_args]
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
            os.remove(os.path.join(workdir, "solution_bin"))
        except Exception:
            pass
        return result, extra_stdout, stderr, exit_code, None, None, profile_info

    def _format_run_many_error_results(self, num_inputs, error_stdout, error_stderr, error_exit_code):
        """Helper to create a list of error result tuples for run_many."""
        error_results = []
        for _ in range(num_inputs):
            error_results.append((
                None,          # result
                error_stdout,
                error_stderr,
                error_exit_code,
                None,          # unused1 (was input_data placeholder)
                None,          # unused2 (was error_type placeholder)
                None           # profile_info
            ))
        return error_results

    def run_many(self, workdir, function_name, batch_inputs, input_data_list=None): # param input_args_list changed to batch_inputs
        self.ensure_image()

        inputs_json_path = os.path.join(workdir, "inputs.json")
        test_driver_code_path = os.path.join(workdir, "main.go")
        solution_bin_path = os.path.join(workdir, "solution_bin")

        try:
            # 1. Create inputs.json
            inputs_json_str = json.dumps(batch_inputs)
            with open(inputs_json_path, "w") as f:
                f.write(inputs_json_str)

            # 2. Get and write the batch test driver code
            driver_code = self.test_driver_template(function_name)
            with open(test_driver_code_path, "w") as f:
                f.write(driver_code)
            
            container_name = self._container_name(workdir)
            start_hot_container(self.docker_image, workdir, container_name)

            build_cmd = ["go", "build", "-o", "solution_bin", "main.go", self.solution_filename]
            _, build_stderr, build_exit = exec_in_hot_container(container_name, build_cmd)

            if build_exit != 0:
                return self._format_run_many_error_results(len(batch_inputs), "", build_stderr, build_exit)

            command = ["./solution_bin"]
            full_stdout, full_stderr, exit_code = exec_in_hot_container(container_name, command)
            
            parsed_results_tuples = []
            processed_cases = 0

            clean_stdout = full_stdout
            if clean_stdout.endswith("---END_OUTPUT---\n"):
                clean_stdout = clean_stdout[:-len("---END_OUTPUT---\n")]
            elif clean_stdout.endswith("---END_OUTPUT---"):
                clean_stdout = clean_stdout[:-len("---END_OUTPUT---")]
            
            raw_parts = clean_stdout.strip().split("---SEPARATOR---")
            
            for i, part_str in enumerate(raw_parts):
                part_str = part_str.strip()
                if not part_str:
                    if processed_cases < len(batch_inputs):
                        parsed_results_tuples.append((
                            "Error: Empty output segment for test case", "", full_stderr, exit_code, None, None, None
                        ))
                        processed_cases += 1
                    continue

                if processed_cases >= len(batch_inputs):
                    break

                lines = part_str.splitlines()
                profile_info = {}
                actual_result_json_str = ""
                current_stderr = full_stderr if exit_code != 0 else "" # Base stderr for this item

                try:
                    if len(lines) < 3: raise ValueError("Output part too short")
                    
                    if lines[0].startswith("PROFILE_TIME_MS:"):
                        profile_info["time_ms"] = float(lines[0].split(":", 1)[1].strip())
                    else: raise ValueError("Missing PROFILE_TIME_MS")
                    
                    if lines[1].startswith("PROFILE_MEM_BYTES:"):
                        profile_info["mem_bytes"] = int(lines[1].split(":", 1)[1].strip())
                    else: raise ValueError("Missing PROFILE_MEM_BYTES")
                    
                    actual_result_json_str = "\n".join(lines[2:])
                    parsed_actual_result = json.loads(actual_result_json_str)
                    
                    parsed_results_tuples.append((
                        parsed_actual_result, "", current_stderr, exit_code, None, None, profile_info
                    ))

                except (ValueError, IndexError, json.JSONDecodeError) as e:
                    error_msg = f"Error parsing output part: {e}. Content: '{part_str[:100]}...'"
                    combined_stderr = f"{current_stderr}\nParseError: {error_msg}".strip()
                    raw_res_if_json_failed = actual_result_json_str if actual_result_json_str else part_str
                    
                    parsed_results_tuples.append((
                        raw_res_if_json_failed, "", combined_stderr, exit_code, None, None,
                        profile_info if "time_ms" in profile_info and "mem_bytes" in profile_info else None
                    ))
                processed_cases += 1

            while processed_cases < len(batch_inputs):
                parsed_results_tuples.append((
                    "Error: No output for this test case (run may have been interrupted)",
                    "", full_stderr, exit_code, None, None, None
                ))
                processed_cases += 1
            
            return parsed_results_tuples[:len(batch_inputs)]

        finally:
            # Clean up generated files
            for p in [inputs_json_path, test_driver_code_path, solution_bin_path]:
                try:
                    if os.path.exists(p): os.remove(p)
                except OSError:
                    pass # Ignore cleanup errors