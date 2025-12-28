#!/usr/bin/env python3
"""
Interactive CLI for AI Web Automation Agent

Usage:
    python cli.py                           # Interactive mode
    python cli.py --url URL --task TASK     # Direct mode
    python cli.py --help                    # Show help
"""

import asyncio
import argparse
import sys
import os
from typing import Optional
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from web_agent.core.master_agent import MasterAgent
except ImportError:
    print("❌ Error: web_agent package not installed.")
    print("   Please run: pip install -e .")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_banner():
    """Print CLI banner"""
    banner = f"""
{Colors.OKCYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        🤖 AI Web Automation Agent CLI v0.1.0             ║
║                                                           ║
║        Powered by Gemini 2.5 Pro + OmniParser            ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def get_user_input(prompt: str, default: Optional[str] = None) -> str:
    """Get user input with optional default value"""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(f"{Colors.OKCYAN}{prompt}{Colors.ENDC}").strip()
    return value if value else (default or "")


def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url:
        return False
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    return True


def get_interactive_inputs() -> tuple[str, str, int]:
    """Get inputs interactively from user"""
    print(f"\n{Colors.BOLD}Enter automation details:{Colors.ENDC}\n")

    # Get URL
    while True:
        url = get_user_input("Target URL (e.g., https://www.google.com)")
        if validate_url(url):
            break
        print_error("Invalid URL. Please include http:// or https://")

    # Get task
    while True:
        task = get_user_input("Task description (e.g., Search for 'Python' and click first result)")
        if task:
            break
        print_error("Task cannot be empty")

    # Get worker count
    while True:
        workers_input = get_user_input("Max parallel workers", "2")
        try:
            workers = int(workers_input)
            if 1 <= workers <= 8:
                break
            print_error("Workers must be between 1 and 8")
        except ValueError:
            print_error("Please enter a valid number")

    return url, task, workers


async def run_automation(url: str, task: str, max_workers: int = 2, headless: bool = False):
    """Run the web automation"""

    print(f"\n{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
    print(f"{Colors.BOLD}Starting Automation{Colors.ENDC}")
    print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}\n")

    print_info(f"URL: {url}")
    print_info(f"Task: {task}")
    print_info(f"Workers: {max_workers}")
    print_info(f"Mode: {'Headless' if headless else 'Visible Browser'}")
    print()

    start_time = datetime.now()

    # Initialize master agent
    print_info("Initializing AI agents...")
    master = None

    try:
        master = MasterAgent(max_parallel_workers=max_workers)
        await master.initialize()
        print_success("Agents initialized successfully")

        # Execute the goal
        print(f"\n{Colors.BOLD}Executing automation...{Colors.ENDC}\n")

        result = await master.execute_goal(
            goal=task,
            starting_url=url
        )

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Display results
        print(f"\n{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}")
        print(f"{Colors.BOLD}Automation Results{Colors.ENDC}")
        print(f"{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}\n")

        if result.success:
            print_success(f"Automation completed successfully! ✨")
        else:
            print_warning(f"Automation completed with issues")

        print(f"\n{Colors.BOLD}Statistics:{Colors.ENDC}")
        print(f"  • Duration: {duration:.2f}s")
        print(f"  • Tasks completed: {result.completed_tasks}/{result.total_tasks}")
        print(f"  • Success rate: {(result.completed_tasks/result.total_tasks*100) if result.total_tasks > 0 else 0:.1f}%")

        if hasattr(result, 'extracted_data') and result.extracted_data:
            print(f"\n{Colors.BOLD}Extracted Data:{Colors.ENDC}")
            print(f"  {result.extracted_data}")

        if hasattr(result, 'message') and result.message:
            print(f"\n{Colors.BOLD}Message:{Colors.ENDC}")
            print(f"  {result.message}")

        print()

        return result.success

    except KeyboardInterrupt:
        print_warning("\n\nAutomation interrupted by user")
        return False

    except Exception as e:
        print_error(f"\nAutomation failed: {str(e)}")
        import traceback
        print(f"\n{Colors.WARNING}Error details:{Colors.ENDC}")
        print(traceback.format_exc())
        return False

    finally:
        if master:
            print_info("Cleaning up resources...")
            await master.cleanup()
            print_success("Cleanup complete")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='AI Web Automation Agent - Automate web tasks with AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:
    python cli.py

  Direct mode:
    python cli.py --url "https://google.com" --task "Search for Python"

  With custom settings:
    python cli.py --url "https://example.com" --task "Fill form" --workers 4 --headless
        """
    )

    parser.add_argument('--url', '-u', type=str, help='Target URL to automate')
    parser.add_argument('--task', '-t', type=str, help='Task description to execute')
    parser.add_argument('--workers', '-w', type=int, default=2,
                       help='Maximum parallel workers (default: 2)')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--version', '-v', action='version', version='%(prog)s 0.1.0')

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Check if running in interactive or direct mode
    if args.url and args.task:
        # Direct mode
        url = args.url
        task = args.task
        workers = args.workers
    else:
        # Interactive mode
        if args.url or args.task:
            print_warning("Both --url and --task are required for direct mode")
            print_info("Switching to interactive mode...\n")

        try:
            url, task, workers = get_interactive_inputs()
        except KeyboardInterrupt:
            print_warning("\n\nOperation cancelled by user")
            sys.exit(0)

    # Validate inputs
    if not validate_url(url):
        print_error(f"Invalid URL: {url}")
        sys.exit(1)

    if not task:
        print_error("Task cannot be empty")
        sys.exit(1)

    # Run automation
    try:
        success = asyncio.run(run_automation(url, task, workers, args.headless))
        sys.exit(0 if success else 1)
    except Exception as e:
        print_error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
