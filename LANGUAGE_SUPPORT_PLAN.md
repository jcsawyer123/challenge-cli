# Language Support Plan for LeetCode CLI

## Overview

To support multiple languages (Python, Go, Java, etc.) in a safe, extensible, and maintainable way, we will implement a **plugin system**. Each language will have its own plugin module, and all code execution will happen inside Docker containers for isolation and reproducibility.

---

## Goals

- **Easy to add new languages** (just drop in a plugin)
- **Safe execution** (all code runs in Docker)
- **Consistent interface** for running, testing, and profiling solutions
- **Per-problem language selection** (via config or CLI flag)
- **Move Python support into a plugin for consistency**

---

## Architecture

### 1. **Plugin Interface**

Each language plugin will implement a standard interface, e.g.:

```python
class LanguagePlugin:
    name = "python"
    docker_image = "python:3.12"

    def build(self, workdir):
        # Optional: build/compile the solution
        pass

    def run(self, workdir, function_name, input_args):
        # Run the solution with the given input
        # Return: output, error, exit_code
        pass
```

### 2. **Plugin Discovery**

- Plugins live in `leetcode_cli/plugins/` (e.g., `python_plugin.py`, `go_plugin.py`)
- The CLI loads plugins dynamically and registers them by name.

### 3. **Docker Runner**

- The CLI uses Docker to run all build and execution commands.
- The problem directory is mounted into the container.
- Input is passed via stdin or command-line args.
- Output is captured and returned to the CLI.

### 4. **Per-Problem Language Selection**

- Each problem can specify its language in `config.json` or `testcases.json`:
  ```json
  {
    "language": "go"
  }
  ```
- Or via a CLI flag: `leetcode-cli test two-sum --lang go`

### 5. **Example Directory Structure**

```
leetcode_cli/
  plugins/
    __init__.py
    python_plugin.py
    go_plugin.py
    # ...
  ...
problems/
  two-sum/
    solution.py
    solution.go
    testcases.json
    config.json
```

---

## Implementation Steps

### 1. **Define the Plugin Interface**

- Create `leetcode_cli/plugins/language_plugin.py` with the base class.

### 2. **Implement the Python Plugin**

- Move all Python-specific logic from the main CLI into `python_plugin.py`.

### 3. **Implement the Go Plugin (as a template for others)**

- Add build (`go build`) and run logic.

### 4. **Implement the Docker Runner**

- Utility to run commands in a specified Docker image, mounting the problem directory.

### 5. **Plugin Registry**

- On CLI startup, discover and register all plugins.

### 6. **Update CLI to Use Plugins**

- When running a problem, determine the language (from config or CLI).
- Use the appropriate plugin to build/run the solution.

---

## Example: Plugin Interface

```python
# language_plugin.py

class LanguagePlugin:
    name = "base"
    docker_image = None

    def build(self, workdir):
        raise NotImplementedError

    def run(self, workdir, function_name, input_args):
        raise NotImplementedError
```

---

## Example: Python Plugin

```python
# python_plugin.py

from .language_plugin import LanguagePlugin

class PythonPlugin(LanguagePlugin):
    name = "python"
    docker_image = "python:3.12"

    def build(self, workdir):
        # No build needed for Python
        return True

    def run(self, workdir, function_name, input_args):
        # Use Docker to run: python solution.py <args>
        # Return output, error, exit_code
        pass
```

---

## Example: Go Plugin

```python
# go_plugin.py

from .language_plugin import LanguagePlugin

class GoPlugin(LanguagePlugin):
    name = "go"
    docker_image = "golang:1.22"

    def build(self, workdir):
        # Run: go build -o solution solution.go
        pass

    def run(self, workdir, function_name, input_args):
        # Run: ./solution <args>
        pass
```

---

## Example: Docker Runner Utility

```python
def run_in_docker(image, workdir, command):
    # Use subprocess to run Docker with the given image, mounting workdir
    # Return stdout, stderr, exit_code
    pass
```

---

## Open Questions

- How to handle input/output for each language (stdin, args, files)?
- How to handle function selection (for languages like Python with multiple functions)?
- How to handle test case comparison for non-Python outputs?
- How to cache Docker images/builds for speed?

---

## Next Steps

1. Implement the base plugin interface.
2. Move Python support into a plugin.
3. Add a Go plugin as a template for others.
4. Refactor CLI to use plugins and Docker runner.
5. Document how to add new languages.

---

## References

- [Judge0 open-source code runner](https://github.com/judge0/judge0)
- [Docker Python SDK](https://docker-py.readthedocs.io/en/stable/)
- [Python subprocess docs](https://docs.python.org/3/library/subprocess.html)


