from typing import Dict, Type

from .language_plugin import LanguagePlugin
from .registry import resolve_language, get_solution_template

from .languages.javascript_plugin import JavaScriptPlugin
from .languages.python_plugin import PythonPlugin
from .languages.go_plugin import GoPlugin

# Import constants to populate
from challenge_cli.core import constants



PLUGINS: Dict[str, LanguagePlugin] = {}

def register_plugin(plugin_cls: Type[LanguagePlugin]):
    """Register a plugin and update global constants."""
    plugin = plugin_cls()
    PLUGINS[plugin.name] = plugin
    
    # Update global constants
    constants.SUPPORTED_LANGUAGES.add(plugin.name)
    constants.DOCKER_IMAGES[plugin.name] = plugin.docker_image
    
    # Register aliases
    for alias in getattr(plugin, 'aliases', []):
        constants.LANGUAGE_ALIASES[alias] = plugin.name
    
    # Register template
    if hasattr(plugin, 'solution_template'):
        constants.SOLUTION_TEMPLATES[plugin.name] = plugin.solution_template

def get_plugin(name: str) -> LanguagePlugin:
    return PLUGINS.get(name)

# Register all available plugins
register_plugin(PythonPlugin)
register_plugin(GoPlugin)
register_plugin(JavaScriptPlugin)