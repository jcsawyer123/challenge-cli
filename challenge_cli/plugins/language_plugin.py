import os
from abc import ABC, abstractmethod

class LanguagePlugin(ABC):
    """
    Base class for all language plugins.

    Each plugin must implement or override the following:

    Attributes:
        name (str): Unique string identifier for the language (e.g., "python").
        docker_image (str): The Docker image tag to use for this language.
        dockerfile_path (str): Path to the Dockerfile for this language.
        solution_filename (str): The expected filename for the user's solution (e.g., "solution.py").
    """

    name = "base"
    docker_image = None
    dockerfile_path = None
    solution_filename = None

    @staticmethod
    @abstractmethod
    def solution_template(function_name="solve"):
        """
        Return a string with the default solution template for this language.

        Args:
            function_name (str): The function/method name to use in the template.

        Returns:
            str: The code template as a string.
        """
        pass

    @abstractmethod
    def ensure_image(self):
        """
        Ensure the Docker image for this plugin is available.
        Should build the image if it does not exist.
        """
        pass

    @abstractmethod
    def run(self, workdir, function_name, input_args, input_data=None):
        """
        Run a single test case.

        Args:
            workdir (str): Path to the language-specific directory (mounted as /workspace).
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
        pass

    @abstractmethod
    def run_many(self, workdir, function_name, input_args_list, input_data_list=None):
        """
        Run multiple test cases efficiently (e.g., in a persistent container).

        Args:
            workdir (str): Path to the language-specific directory.
            function_name (str): Name of the function/method to call.
            input_args_list (list of list): Arguments for each test case.
            input_data_list (list of str, optional): Stdin strings for each test case.

        Returns:
            list of tuple: Each tuple as described in `run()`.
        """
        pass
        
    def _container_name(self, workdir):
        """
        Generate a unique container name for the hot container,
        based on platform, language, image tag, and challenge path.

        Args:
            workdir (str): Path to the language-specific directory.

        Returns:
            str: Unique container name.
        """
        # Extract platform and challenge path from directory structure
        # workdir pattern: problems_dir/platform/challenge_path/language
        language_dir = os.path.abspath(workdir)
        challenge_dir = os.path.dirname(language_dir)
        platform = os.path.basename(os.path.dirname(challenge_dir))
        challenge_path = os.path.basename(challenge_dir)
        
        # Clean up image tag to make it a valid container name
        image_tag = self.docker_image.replace(":", "-").replace("/", "-")
        
        # Make challenge path safe for use in container name
        safe_challenge = challenge_path.replace("/", "-").replace("\\", "-")
        
        return f"challenge-{platform}-{safe_challenge}-{self.name}-{image_tag}"