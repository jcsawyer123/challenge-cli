"""
Constants used throughout the application.
"""

# File names
TESTCASES_FILENAME = "testcases.json"
COMPLEXITY_FILENAME = "complexity.json"

# Language configuration
# NOTE: These are now dynamically loaded from language plugins
SUPPORTED_LANGUAGES = set()  # Will be populated by plugins
LANGUAGE_ALIASES = {}  # Will be populated by plugins
DOCKER_IMAGES = {}  # Will be populated by plugins
SOLUTION_TEMPLATES = {}  # Will be populated by plugins
