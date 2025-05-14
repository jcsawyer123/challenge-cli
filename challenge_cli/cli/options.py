"""
Resolved options and configuration handling for Challenge CLI.
"""

from dataclasses import dataclass
from typing import Optional

from challenge_cli.core.config import ChallengeConfig, load_config_file
from challenge_cli.core.logging import configure_logging, log_debug, log_info
from challenge_cli.plugins.registry import resolve_language


@dataclass
class ResolvedOptions:
    """Container for resolved CLI options."""

    platform: str
    problems_dir: str
    use_history: bool
    max_snapshots: int
    language: Optional[str]
    debug: bool
    config: ChallengeConfig  # Include the full config object


def resolve_options(
    language_override: Optional[str] = None,
    platform_override: Optional[str] = None,
    config_override: Optional[str] = None,
    debug_override: bool = False,
    history_override: Optional[bool] = None,
    no_history_override: bool = False,
) -> ResolvedOptions:
    """Resolves options based on command args, config files, and defaults."""
    # Configure logging first
    configure_logging(debug=debug_override)

    log_debug("Starting option resolution")

    # Load configuration
    log_debug(f"Loading config file: {config_override or 'default locations'}")
    config_data = load_config_file(config_override)
    config = ChallengeConfig.from_dict(config_data)

    # Apply overrides
    if platform_override:
        log_debug(f"Platform override: {platform_override}")
        config.platform = platform_override

    if debug_override:
        config.debug = True

    # Resolve language
    language = None
    if language_override:
        log_debug(f"Resolving language from override: {language_override}")
        language = resolve_language(language_override)
    elif config.language:
        log_debug(f"Using language from config: {config.language}")
        language = config.language
    else:
        # Try platform-specific config
        platform_config = config.get_platform_config()
        if platform_config.language:
            log_debug(
                f"Using language from platform config: {platform_config.language}"
            )
            language = platform_config.language

    # Resolve history settings
    use_history = config.history.enabled

    # Command-line flags override config
    if history_override is not None:
        log_debug(f"History override: {history_override}")
        use_history = history_override
    if no_history_override:
        log_debug("History disabled via --no-history flag")
        use_history = False  # --no-history takes precedence

    resolved = ResolvedOptions(
        platform=config.platform,
        problems_dir=str(config.problems_dir),
        use_history=use_history,
        max_snapshots=config.history.max_snapshots,
        language=language,
        debug=config.debug,
        config=config,  # Pass the full config for future use
    )

    log_info(
        "Options resolved",
        platform=resolved.platform,
        language=resolved.language,
        use_history=resolved.use_history,
    )

    return resolved
