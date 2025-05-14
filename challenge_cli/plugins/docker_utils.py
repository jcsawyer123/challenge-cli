import os
import subprocess
import time
from typing import Optional, Tuple

from challenge_cli.core.config import get_config
from challenge_cli.core.logging import (
    log_context,
    log_debug,
    log_error,
    log_info,
    log_warning,
    logged_operation,
)


@logged_operation("docker_image_exists")
def image_exists(image_tag: str) -> bool:
    """Check if a Docker image exists locally."""
    log_debug(f"Checking if Docker image '{image_tag}' exists")
    result = subprocess.run(
        ["docker", "images", "-q", image_tag], capture_output=True, text=True
    )
    exists = bool(result.stdout.strip())
    log_debug(f"Image '{image_tag}' exists: {exists}")
    return exists


@logged_operation("docker_build_image")
def build_image(dockerfile_path: str, image_tag: str, context_dir: str = ".") -> None:
    """Build a Docker image from a Dockerfile."""
    log_info(f"Building Docker image '{image_tag}' from {dockerfile_path} ...")
    build_cmd = ["docker", "build", "-f", dockerfile_path, "-t", image_tag, context_dir]
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    try:
        subprocess.run(build_cmd, check=True, env=env)
        log_info(f"Successfully built image '{image_tag}'")
    except subprocess.CalledProcessError as e:
        log_error(f"Failed to build image '{image_tag}': {e}", exc_info=True)
        raise


@logged_operation("docker_ensure_image")
def ensure_docker_image(
    image_tag: str, dockerfile_path: str, context_dir: str = "."
) -> None:
    """Ensure a Docker image exists, building it if necessary."""
    if not image_exists(image_tag):
        log_info(f"Image '{image_tag}' not found, building...")
        build_image(dockerfile_path, image_tag, context_dir)
    else:
        log_debug(f"Image '{image_tag}' already exists, skipping build.")


@logged_operation("docker_container_running")
def container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    log_debug(f"Checking if container '{container_name}' is running")
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
        capture_output=True,
        text=True,
    )
    running = bool(result.stdout.strip())
    log_debug(f"Container '{container_name}' running: {running}")
    return running


@logged_operation("docker_container_healthy")
def container_healthy(container_name: str) -> bool:
    """Quick health check for container."""
    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "echo", "ok"],
            capture_output=True,
            timeout=1,
        )
        return result.returncode == 0 and result.stdout.strip() == b"ok"
    except subprocess.TimeoutExpired:
        return False


@logged_operation("docker_start_hot_container")
def start_hot_container(
    image: str,
    workdir: str,
    container_name: str,
    problems_dir: str = None,
    cache_dir: str = None,
) -> None:
    """Start a 'hot' container that stays alive for reuse."""
    config = get_config()
    sleep_seconds = config.docker.container_sleep

    with log_context(container=container_name, image=image):
        if container_running(container_name):
            if container_healthy(container_name):
                log_debug(f"Container '{container_name}' already running and healthy")
                _update_container_timestamp(container_name)
                return
            else:
                log_warning(f"Container '{container_name}' unhealthy, restarting")
                shutdown_container(container_name)

        log_info(f"Starting hot container '{container_name}' from image '{image}'")

        # Set up volume mounts
        docker_cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
        ]

        # Mount problems directory at root
        if problems_dir:
            mount_path = os.path.abspath(problems_dir)
            docker_cmd.extend(["-v", f"{mount_path}:/workspace"])
            log_debug(f"Mounting problems directory: {mount_path}")
        else:
            # Fallback to specific workdir mount
            mount_path = os.path.abspath(workdir)
            docker_cmd.extend(["-v", f"{mount_path}:/workspace"])
            log_debug(f"Mounting workdir: {mount_path}")

        # Mount cache directory if provided
        if cache_dir:
            cache_path = os.path.abspath(cache_dir)
            os.makedirs(cache_path, exist_ok=True)
            docker_cmd.extend(["-v", f"{cache_path}:/cache"])
            log_debug(f"Mounting cache directory: {cache_path}")

            # Set environment variables for language-specific caching
            docker_cmd.extend(
                [
                    "-e",
                    "GOCACHE=/cache/go/build",
                    "-e",
                    "GOMODCACHE=/cache/go/modules",
                    "-e",
                    "NODE_PATH=/cache/javascript/node_modules",
                    "-e",
                    "PYTHONPYCACHEPREFIX=/cache/python",
                    "-e",
                    "npm_config_cache=/cache/javascript/npm",
                ]
            )

        # Complete the command
        docker_cmd.extend(
            [
                "-w",
                "/workspace",
                "--name",
                container_name,
                image,
                "sleep",
                str(sleep_seconds),
            ]
        )

        try:
            subprocess.run(docker_cmd, check=True)
            log_info(f"Started container '{container_name}'")
        except subprocess.CalledProcessError as e:
            log_error(
                f"Failed to start container '{container_name}': {e}", exc_info=True
            )
            raise


