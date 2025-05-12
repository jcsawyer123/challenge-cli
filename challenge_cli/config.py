"""
Central configuration module for Challenge CLI.
"""

from typing import Dict, Optional
import os
from pathlib import Path


# Docker Configuration
DOCKER_IMAGES = {
    'python': 'leetcode-python-runner:3.12',
    'javascript': 'leetcode-javascript-runner:18',
    'go': 'leetcode-go-runner:1.22',
}

DOCKER_BUILD_TIMEOUT = 300  # seconds
DOCKER_RUN_TIMEOUT = 10    # seconds
DOCKER_CONTAINER_SLEEP = 600  # seconds

# Default Configuration  
DEFAULT_PLATFORM = 'leetcode'
DEFAULT_LANGUAGE = 'python'
DEFAULT_FUNCTION_NAME = 'solve'
DEFAULT_PROBLEMS_DIR = os.getcwd()

# History Configuration
HISTORY_ENABLED_DEFAULT = True
HISTORY_MAX_SNAPSHOTS = 50
HISTORY_DIR_NAME = '.history'

# Output Configuration
MAX_ERROR_DISPLAY_LENGTH = 1000
DEFAULT_PROFILE_ITERATIONS = 100

# File Names
TESTCASES_FILENAME = 'testcases.json'
COMPLEXITY_FILENAME = 'complexity.json'
CONFIG_FILENAME = 'challenge_cli_config.json'

# Paths
HOME_CONFIG_PATH = Path.home() / f'.{CONFIG_FILENAME}'
LOCAL_CONFIG_PATH = Path.cwd() / CONFIG_FILENAME

# Supported Languages and Platforms
SUPPORTED_LANGUAGES = {'python', 'javascript', 'go'}
SUPPORTED_PLATFORMS = {'leetcode', 'aoc', 'custom'}

# Language Aliases
LANGUAGE_ALIASES = {
    'py': 'python',
    'js': 'javascript',
    'node': 'javascript',
    'golang': 'go',
}

# Solution Templates
SOLUTION_TEMPLATES = {
    'python': '''class Solution:
    def {function_name}(self, param1, param2):
        """
        Replace this with the actual function signature.
        """
        pass
''',
    
    'javascript': '''/**
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
''',
    
    'go': '''package main

func {function_name}(param1 interface{{}}, param2 interface{{}}) interface{{}} {{
    // Your solution here
    return nil
}}
'''
}

# Error Messages
ERROR_MESSAGES = {
    'no_language': 'No language specified and could not infer from context',
    'no_plugin': 'No plugin found for language: {language}',
    'no_testcases': 'Test cases file not found: {path}',
    'invalid_config': 'Invalid configuration file: {path}',
    'build_failed': 'Failed to build solution',
    'timeout': 'Execution timed out after {timeout} seconds',
}


def get_docker_image(language: str) -> Optional[str]:
    """Get Docker image for a language."""
    return DOCKER_IMAGES.get(language)


def resolve_language(alias: str) -> Optional[str]:
    """Resolve language alias to standard name."""
    lowered = alias.lower()
    return LANGUAGE_ALIASES.get(lowered, lowered if lowered in SUPPORTED_LANGUAGES else None)


def get_config_paths() -> list:
    """Get configuration file paths in order of precedence."""
    return [LOCAL_CONFIG_PATH, HOME_CONFIG_PATH]


def format_error(error_key: str, **kwargs) -> str:
    """Format an error message with parameters."""
    template = ERROR_MESSAGES.get(error_key, 'Unknown error: {error_key}')
    return template.format(error_key=error_key, **kwargs)