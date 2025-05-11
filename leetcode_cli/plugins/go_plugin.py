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

    def run_many(self, workdir, function_name, input_args_list, input_data_list=None):
        self.ensure_image()
        wrapper_path = self._prepare_workspace(workdir, function_name)
        container_name = self._container_name(workdir)
        start_hot_container(self.docker_image, workdir, container_name)
        build_cmd = ["go", "build", "-o", "solution_bin", "main.go", self.solution_filename]
        _, build_stderr, build_exit = exec_in_hot_container(container_name, build_cmd)
        results = []
        if build_exit != 0:
            try:
                os.remove(wrapper_path)
            except Exception:
                pass
            for _ in input_args_list:
                results.append((None, "", build_stderr, build_exit, None, None, None))
            return results
        try:
            for i, input_args in enumerate(input_args_list):
                input_data = input_data_list[i] if input_data_list else None
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
                results.append((result, extra_stdout, stderr, exit_code, None, None, profile_info))
        finally:
            try:
                os.remove(wrapper_path)
                os.remove(os.path.join(workdir, "solution_bin"))
            except Exception:
                pass
        return results