import os

# REpLACE THIS WITH THE ACTUAL LANGUAGE-SPECIFIC WRAPPER
WRAPPER_TEMPLATE = """
# --- IMPORTS (language-specific) ---
# import sys
# import json
# import time
# import memory_profiler (or equivalent)
# from solution import Solution (or language-specific import)

if __name__ == "__main__":
    # --- PARSE INPUT ARGUMENTS (language-specific) ---
    # args = [parse_arg(arg) for arg in sys.argv[1:]]
    # sol = Solution()  # or language-specific instantiation

    # --- START MEMORY PROFILING (language-specific) ---
    # memory_profiler.start()

    # --- START TIMER (language-specific) ---
    # t0 = current_time()

    # --- CALL THE FUNCTION/METHOD ---
    # result = sol.{function_name}(*args)

    # --- END TIMER ---
    # t1 = current_time()

    # --- END MEMORY PROFILING ---
    # mem_used = memory_profiler.peak()

    # --- PRINT FUNCTION-ONLY PROFILE INFO ---
    # print("LEETCODE_PROFILE: " + json.dumps({
    #     "time_ms": (t1-t0)*1000,
    #     "mem_bytes": mem_used
    # }))

    # --- PRINT THE RESULT (as JSON or language-appropriate) ---
    # print(json.dumps(result))
"""


class LanguagePlugin:
    """
    Base class for all language plugins.

    Each plugin must implement or override the following:

    Attributes:
        name (str): Unique string identifier for the language (e.g., "python").
        docker_image (str): The Docker image tag to use for this language.
        dockerfile_path (str): Path to the Dockerfile for this language.
        solution_filename (str): The expected filename for the user's solution (e.g., "solution.py").
        WRAPPER_TEMPLATE (str): A string template for a wrapper script that:
            - Parses input arguments
            - Calls the user's function/method
            - Measures function-only time and memory usage
            - Prints a marker line with profile info (e.g., "LEETCODE_PROFILE: ...")
            - Prints the function result as JSON or language-appropriate format

    Methods to implement/override:

    solution_template(function_name)
        Args:
            function_name (str): The function/method name to use in the template.
        Returns:
            str: The code template as a string.

    ensure_image()
        Ensures the Docker image is available (builds it if needed).
        No arguments. No return value.

    _prepare_workspace(workdir, function_name, wrapper_code)
        Args:
            workdir (str): Path to the problem directory (workspace).
            function_name (str): Name of the function/method to call.
            wrapper_code (str): The wrapper code to write.
        Returns:
            str: The path to the wrapper file created in the workspace.

    run(workdir, function_name, input_args, input_data=None)
        Runs a single test case.
        Args:
            workdir (str): Path to the problem directory (mounted as /workspace in Docker).
            function_name (str): Name of the function/method to call.
            input_args (list): List of arguments to pass to the function (should be JSON-serializable).
            input_data (str, optional): String to pass to stdin (if needed, e.g., for languages that use stdin).
        Returns:
            tuple:
                result (any): The parsed return value from the function (type depends on the problem).
                extra_stdout (str): Any extra stdout (e.g., print statements), may be empty.
                stderr (str): Stderr from the process.
                exit_code (int): Exit code from the process.
                exec_time (float or None): Wall time for the run (seconds), or None if not measured.
                max_rss_kb (int or None): Max memory used (KB), or None if not measured.
                profile_info (dict or None): Function-only profiling info, e.g., {"time_ms": float, "mem_bytes": int}, or None.

    run_many(workdir, function_name, input_args_list, input_data_list=None)
        Runs multiple test cases efficiently (e.g., in a persistent container).
        Args:
            workdir (str): Path to the problem directory.
            function_name (str): Name of the function/method to call.
            input_args_list (list of list): List of argument lists for each test case.
            input_data_list (list of str, optional): List of stdin strings for each test case.
        Returns:
            list of tuple: Each tuple is as described in `run()`.

    Notes:
        - All plugins should use the problem directory as the workspace.
        - All plugins should inject a wrapper for function-only profiling, and parse the result and profile info in a standard way.
        - The WRAPPER_TEMPLATE should be adapted for each language, following the pseudo-code pattern in the base class.
        - All arguments and return values should be documented in each plugin for clarity.
    """

    name = "base"
    docker_image = None
    dockerfile_path = os.path.join(os.path.dirname(__file__), "dockerfiles", "Dockerfile.language")
    solution_filename = "solution.txt"  # Override in plugin

    @staticmethod
    def solution_template(function_name="solve"):
        """
        Return a string with the default solution template for this language.

        Args:
            function_name (str): The function/method name to use in the template.

        Returns:
            str: The code template as a string.
        """
        raise NotImplementedError

    def ensure_image(self):
        """
        Ensure the Docker image for this plugin is available.
        Should build the image if it does not exist.
        """
        raise NotImplementedError

    def _prepare_workspace(self, workdir, function_name, wrapper_code):
        """
        Write the wrapper code into the workspace (problem directory).
        Returns the path to the wrapper file.
        """
        wrapper_path = self._prepare_workspace(workdir, function_name, WRAPPER_TEMPLATE.format(function_name=function_name))
        with open(wrapper_path, "w") as f:
            f.write(wrapper_code)
        return wrapper_path
    
    def _container_name(self, workdir):
        """
        Generate a unique container name for the hot container,
        based on language, image tag, and problem directory.

        Args:
            workdir (str): Path to the problem directory.

        Returns:
            str: Unique container name.
        """
        # Use only the image tag (not the full repo) for brevity
        image_tag = self.docker_image.replace(":", "-").replace("/", "-")
        problem_id = os.path.basename(os.path.abspath(workdir))
        return f"leetcode-hot-{self.name}-{image_tag}-{problem_id}"


    def run(self, workdir, function_name, input_args, input_data=None):
        """
        Run a single test case.

        Args:
            workdir (str): Path to the problem directory (mounted as /workspace).
            function_name (str): Name of the function/method to call.
            input_args (list): Arguments to pass to the function (JSON-serializable).
            input_data (str, optional): String to pass to stdin (if needed).

        Returns:
            tuple:
                result (any): Parsed return value from the function.
                extra_stdout (str): Any extra stdout (may be empty).
                stderr (str): Stderr from the process.
                exit_code (int): Process exit code.
                exec_time (float or None): Wall time for the run (seconds), or None.
                max_rss_kb (int or None): Max memory used (KB), or None.
                profile_info (dict or None): Function-only profiling info, e.g., {"time_ms": float, "mem_bytes": int}, or None.
        """
        raise NotImplementedError

    def run_many(self, workdir, function_name, input_args_list, input_data_list=None):
        """
        Run multiple test cases efficiently (e.g., in a persistent container).

        Args:
            workdir (str): Path to the problem directory.
            function_name (str): Name of the function/method to call.
            input_args_list (list of list): Arguments for each test case.
            input_data_list (list of str, optional): Stdin strings for each test case.

        Returns:
            list of tuple: Each tuple as described in `run()`.
        """
        results = []
        for i, input_args in enumerate(input_args_list):
            input_data = input_data_list[i] if input_data_list else None
            results.append(self.run(workdir, function_name, input_args, input_data=input_data))
        return results
