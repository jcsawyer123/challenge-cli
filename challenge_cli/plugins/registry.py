from challenge_cli.core import constants
from challenge_cli.core.config import DEFAULT_FUNCTION_NAME
from challenge_cli.core.exceptions import ConfigurationError


def resolve_language(lang: str) -> str:
    """Resolve language alias to standard name."""
    lowered = lang.lower()

    # Check if it's already a supported language
    if lowered in constants.SUPPORTED_LANGUAGES:
        return lowered

    # Check aliases
    resolved = constants.LANGUAGE_ALIASES.get(lowered)
    if resolved:
        return resolved

    # Language not found
    supported = ", ".join(sorted(constants.SUPPORTED_LANGUAGES))
    aliases = ", ".join(sorted(constants.LANGUAGE_ALIASES.keys()))
    raise ConfigurationError(
        f"Unsupported language: '{lang}'. "
        f"Supported languages: {supported}. "
        f"Aliases: {aliases}"
    )


def get_solution_template(
    language: str, function_name: str = DEFAULT_FUNCTION_NAME
) -> str:
    """Get the solution template for a language."""
    # Import here to avoid circular dependency
    from . import get_plugin

    language = resolve_language(language)
    plugin = get_plugin(language)

    if not plugin:
        raise ConfigurationError(f"No plugin found for language: {language}")

    return plugin.solution_template(function_name)
