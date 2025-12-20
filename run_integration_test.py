"""
Standalone runner for the integration test.
This script allows running the integration test without pytest,
which can be helpful for debugging and viewing logs directly.
"""

import asyncio
import os
import sys
import traceback
import warnings

# Suppress the specific SyntaxWarning from the transformers library, which is not in our control to fix.
warnings.filterwarnings(
    "ignore",
    message=r"invalid escape sequence '\\d'",
    category=SyntaxWarning,
)

# Add the 'src' directory to the Python path to allow for absolute imports
# This is necessary because the application code and tests use absolute paths
# relative to the 'src' directory.
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now that the path is configured, we can import the test function.
try:
    from tests.integration.test_supervised_execution import (
        test_supervised_execution_simple_goal,
    )
except ImportError as e:
    print(
        f"Error: Could not import the test function. Make sure the path is correct and all dependencies are installed."
    )
    print(f"Details: {e}")
    sys.exit(1)


async def main():
    """
    Asynchronous main function to set up and run the integration test.
    """
    print("--- Starting standalone integration test runner ---")
    try:
        # Await the test function directly.
        await test_supervised_execution_simple_goal()
        print("\n--- Test finished successfully! ---")
    except AssertionError as e:
        # Catch assertion errors specifically to provide a clear "test failed" message.
        print(f"\n--- Test FAILED with an assertion error ---")
        print(f"Assertion: {e}")
        traceback.print_exc()
    except Exception as e:
        # Catch any other exceptions that might occur during the test.
        print(f"\n--- Test FAILED with an exception: {type(e).__name__} ---")
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        # This will run whether the test passes, fails, or is interrupted.
        print("--- Standalone runner finished ---")


if __name__ == "__main__":
    # Use a try/except block to gracefully handle manual termination (Ctrl+C).
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n--- Test execution cancelled by user ---")
