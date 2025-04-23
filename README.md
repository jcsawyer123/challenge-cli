# LeetCode Local Testing CLI

A modern, user-friendly command-line tool for **testing, profiling, and analyzing LeetCode solutions locally**—with pretty output, tab completion, and easy configuration.

---

## Features

- **Initialize** new LeetCode problem folders with solution and test templates
- **Run tests** with detailed or summary output, including memory and timing stats
- **Profile** your solution’s performance over many iterations
- **Analyze** time and space complexity heuristically
- **Pretty, colorized output** for easy reading
- **Tab completion** for all commands and options (via [argcomplete](https://pypi.org/project/argcomplete/))
- **Configurable**: set your problems directory via config file or CLI flag

---

## Installation

### 1. **Clone and Install**

```sh
git clone https://github.com/jcsawyer123/leetcode-cli.git
cd leetcode-cli
pip install -e .
```

### 2. **(Optional) Enable Tab Completion**

#### Bash

```sh
activate-global-python-argcomplete --user
```
Restart your shell.

#### Zsh

Add to your `.zshrc`:
```sh
eval "$(register-python-argcomplete leetcode-cli)"
```

#### Fish

```sh
register-python-argcomplete leetcode-cli | source
```

---

## Usage

### **Initialize a New Problem**

```sh
leetcode-cli init two-sum
```
Creates a folder `two-sum/` with `solution.py` and `testcases.json` templates.

### **Edit Your Solution and Test Cases**

- Edit `two-sum/solution.py` with your code.
- Edit `two-sum/testcases.json` with your test cases.

### **Run Tests**

```sh
leetcode-cli test two-sum
```

- Add `-d` or `--detailed` for detailed output.
- Use `-c` or `--cases` to run specific cases (e.g., `-c 1,3-5`).

### **Profile Performance**

```sh
leetcode-cli profile two-sum
```

- Use `-i` or `--iterations` to set the number of runs.

### **Analyze Complexity**

```sh
leetcode-cli analyze two-sum
```

---

## Configuration

By default, the CLI looks for problems in the current directory.  
To set a custom problems directory, create a config file:

**`~/.leetcode_cli_config.json`**
```json
{
  "problems_dir": "/absolute/path/to/your/leetcode/problems"
}
```


---

## Example Workflow

```sh
leetcode-cli init two-sum
# Edit two-sum/solution.py and two-sum/testcases.json
leetcode-cli test two-sum -d
leetcode-cli profile two-sum -i 1000
leetcode-cli analyze two-sum
```

---

## Advanced

- **Tab completion**: See [Installation](#installation) for enabling shell completion.
- **Custom config**: Use `--config /path/to/config.json` to specify a config file.

---

## Requirements

- Python 3.7+
- [colorama](https://pypi.org/project/colorama/)
- [psutil](https://pypi.org/project/psutil/)
- [argcomplete](https://pypi.org/project/argcomplete/)

All dependencies are installed automatically.

