import subprocess
import os
import time
from typing import Tuple, Optional


def image_exists(image_tag: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "images", "-q", image_tag],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())


def build_image(dockerfile_path: str, image_tag: str, context_dir: str = ".") -> None:
    """Build a Docker image from a Dockerfile."""
    print(f"Building Docker image '{image_tag}' from {dockerfile_path} ...")
    build_cmd = [
        "docker", "build",
        "-f", dockerfile_path,
        "-t", image_tag,
        context_dir
    ]
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    subprocess.run(build_cmd, check=True, env=env)


def ensure_docker_image(image_tag: str, dockerfile_path: str, context_dir: str = ".") -> None:
    """Ensure a Docker image exists, building it if necessary."""
    if not image_exists(image_tag):
        build_image(dockerfile_path, image_tag, context_dir)


def container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def start_hot_container(image: str, workdir: str, container_name: str, sleep_seconds: int = 600) -> None:
    """Start a 'hot' container that stays alive for reuse."""
    if not container_running(container_name):
        subprocess.run([
            "docker", "run", "-d", "--rm",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{os.path.abspath(workdir)}:/workspace",
            "-w", "/workspace",
            "--name", container_name,
            image, "sleep", str(sleep_seconds)
        ], check=True)
    # Update timestamp file
    _update_container_timestamp(container_name)


def execute_in_container(
    container_name: str, 
    command: list, 
    input_data: Optional[str] = None, 
    timeout: int = 10
) -> Tuple[str, str, int]:
    """
    Execute a command in a running container.
    
    Returns:
        Tuple of (stdout, stderr, exit_code)
    """
    _update_container_timestamp(container_name)
    docker_cmd = ["docker", "exec", container_name] + command
    
    try:
        result = subprocess.run(
            docker_cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout} seconds", -1
    except Exception as e:
        return "", str(e), -1


def shutdown_container(container_name: str) -> None:
    """Stop and remove a container, cleaning up timestamp file."""
    subprocess.run(["docker", "stop", container_name], check=False)
    _remove_container_timestamp(container_name)


def shutdown_all_containers() -> None:
    """Shutdown all challenge containers and clean up timestamp files."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    
    for name in result.stdout.splitlines():
        if name.startswith("challenge-"):
            print(f"Stopping container: {name}")
            shutdown_container(name)
    
    # Clean up any orphaned timestamp files
    _cleanup_orphaned_timestamps()


# Private helper functions
def _get_timestamp_path(container_name: str) -> str:
    """Get the path to the timestamp file for a container."""
    return f"/tmp/{container_name}.lastused"


def _update_container_timestamp(container_name: str) -> None:
    """Update the last-used timestamp for a container."""
    timestamp_path = _get_timestamp_path(container_name)
    with open(timestamp_path, "w") as f:
        f.write(str(time.time()))


def _remove_container_timestamp(container_name: str) -> None:
    """Remove the timestamp file for a container."""
    timestamp_path = _get_timestamp_path(container_name)
    try:
        os.remove(timestamp_path)
    except FileNotFoundError:
        pass


def _cleanup_orphaned_timestamps() -> None:
    """Remove timestamp files for containers that no longer exist."""
    for filename in os.listdir("/tmp"):
        if filename.startswith("challenge-") and filename.endswith(".lastused"):
            timestamp_path = os.path.join("/tmp", filename)
            try:
                os.remove(timestamp_path)
            except Exception:
                pass


# Backwards compatibility aliases (deprecated)
exec_in_hot_container = execute_in_container
shutdown_hot_container = shutdown_container