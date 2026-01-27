#  Copyright 2020-2026 Robert Bosch GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# *******************************************************************************
#
# File: run_tests.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Script to run all tests for ProcessHub package.
#
# Usage:
#   python run_tests.py              # Run all tests
#   python run_tests.py -v           # Run with verbose output
#   python run_tests.py --cov        # Run with coverage report
#   python run_tests.py --unit       # Run unit tests only
#   python run_tests.py --integration # Run integration tests only
#
# *******************************************************************************
"""
Test runner script for ProcessHub package.

This script provides a convenient way to run all tests with various options.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Run ProcessHub tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py              # Run all tests
  python run_tests.py -v           # Run with verbose output
  python run_tests.py --cov        # Run with coverage report
  python run_tests.py --unit       # Run unit tests only
  python run_tests.py --integration # Run integration tests only
  python run_tests.py -k "restart" # Run tests matching "restart"
        """,
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Run tests with verbose output",
    )
    parser.add_argument(
        "--cov", "--coverage",
        action="store_true",
        help="Run tests with coverage report",
    )
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Run unit tests only",
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests only",
    )
    parser.add_argument(
        "-k", "--keyword",
        type=str,
        help="Run tests matching the given keyword expression",
    )
    parser.add_argument(
        "-x", "--exitfirst",
        action="store_true",
        help="Exit on first failure",
    )
    parser.add_argument(
        "--html",
        type=str,
        metavar="FILE",
        help="Generate HTML report to FILE",
    )

    args = parser.parse_args()

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Determine test path
    root_dir = Path(__file__).parent
    tests_dir = root_dir

    if args.unit:
        cmd.append(str(tests_dir / "unit"))
    elif args.integration:
        cmd.append(str(tests_dir / "integration"))
    else:
        cmd.append(str(tests_dir))

    # Add options
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    if args.cov:
        cmd.extend(["--cov=ProcessHub", "--cov-report=term-missing"])

    if args.keyword:
        cmd.extend(["-k", args.keyword])

    if args.exitfirst:
        cmd.append("-x")

    if args.html:
        cmd.extend(["--html", args.html, "--self-contained-html"])

    # Add color output
    cmd.append("--color=yes")

    # Print command being run
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    # Run tests
    result = subprocess.run(cmd, cwd=root_dir)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