@logged_operation("docker_exec_in_container")
def execute_in_container(
    container_name: str,
    command: list,
    working_dir: Optional[str] = None,
    input_data: Optional[str] = None,
    timeout: int = 10,
) -> Tuple[str, str, int]:
    """
    Execute a command in a running container.

    Args:
        container_name: Name of the container
        command: Command to execute
        working_dir: Working directory inside the container
        input_data: Optional stdin data
        timeout: Command timeout in seconds

    Returns:
        Tuple of (stdout, stderr, exit_code)
    """
    with log_context(container=container_name):
        _update_container_timestamp(container_name)

        docker_cmd = ["docker", "exec"]

        if working_dir:
            docker_cmd.extend(["-w", working_dir])
            log_debug(f"Using working directory: {working_dir}")

        docker_cmd.extend([container_name] + command)
        log_debug(f"Executing in container '{container_name}': {' '.join(command)}")

        try:
            result = subprocess.run(
                docker_cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            log_debug(f"Command result: exit_code={result.returncode}")
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            log_warning(
                f"Command in container '{container_name}' timed out after {timeout} seconds"
            )
            return "", f"Command timed out after {timeout} seconds", -1
        except Exception as e:
            log_error(
                f"Error executing in container '{container_name}': {e}", exc_info=True
            )
            return "", str(e), -1


@logged_operation("docker_shutdown_container")
def shutdown_container(container_name: str) -> None:
    """Stop and remove a container, cleaning up timestamp file."""
    with log_context(container=container_name):
        log_info(f"Stopping container '{container_name}'")
        subprocess.run(["docker", "stop", container_name], check=False)
        _remove_container_timestamp(container_name)
        log_debug(f"Container '{container_name}' stopped and timestamp cleaned up")


@logged_operation("docker_shutdown_all_containers")
def shutdown_all_containers() -> None:
    """Shutdown all challenge containers and clean up timestamp files."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    )
    for name in result.stdout.splitlines():
        if name.startswith("challenge-cli-"):  # Updated prefix
            log_info(f"Stopping container: {name}")
            shutdown_container(name)
    _cleanup_orphaned_timestamps()
    log_info("All challenge containers stopped and orphaned timestamps cleaned up")


# Private helper functions
def _get_timestamp_path(container_name: str) -> str:
    """Get the path to the timestamp file for a container."""
    return f"/tmp/{container_name}.lastused"


def _update_container_timestamp(container_name: str) -> None:
    """Update the last-used timestamp for a container."""
    timestamp_path = _get_timestamp_path(container_name)
    try:
        with open(timestamp_path, "w") as f:
            f.write(str(time.time()))
        log_debug(f"Updated timestamp for container '{container_name}'")
    except Exception as e:
        log_warning(f"Failed to update timestamp for '{container_name}': {e}")


def _remove_container_timestamp(container_name: str) -> None:
    """Remove the timestamp file for a container."""
    timestamp_path = _get_timestamp_path(container_name)
    try:
        os.remove(timestamp_path)
        log_debug(f"Removed timestamp for container '{container_name}'")
    except FileNotFoundError:
        log_debug(f"No timestamp file to remove for '{container_name}'")
    except Exception as e:
        log_warning(f"Failed to remove timestamp for '{container_name}': {e}")


def _cleanup_orphaned_timestamps() -> None:
    """Remove timestamp files for containers that no longer exist."""
    for filename in os.listdir("/tmp"):
        if filename.startswith("challenge-cli-") and filename.endswith(".lastused"):
            timestamp_path = os.path.join("/tmp", filename)
            try:
                os.remove(timestamp_path)
                log_debug(f"Removed orphaned timestamp: {timestamp_path}")
            except Exception as e:
                log_warning(
                    f"Failed to remove orphaned timestamp '{timestamp_path}': {e}"
                )
