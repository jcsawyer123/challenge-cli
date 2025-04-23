# output.py
from colorama import Fore, Style, init

init(autoreset=True)

SUCCESS = Fore.GREEN
FAIL = Fore.RED
INFO = Fore.CYAN
WARNING = Fore.YELLOW
STDOUT = Fore.MAGENTA
RESET = Style.RESET_ALL
BOLD = Style.BRIGHT

def print_banner():
    print(f"{INFO}{'='*60}{RESET}")
    print(f"{BOLD}{WARNING}LeetCode Local Testing CLI{RESET}".center(60))
    print(f"{INFO}{'='*60}{RESET}")

def print_divider():
    print(f"{INFO}{'-'*60}{RESET}")

def print_test_case_result(
    case_num,
    passed,
    exec_time,
    memory,
    result,
    expected,
    stdout,
    input_values=None,
    current_mem=None,
    mem_change=None,
    detailed=False
):
    status = f"{SUCCESS}✅ PASSED{RESET}" if passed else f"{FAIL}❌ FAILED{RESET}"
    print(f"{WARNING}Test Case {case_num}:{RESET} {status} ({exec_time}, {memory})")
    if detailed:
        if input_values is not None:
            print(f"  {INFO}Input:   {RESET}{input_values}")
        print(f"  {INFO}Expected:{RESET} {expected}")
        print(f"  {INFO}Output  :{RESET} {result}")
        if current_mem is not None:
            print(f"  {INFO}Current Memory:      {RESET}{current_mem}")
        if mem_change is not None:
            print(f"  {INFO}Process Memory Change:{RESET} {mem_change}")
    elif not passed:
        print(f"  {INFO}Expected:{RESET} {expected}")
        print(f"  {INFO}Output  :{RESET} {result}")
    if stdout:
        print(f"  {STDOUT}Stdout:{RESET}")
        for line in stdout.splitlines():
            print(f"    {line}")
    # if detailed:
    #     print_divider()

def print_error(
    case_num,
    error_msg,
    lineno=None,
    line_content=None,
    stdout=None,
    detailed=False,
    traceback_str=None
):
    print(f"{FAIL}Test Case {case_num}: ❌ ERROR: {error_msg}{RESET}")
    if lineno and line_content:
        print(f"  {WARNING}at line {lineno}:{RESET} {line_content}")
    if detailed and traceback_str:
        print(f"  {INFO}Traceback:{RESET}\n{traceback_str}")
    if stdout:
        print(f"  {STDOUT}Stdout before error:{RESET}")
        for line in stdout.splitlines():
            print(f"    {line}")
    # if detailed:
    #     print_divider()

def print_profile_result(
    case_num,
    iterations,
    avg_time,
    min_time,
    max_time,
    avg_current_mem,
    avg_peak_mem,
    max_peak_mem,
    memory_change,
    warmup_stdout,
    profile_stdout
):
    print(f"{WARNING}Test Case {case_num}:{RESET} {BOLD}{INFO}{iterations} iterations{RESET}")
    print(f"  Time: avg={avg_time}, min={min_time}, max={max_time}")
    print(f"  Memory: avg current={avg_current_mem}, avg peak={avg_peak_mem}, max peak={max_peak_mem}")
    print(f"  Process memory change: {memory_change}")
    if warmup_stdout or profile_stdout:
        print(f"  {STDOUT}Stdout sample:{RESET}")
        lines = (warmup_stdout + profile_stdout).splitlines()
        for line in lines[:5]:
            print(f"    {line}")
        if len(lines) > 5:
            print(f"    ... ({len(lines) - 5} more lines)")

def print_summary(total_passed, total_run, selected, total):
    print(f"\n{INFO}{'='*60}{RESET}")
    print(
        f"{BOLD}{WARNING}Summary:{RESET} "
        f"Passed {SUCCESS}{total_passed}{RESET}/"
        f"{INFO}{total_run}{RESET} test cases "
        f"(out of {INFO}{selected}{RESET} selected, {INFO}{total}{RESET} total)"
    )
    print(f"{INFO}{'='*60}{RESET}")

def print_profile_summary(total_profiled, selected, total):
    print(f"\n{INFO}{'='*60}{RESET}")
    print(
        f"{BOLD}{WARNING}Profiled:{RESET} "
        f"{INFO}{total_profiled}{RESET} of {INFO}{selected}{RESET} selected test cases "
        f"({INFO}{total}{RESET} total)"
    )
    print(f"{INFO}{'='*60}{RESET}")

def print_info(msg):
    print(f"{INFO}{msg}{RESET}")

def print_warning(msg):
    print(f"{WARNING}⚠️  {msg}{RESET}")

def print_success(msg):
    print(f"{SUCCESS}{msg}{RESET}")

def print_fail(msg):
    print(f"{FAIL}{msg}{RESET}")

def print_complexity_header():
    print(f"\n{INFO}{'='*60}{RESET}")
    print(f"{BOLD}{WARNING}COMPLEXITY ANALYSIS RESULTS{RESET}".center(60))
    print(f"{INFO}{'='*60}{RESET}")

def print_complexity_method(method_name, analysis):
    print(f"\n{BOLD}{INFO}Method: {method_name}{RESET}")
    print_divider()
    print(f"{INFO}Time Complexity:{RESET} {analysis['time_complexity']}")
    print(f"{INFO}Space Complexity:{RESET} {analysis['space_complexity']}")
    print(f"\n{INFO}Explanation:{RESET}")
    print(analysis['explanation'])

def print_complexity_footer(complexity_file):
    print(f"\n{INFO}{'='*60}{RESET}")
