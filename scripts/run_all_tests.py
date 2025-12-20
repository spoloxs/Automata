#!/usr/bin/env python3
"""
Run all tests one by one and report results.
Shows which tests pass/fail individually.
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class TestResult:
    """Test result container"""

    file: str
    status: str  # 'PASSED', 'FAILED', 'ERROR', 'SKIPPED'
    duration: float
    output: str


# Project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def find_all_tests(test_dir: Path) -> List[Path]:
    """Find all test files"""
    return sorted(test_dir.rglob("test_*.py"))


def run_single_test(test_file: Path) -> TestResult:
    """Run a single test file"""
    rel_path = test_file.relative_to(PROJECT_ROOT)

    print(f"\n{'=' * 70}")
    print(f"Running: {rel_path}")
    print(f"{'=' * 70}")

    start_time = time.time()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        duration = time.time() - start_time

        output = result.stdout + result.stderr

        # Determine status
        if result.returncode == 0:
            status = "PASSED"
            print("✅ PASSED")
        elif "error" in output.lower() or "importerror" in output.lower():
            status = "ERROR"
            print("❌ ERROR (Import/Setup Issue)")
        elif result.returncode == 5:
            status = "SKIPPED"
            print("⚠️  SKIPPED (No tests collected)")
        else:
            status = "FAILED"
            print("❌ FAILED")

        return TestResult(
            file=str(rel_path), status=status, duration=duration, output=output
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print("⏱️  TIMEOUT")
        return TestResult(
            file=str(rel_path),
            status="TIMEOUT",
            duration=duration,
            output="Test timed out after 60 seconds",
        )

    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 EXCEPTION: {e}")
        return TestResult(
            file=str(rel_path), status="EXCEPTION", duration=duration, output=str(e)
        )


def print_summary(results: List[TestResult]):
    """Print summary of all test results"""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70 + "\n")

    # Categorize results
    passed = [r for r in results if r.status == "PASSED"]
    failed = [r for r in results if r.status == "FAILED"]
    errors = [r for r in results if r.status == "ERROR"]
    skipped = [r for r in results if r.status == "SKIPPED"]
    timeouts = [r for r in results if r.status == "TIMEOUT"]

    # Print by category
    if passed:
        print(f"✅ PASSED ({len(passed)}):")
        for r in passed:
            print(f"   {r.file} ({r.duration:.2f}s)")

    if skipped:
        print(f"\n⚠️  SKIPPED ({len(skipped)}):")
        for r in skipped:
            print(f"   {r.file}")

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}) - Import/Setup Issues:")
        for r in errors:
            print(f"   {r.file}")
            # Show first error line
            for line in r.output.split("\n"):
                if (
                    "Error" in line
                    or "ImportError" in line
                    or "ModuleNotFoundError" in line
                ):
                    print(f"      → {line.strip()}")
                    break

    if failed:
        print(f"\n❌ FAILED ({len(failed)}) - Test Failures:")
        for r in failed:
            print(f"   {r.file}")

    if timeouts:
        print(f"\n⏱️  TIMEOUTS ({len(timeouts)}):")
        for r in timeouts:
            print(f"   {r.file}")

    # Overall stats
    print("\n" + "=" * 70)
    total = len(results)
    print(f"TOTAL: {total} test files")
    print(f"  ✅ Passed:  {len(passed)}")
    print(f"  ⚠️  Skipped: {len(skipped)}")
    print(f"  ❌ Failed:  {len(failed)}")
    print(f"  ❌ Errors:  {len(errors)}")
    print(f"  ⏱️  Timeout: {len(timeouts)}")
    print("=" * 70)

    # Exit code
    if errors or failed or timeouts:
        return 1
    return 0


def main():
    """Main test runner"""
    print("🧪 Web Agent Test Runner")
    print("=" * 70)
    print(f"Project root: {PROJECT_ROOT}\n")

    # Find all tests
    test_dir = PROJECT_ROOT / "tests"
    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        sys.exit(1)

    test_files = find_all_tests(test_dir)

    if not test_files:
        print(f"❌ No test files found in {test_dir}")
        sys.exit(1)

    print(f"Found {len(test_files)} test files\n")

    # Run all tests
    results = []
    for test_file in test_files:
        result = run_single_test(test_file)
        results.append(result)

    # Print summary
    exit_code = print_summary(results)

    # Save detailed report
    report_file = PROJECT_ROOT / "test_report.txt"
    with open(report_file, "w") as f:
        f.write("DETAILED TEST REPORT\n")
        f.write("=" * 70 + "\n\n")
        for r in results:
            f.write(f"File: {r.file}\n")
            f.write(f"Status: {r.status}\n")
            f.write(f"Duration: {r.duration:.2f}s\n")
            f.write(f"Output:\n{r.output}\n")
            f.write("-" * 70 + "\n\n")

    print(f"\n📄 Detailed report saved to: {report_file}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
