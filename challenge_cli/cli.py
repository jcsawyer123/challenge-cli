import argparse
import argcomplete
import os
import json
from challenge_cli.tester import ChallengeTester
from challenge_cli.plugins.docker_utils import shutdown_all_containers

def load_config(config_path=None):
    config_paths = [
        config_path if config_path else None,
        os.path.join(os.getcwd(), "challenge_cli_config.json"),
        os.path.expanduser("~/.challenge_cli_config.json"),
    ]
    for path in config_paths:
        if path and os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    return {}

def resolve_language_shorthand(lang_shorthand):
    if not lang_shorthand:
        return None
        
    language_map = {
        # Full names
        "python": "python",
        "go": "go",
        "javascript": "javascript",
        # Shorthands
        "py": "python",
        "js": "javascript",
        "node": "javascript",
        "golang": "go",
    }
    
    lang_shorthand = lang_shorthand.lower()
    return language_map.get(lang_shorthand, lang_shorthand)

def main():
    parser = argparse.ArgumentParser(description="Challenge Testing CLI")
    
    # Global options
    parser.add_argument(
        "--platform", "-p", type=str,
        help="Challenge platform (leetcode, aoc, etc.)"
    )
    parser.add_argument(
        "--config", type=str,
        help="Path to config file"
    )
    parser.add_argument(
        "--debug", action="store_true", 
        help="Show full tracebacks and extra debug info"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new challenge")
    init_parser.add_argument("challenge_path", help="Path to the challenge (e.g., 'two-sum' or 'day1/part1')")
    init_parser.add_argument(
        "--language", "-l", type=str, default="python",
        help="Programming language to use (default: python, shorthands: py, js, go)"
    )
    init_parser.add_argument(
        "--function", "-f", type=str, default="solve",
        help="Function/method name to use in the template (default: solve)"
    )

    # Clean containers
    subparsers.add_parser("shutdown-containers", help="Shutdown all hot containers immediately (alias: clean)")
    subparsers.add_parser("clean", help="Alias for shutdown-containers")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test a solution")
    test_parser.add_argument("challenge_path", help="Path to the challenge (e.g., 'two-sum' or 'day1/part1')")
    test_parser.add_argument(
        "--language", "-l", type=str,
        help="Programming language to use (default: inferred from testcases.json, shorthands: py, js, go)"
    )
    test_parser.add_argument("--detailed", "-d", action="store_true", 
                             help="Display detailed test information")
    test_parser.add_argument("--cases", "-c", type=str, default=None,
                             help="Specify test cases to run (e.g., '1,2,5-7')")
    
    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Profile a solution")
    profile_parser.add_argument("challenge_path", help="Path to the challenge (e.g., 'two-sum' or 'day1/part1')")
    profile_parser.add_argument(
        "--language", "-l", type=str,
        help="Programming language to use (default: inferred from testcases.json, shorthands: py, js, go)"
    )
    profile_parser.add_argument("--iterations", "-i", type=int, default=100, 
                                help="Number of iterations for profiling")
    profile_parser.add_argument("--detailed", "-d", action="store_true", 
                                help="Display detailed profiling information")
    profile_parser.add_argument("--cases", "-c", type=str, default=None,
                                help="Specify test cases to run (e.g., '1,2,5-7')")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze solution complexity (Python only)")
    analyze_parser.add_argument("challenge_path", help="Path to the challenge (e.g., 'two-sum' or 'day1/part1')")
    analyze_parser.add_argument(
        "--language", "-l", type=str, default="python",
        help="Programming language to use (default: python, shorthands: py, js, go)"
    )
    
    argcomplete.autocomplete(parser)
    args = parser.parse_args()    
    
    if not args.command:
        parser.print_help()
        return
    
    config = load_config(args.config)
    problems_dir = config.get("problems_dir", os.getcwd())
    
    # Determine platform - order of precedence:
    # 1. Command line arg (--platform)
    # 2. Config default_platform
    # 3. Fallback to "leetcode"
    platform = args.platform or config.get("default_platform", "leetcode")
    
    # Get platform-specific settings
    platform_config = config.get("platforms", {}).get(platform, {})
    
    # Determine language - order of precedence:
    # 1. Command line arg (--language)
    # 2. Platform config default language
    # 3. Let the tester infer from testcases.json
    language = resolve_language_shorthand(getattr(args, 'language', None))
    if not language:
        language = platform_config.get("language")

    # Clean containers and exit if requested
    if args.command in ("shutdown-containers", "clean"):
        shutdown_all_containers()
        print(f"Shutdown all {platform} containers.")
        return

    # Create tester with the platform prefix in the problem path
    challenge_path = getattr(args, 'challenge_path', None)
    full_path = os.path.join(problems_dir, platform, challenge_path) if challenge_path else None
    
    tester = ChallengeTester(
        platform=platform,
        challenge_path=challenge_path,
        language=language,
        problems_dir=problems_dir
    )
    
    if args.command == "init":
        tester.init_problem(language=language, function_name=args.function)
    elif args.command == "test":
        tester.run_tests(language=language, detailed=args.detailed, cases_arg=args.cases)
    elif args.command == "profile":
        tester.profile(language=language, iterations=args.iterations, detailed=args.detailed, cases_arg=args.cases)
    elif args.command == "analyze":
        tester.analyze_complexity(language=language)


if __name__ == "__main__":
    main()