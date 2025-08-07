import pytest
import sys
from pathlib import Path

def main():
    """Run test suite with proper configuration."""
    test_dir = Path(__file__).parent
    
    pytest_args = [
        str(test_dir),
        '-v',  # Verbose output
        '--tb=short',  # Shorter traceback format
        '--strict-markers',  # Strict marker validation
        '--randomly-seed=1234',  # Consistent random seed
        '--durations=10',  # Show 10 slowest tests
        '--cov=.',  # Coverage reporting
        '--cov-report=term-missing',  # Show missing lines
        '--cov-report=html:coverage_report'  # HTML coverage report
    ]
    
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
