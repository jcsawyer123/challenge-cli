import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Union
from functools import cached_property

# Configuration defaults
DEFAULT_PLATFORM = 'leetcode'
DEFAULT_LANGUAGE = 'python'
DEFAULT_FUNCTION_NAME = 'solve'
DEFAULT_PROBLEMS_DIR = Path.cwd()
HISTORY_ENABLED_DEFAULT = True
HISTORY_MAX_SNAPSHOTS = 50
HISTORY_DIR_NAME = '.history'
DOCKER_BUILD_TIMEOUT = 300
DOCKER_RUN_TIMEOUT = 10
DOCKER_CONTAINER_SLEEP = 600
MAX_ERROR_DISPLAY_LENGTH = 1000
DEFAULT_PROFILE_ITERATIONS = 100
CONFIG_FILENAME = 'challenge_cli_config.json'


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


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""
    language: Optional[str] = None
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChallengeConfig:
    """Main configuration class for Challenge CLI."""
    platform: str = DEFAULT_PLATFORM
    language: Optional[str] = None
    problems_dir: Path = field(default_factory=lambda: DEFAULT_PROBLEMS_DIR)
    debug: bool = False
    history: HistoryConfig = field(default_factory=HistoryConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    platforms: Dict[str, PlatformConfig] = field(default_factory=dict)
    profile_iterations: int = DEFAULT_PROFILE_ITERATIONS
    max_error_display_length: int = MAX_ERROR_DISPLAY_LENGTH
    
    def __post_init__(self):
        # Ensure problems_dir is a Path object
        if not isinstance(self.problems_dir, Path):
            self.problems_dir = Path(self.problems_dir)
    
    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> 'ChallengeConfig':
        """Load configuration from file."""
        config_data = load_config_file(config_path)
        return cls.from_dict(config_data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChallengeConfig':
        """Create config from dictionary."""
        config_data = data.copy()
        
        # Handle nested configurations
        if 'history' in config_data:
            if isinstance(config_data['history'], dict):
                config_data['history'] = HistoryConfig(**config_data['history'])
            elif isinstance(config_data['history'], bool):
                config_data['history'] = HistoryConfig(enabled=config_data['history'])
        
        if 'docker' in config_data and isinstance(config_data['docker'], dict):
            config_data['docker'] = DockerConfig(**config_data['docker'])
        
        if 'platforms' in config_data:
            platforms = {}
            for platform, settings in config_data['platforms'].items():
                if isinstance(settings, dict):
                    platforms[platform] = PlatformConfig(**settings)
            config_data['platforms'] = platforms
        
        if 'problems_dir' in config_data:
            config_data['problems_dir'] = Path(config_data['problems_dir']).expanduser()
        
        return cls(**config_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        data = asdict(self)
        data['problems_dir'] = str(data['problems_dir'])
        return data
    
    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if path is None:
            path = Path.home() / f'.{CONFIG_FILENAME}'
        
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def get_platform_config(self, platform: Optional[str] = None) -> PlatformConfig:
        """Get configuration for a specific platform."""
        platform = platform or self.platform
        return self.platforms.get(platform, PlatformConfig())


def load_config_file(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file."""
    paths = []
    
    if config_path:
        paths.append(Path(config_path))
    
    paths.extend([
        Path.cwd() / CONFIG_FILENAME,
        Path.home() / f'.{CONFIG_FILENAME}',
    ])
    
    for path in paths:
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
    
    return {}


# Global configuration instance
_config: Optional[ChallengeConfig] = None


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