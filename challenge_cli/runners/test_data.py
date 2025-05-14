"""Test data management for challenges."""

import json
import os
from typing import Dict, Optional, Set

from challenge_cli.core.data_utils import load_json, parse_cases_arg, save_json

TESTCASES_TEMPLATE = """{
    "testcases": [
        {
            "input": ["param1_value", "param2_value"],
            "output": "expected_output"
        }
    ],
    "implementations": {
        "%s": {
            "function": "%s"
        }
    }
}
"""


class TestDataManager:
    """Manages test cases and challenge metadata."""

    def __init__(self, challenge_dir: str):
        """
        Initialize test data manager.

        Args:
            challenge_dir: Path to the challenge directory
        """
        self.challenge_dir = challenge_dir
        self.testcases_file = os.path.join(challenge_dir, "testcases.json")

    def load_testcases(self) -> Dict:
        """
        Load test cases from testcases.json.

        Returns:
            Dictionary containing test cases and implementations

        Raises:
            FileNotFoundError: If testcases.json doesn't exist
        """
        if not os.path.exists(self.testcases_file):
            raise FileNotFoundError(f"Test cases file not found: {self.testcases_file}")
        return load_json(self.testcases_file)

    def get_function_name(self, language: str) -> str:
        """
        Get the function name for a specific language.

        Args:
            language: Programming language

        Returns:
            Function name for the language

        Raises:
            ValueError: If no implementation found for language
        """
        testcases = self.load_testcases()
        implementations = testcases.get("implementations", {})

        if language in implementations:
            return implementations[language]["function"]

        # Check old format
        if "language" in testcases and testcases["language"] == language:
            return testcases.get("function", "solve")

        raise ValueError(f"No implementation found for language: {language}")

    def initialize_testcases_file(self, language: str, function_name: str) -> None:
        """
        Initialize or update the testcases.json file.

        Args:
            language: Programming language
            function_name: Name of the function
        """
        testcases_updated = False

        if os.path.exists(self.testcases_file):
            try:
                testcases = load_json(self.testcases_file)

                # Handle old format conversion
                if "language" in testcases and "function" in testcases:
                    # Convert from old format
                    old_language = testcases["language"]
                    old_function = testcases["function"]
                    old_testcases_list = testcases.get("testcases", [])

                    testcases = {
                        "testcases": old_testcases_list,
                        "implementations": {
                            old_language: {"function": old_function},
                            language: {"function": function_name},
                        },
                    }
                else:
                    # Update existing format
                    implementations = testcases.get("implementations", {})
                    implementations[language] = {"function": function_name}
                    testcases["implementations"] = implementations

                save_json(self.testcases_file, testcases)
                testcases_updated = True

            except json.JSONDecodeError:
                print(
                    f"Warning: Existing '{self.testcases_file}' is invalid JSON. Overwriting."
                )

        if not testcases_updated:
            # Create new file
            with open(self.testcases_file, "w") as f:
                f.write(TESTCASES_TEMPLATE % (language, function_name))
            print(f"Created new testcases file: {self.testcases_file}")

    def parse_test_cases(self, cases_arg: Optional[str] = None) -> Set[int]:
        """
        Parse test case selection argument.

        Args:
            cases_arg: Test case selection string (e.g., "1,3,5-7")

        Returns:
            Set of test case numbers to run
        """
        testcases = self.load_testcases()
        total_cases = len(testcases["testcases"])
        return parse_cases_arg(cases_arg, total_cases)
