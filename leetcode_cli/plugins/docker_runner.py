import subprocess
import os
import uuid

def run_in_docker(
    image: str,
    workdir: str,
    command: list,
    input_data: str = None,
    timeout: int = 10
):
    """
    Run a command in a new Docker container.
    Returns: (stdout, stderr, exit_code)
    """
    docker_cmd = [
        "docker", "run", "--rm",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{os.path.abspath(workdir)}:/workspace",
        "-w", "/workspace",
        image
    ] + command

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
        return "", f"Timeout after {timeout} seconds", -1
    except Exception as e:
        return "", str(e), -1

# --- Persistent container utilities ---

def start_persistent_container(image, workdir, container_name):
    """
    Start a persistent Docker container in the background.
    """
    docker_cmd = [
        "docker", "run", "-d", "--rm",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{os.path.abspath(workdir)}:/workspace",
        "-w", "/workspace",
        "--name", container_name,
        image, "sleep", "3600"
    ]
    subprocess.run(docker_cmd, check=True)

def exec_in_container(container_name, command, input_data=None, timeout=10):
    """
    Run a command in an existing container.
    Returns: (stdout, stderr, exit_code)
    """
    docker_cmd = [
        "docker", "exec", container_name
    ] + command
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
        return "", f"Timeout after {timeout} seconds", -1
    except Exception as e:
        return "", str(e), -1

def stop_container(container_name):
    """
    Stop and remove a persistent Docker container.
    """
    subprocess.run(["docker", "stop", container_name], check=False)
