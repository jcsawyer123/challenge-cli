import subprocess
import os
import time

def image_exists(image_tag):
    result = subprocess.run(
        ["docker", "images", "-q", image_tag],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())

def build_image(dockerfile_path, image_tag, context_dir="."):
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

def ensure_docker_image(image_tag, dockerfile_path, context_dir="."):
    if not image_exists(image_tag):
        build_image(dockerfile_path, image_tag, context_dir)

def container_running(container_name):
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())

def start_hot_container(image, workdir, container_name, sleep_seconds=600):
    if not container_running(container_name):
        subprocess.run([
            "docker", "run", "-d", "--rm",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{os.path.abspath(workdir)}:/workspace",
            "-w", "/workspace",
            "--name", container_name,
            image, "sleep", str(sleep_seconds)
        ], check=True)
    # Touch a timestamp file
    with open(f"/tmp/{container_name}.lastused", "w") as f:
        f.write(str(time.time()))

def exec_in_hot_container(container_name, command, input_data=None, timeout=10):
    with open(f"/tmp/{container_name}.lastused", "w") as f:
        f.write(str(time.time()))
    docker_cmd = ["docker", "exec", container_name] + command
    result = subprocess.run(
        docker_cmd,
        input=input_data,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    return result.stdout, result.stderr, result.returncode

def shutdown_hot_container(container_name):
    subprocess.run(["docker", "stop", container_name], check=False)
    try:
        os.remove(f"/tmp/{container_name}.lastused")
    except FileNotFoundError:
        pass

def shutdown_all_containers():
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    for name in result.stdout.splitlines():
        if name.startswith("challenge-"):
            print(f"Stopping container: {name}")
            shutdown_hot_container(name)
    for fname in os.listdir("/tmp"):
        if fname.startswith("challenge-") and fname.endswith(".lastused"):
            try:
                os.remove(os.path.join("/tmp", fname))
            except Exception:
                pass