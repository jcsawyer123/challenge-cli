from leetcode_cli.plugins.go_plugin import GoPlugin
from .language_plugin import LanguagePlugin
from .python_plugin import PythonPlugin

PLUGINS = {}

def register_plugin(plugin_cls):
    PLUGINS[plugin_cls.name] = plugin_cls()

def get_plugin(name):
    return PLUGINS.get(name)

def all_plugins():
    return list(PLUGINS.values())

register_plugin(PythonPlugin)
register_plugin(GoPlugin)
