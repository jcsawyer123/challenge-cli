import argparse
import argcomplete
import os
import json
from leetcode_cli.tester import LeetCodeTester

def load_config():
    # Check current directory first, then home directory
    config_paths = [
        os.path.join(os.getcwd(), "leetcode_cli_config.json"),
        os.path.expanduser("~/.leetcode_cli_config.json"),
    ]
    for path in config_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(description="LeetCode Local Testing CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new problem")
    init_parser.add_argument("problem_id", help="LeetCode problem ID or name")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test a solution")
    test_parser.add_argument("problem_id", help="LeetCode problem ID or name")
    test_parser.add_argument("--detailed", "-d", action="store_true", 
                             help="Display detailed test information")
    test_parser.add_argument("--cases", "-c", type=str, default=None,
                             help="Specify test cases to run (e.g., '1,2,5-7')")
    
    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Profile a solution")
    profile_parser.add_argument("problem_id", help="LeetCode problem ID or name")
    profile_parser.add_argument("--iterations", "-i", type=int, default=100, 
                                help="Number of iterations for profiling")
    profile_parser.add_argument("--detailed", "-d", action="store_true", 
                                help="Display detailed profiling information")
    profile_parser.add_argument("--cases", "-c", type=str, default=None,
                                help="Specify test cases to run (e.g., '1,2,5-7')")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze solution complexity")
    analyze_parser.add_argument("problem_id", help="LeetCode problem ID or name")
    
    parser.add_argument(
        "--debug", action="store_true", help="Show full tracebacks and extra debug info"
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()    
    
    if not args.command:
        parser.print_help()
        return
    
    config = load_config()
    problems_dir = config.get("problems_dir", os.getcwd())  # fallback to cwd

    # Pass to your tester
    tester = LeetCodeTester(args.problem_id, problems_dir=problems_dir)
    
    if args.command == "init":
        tester.init_problem()
    elif args.command == "test":
        tester.run_tests(detailed=args.detailed, cases_arg=args.cases)
    elif args.command == "profile":
        tester.profile(iterations=args.iterations, detailed=args.detailed, cases_arg=args.cases)
    elif args.command == "analyze":
        tester.analyze_complexity()


if __name__ == "__main__":
    main()