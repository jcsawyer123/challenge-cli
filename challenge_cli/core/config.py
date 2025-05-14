import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# Configuration defaults - all constants at the top
CONFIG_FILENAME = "challenge_cli_config.json"
DEFAULT_PLATFORM = "leetcode"
DEFAULT_LANGUAGE = "python"
DEFAULT_FUNCTION_NAME = "solve"
DEFAULT_PROBLEMS_DIR = Path.cwd()
DEFAULT_PROFILE_ITERATIONS = 100
DOCKER_BUILD_TIMEOUT = 300
DOCKER_RUN_TIMEOUT = 10
DOCKER_CONTAINER_SLEEP = 3600  # Increased for better cache utilization
HISTORY_ENABLED_DEFAULT = True
HISTORY_MAX_SNAPSHOTS = 50
HISTORY_DIR_NAME = ".history"
MAX_ERROR_DISPLAY_LENGTH = 1000

# Global configuration instance
_config: Optional["ChallengeConfig"] = None


@dataclass
class CacheConfig:
    """Cache configuration."""

    enabled: bool = True
    directory: Optional[str] = None  # Default: .cache in problems_dir
    max_size_mb: int = 500
    ttl_days: int = 7
    compile_cache: bool = True
    dependency_cache: bool = True


@dataclass
class HistoryConfig:
    """History tracking configuration."""

    enabled: bool = HISTORY_ENABLED_DEFAULT
    max_snapshots: int = HISTORY_MAX_SNAPSHOTS
    dir_name: str = HISTORY_DIR_NAME


@dataclass
class DockerConfig:
    """Docker-related configuration."""

    build_timeout: int = DOCKER_BUILD_TIMEOUT
    run_timeout: int = DOCKER_RUN_TIMEOUT
    container_sleep: int = DOCKER_CONTAINER_SLEEP
    container_sharing: str = "per-language"  # Options: "per-language", "per-challenge"


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""

    language: Optional[str] = None
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Store any extra kwargs in custom_settings."""
        # This allows the dataclass to accept arbitrary keyword arguments
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformConfig":
        """Create PlatformConfig from dictionary, handling extra fields."""
        config_data = data.copy()
        language = config_data.pop("language", None)
        # All remaining fields go into custom_settings
        return cls(language=language, custom_settings=config_data)


@dataclass
class ChallengeConfig:
    """Main configuration class for Challenge CLI."""

    platform: str = DEFAULT_PLATFORM
    language: Optional[str] = None
    problems_dir: Path = field(default_factory=lambda: DEFAULT_PROBLEMS_DIR)
    debug: bool = False
    history: HistoryConfig = field(default_factory=HistoryConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    platforms: Dict[str, PlatformConfig] = field(default_factory=dict)
    profile_iterations: int = DEFAULT_PROFILE_ITERATIONS
    max_error_display_length: int = MAX_ERROR_DISPLAY_LENGTH

    def __post_init__(self):
        # Ensure problems_dir is a Path object
        if not isinstance(self.problems_dir, Path):
            self.problems_dir = Path(self.problems_dir)

    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> "ChallengeConfig":
        """Load configuration from file."""
        config_data = load_config_file(config_path)
        return cls.from_dict(config_data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChallengeConfig":
        """Create config from dictionary."""
        config_data = data.copy()

        # Map JSON keys to config fields
        field_mapping = {
            "default_platform": "platform",
            "default_language": "language",
            "problems_dir": "problems_dir",
            "history_enabled": "history.enabled",
            "history_max_snapshots": "history.max_snapshots",
            "history_dir_name": "history.dir_name",
            "docker_build_timeout": "docker.build_timeout",
            "docker_run_timeout": "docker.run_timeout",
            "docker_container_sleep": "docker.container_sleep",
            "max_error_display_length": "max_error_display_length",
            "profile_iterations": "profile_iterations",
        }

        # Process mapped fields
        for json_key, config_key in field_mapping.items():
            if json_key in config_data:
                value = config_data.pop(json_key)
                if "." in config_key:  # Nested field
                    parent, child = config_key.split(".", 1)
                    if parent not in config_data:
                        config_data[parent] = {}
                    config_data[parent][child] = value
                else:
                    config_data[config_key] = value

        # Handle nested configurations
        if "history" in config_data:
            if isinstance(config_data["history"], dict):
                config_data["history"] = HistoryConfig(**config_data["history"])
            elif isinstance(config_data["history"], bool):
                config_data["history"] = HistoryConfig(enabled=config_data["history"])

        if "docker" in config_data and isinstance(config_data["docker"], dict):
            config_data["docker"] = DockerConfig(**config_data["docker"])

        if "cache" in config_data and isinstance(config_data["cache"], dict):
            config_data["cache"] = CacheConfig(**config_data["cache"])

        if "platforms" in config_data:
            platforms = {}
            for platform, settings in config_data["platforms"].items():
                if isinstance(settings, dict):
                    platforms[platform] = PlatformConfig.from_dict(settings)
            config_data["platforms"] = platforms

        if "problems_dir" in config_data:
            config_data["problems_dir"] = Path(config_data["problems_dir"]).expanduser()

        return cls(**config_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        data = asdict(self)
        data["problems_dir"] = str(data["problems_dir"])
        return data

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if path is None:
            path = Path.home() / f".{CONFIG_FILENAME}"

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def get_platform_config(self, platform: Optional[str] = None) -> PlatformConfig:
        """Get configuration for a specific platform."""
        platform = platform or self.platform
        return self.platforms.get(platform, PlatformConfig())

    def get_cache_dir(self) -> Path:
        """Get the cache directory path."""
        if self.cache.directory:
            return Path(self.cache.directory).expanduser()
        return self.problems_dir / ".cache"


def load_config_file(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    paths = []

    if config_path:
        paths.append(Path(config_path))

    paths.extend(
        [
            Path.cwd() / CONFIG_FILENAME,
            Path.home() / f".{CONFIG_FILENAME}",
        ]
    )

    for path in paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

    return {}


def get_config() -> ChallengeConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ChallengeConfig.from_file()
    return _config


def set_config(config: ChallengeConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
