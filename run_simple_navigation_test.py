"""
Standalone runner for the simplified navigation test.
This script allows running the navigation-only test without pytest,
which is helpful for focused debugging.
"""

import asyncio
import os
import sys
import traceback
import warnings

# Suppress the specific SyntaxWarning from the transformers library.
warnings.filterwarnings(
    "ignore",
    message=r"invalid escape sequence '\\d'",
    category=SyntaxWarning,
)

# Add the 'src' directory to the Python path to allow for absolute imports.
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the specific test function.
try:
    from tests.integration.test_simple_navigation import (
        test_single_navigation_task,
    )
except ImportError as e:
    print(
        f"Error: Could not import test function. Ensure paths and dependencies are correct."
    )
    print(f"Details: {e}")
    sys.exit(1)


async def main():
    """
    Asynchronous main function to run the simplified navigation test.
    """
    print("--- Starting standalone navigation test runner ---")
    try:
        await test_single_navigation_task()
        print("\n--- Navigation test finished successfully! ---")
    except AssertionError as e:
        print(f"\n--- Navigation test FAILED with an assertion error ---")
        print(f"Assertion: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"\n--- Navigation test FAILED with an exception: {type(e).__name__} ---")
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        print("--- Standalone navigation runner finished ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n--- Test execution cancelled by user ---")
