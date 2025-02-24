#!/usr/bin/env python
import pytest
from pathlib import Path
import argparse

def run_tests(test_type="all"):
    """Run tests based on the specified type
    
    Args:
        test_type (str): Type of tests to run ('unit', 'integration', or 'all')
    """
    root_dir = Path(__file__).parent
    test_dir = root_dir / "tests"
    
    # Base pytest arguments
    pytest_args = [
        str(test_dir),
        "-v",
        "--no-header",
        "-W", "ignore::pytest.PytestCollectionWarning"
    ]
    
    # Add markers based on test type
    if test_type == "unit":
        pytest_args.extend(["-m", "not integration"])
    elif test_type == "integration":
        pytest_args.extend(["-m", "integration"])
    
    # Run tests
    return pytest.main(pytest_args)

def main():
    parser = argparse.ArgumentParser(description="Run tests for Resource Management Assistant")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "all"],
        default="all",
        help="Type of tests to run (unit, integration, or all)"
    )
    
    args = parser.parse_args()
    exit_code = run_tests(args.type)
    
    if exit_code == pytest.ExitCode.OK:
        print("✅ All tests passed!")
    else:
        print("❌ Tests failed!")
        exit(1)

if __name__ == "__main__":
    main()