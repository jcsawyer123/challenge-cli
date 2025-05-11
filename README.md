# Challenge CLI

A modern, cross-platform coding challenge testing tool that supports multiple languages and challenge sources.

## Features

- **Multi-platform**: Support for LeetCode, Advent of Code, and custom challenges
- **Multiple languages**: Python, JavaScript, Go (and easily extensible)
- **Path-based**: Flexible directory structure for different challenge types
- **Test, profile, analyze**: Comprehensive performance testing
- **Containerized**: Secure execution in Docker containers
- **Pretty output**: Clear, colorful test results

## Installation

```sh
# Clone and install
git clone https://github.com/jcsawyer123/challenge-cli.git
cd challenge-cli
pip install -e .

# (Optional) Enable tab completion
pip install argcomplete
activate-global-python-argcomplete --user
```

## Quick Start

```sh
# LeetCode challenge
challenge-cli -p leetcode init two-sum -l python
# Edit the solution and test cases
challenge-cli -p leetcode test two-sum -l python

# Advent of Code challenge
challenge-cli -p aoc init 2023/day1/part1 -l python
# Edit the solution and test cases
challenge-cli -p aoc test 2023/day1/part1 -l python
```

## Configuration

Create `~/.challenge_cli_config.json`:

```json
{
  "problems_dir": "/path/to/your/challenges",
  "default_platform": "leetcode",
  "platforms": {
    "leetcode": {
      "language": "python"
    },
    "aoc": {
      "language": "go",
    }
  }
}
```

## Commands

### Initialize a Challenge

```sh
challenge-cli [-p PLATFORM] init CHALLENGE_PATH [-l LANGUAGE] [-f FUNCTION_NAME]
```

### Test a Solution

```sh
challenge-cli [-p PLATFORM] test CHALLENGE_PATH [-l LANGUAGE] [-d] [-c CASES]
```

Options:
- `-d, --detailed`: Show detailed output
- `-c, --cases`: Specify test cases (e.g., `1,3-5`)

### Profile Performance

```sh
challenge-cli [-p PLATFORM] profile CHALLENGE_PATH [-l LANGUAGE] [-i ITERATIONS]
```

Options:
- `-i, --iterations`: Number of iterations (default: 100)
- `-d, --detailed`: Show detailed output

### Analyze Complexity (Python only)

```sh
challenge-cli [-p PLATFORM] analyze CHALLENGE_PATH [-l LANGUAGE]
```

### Clean Up Containers

```sh
challenge-cli shutdown-containers
```

## Language Shorthands

- `py` for Python
- `js` for JavaScript
- `go` for Go

Example: `challenge-cli init two-sum -l py`

## Directory Structure

```
challenges/
  leetcode/
    two-sum/
      python/
        solution.py
      go/
        solution.go
      testcases.json
  aoc/
    2023/
      day1/
        part1/
          python/
            solution.py
          testcases.json
```

## Global Options

- `-p, --platform`: Challenge platform (leetcode, aoc, etc.)
- `--config`: Specify config file path
- `--debug`: Show detailed error information

## Requirements

- Python 3.7+
- Docker
- colorama, psutil, argcomplete

## Examples

### Multiple Languages

```sh
# Initialize in different languages
challenge-cli -p leetcode init two-sum -l python
challenge-cli -p leetcode init two-sum -l go

# Compare performance
challenge-cli -p leetcode profile two-sum -l python
challenge-cli -p leetcode profile two-sum -l go
```

### Testing Specific Cases

```sh
challenge-cli -p leetcode test two-sum -l python -c 1,3,5-7
```

### Detailed Analysis

```sh
challenge-cli -p leetcode analyze two-sum -l python
```