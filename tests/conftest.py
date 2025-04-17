import sys
import os
import pytest
import coverage

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from .fixtures.types import *  # noqa: F403
from .fixtures.example_data import *  # noqa: F403
from .fixtures.simple_app import *  # noqa: F403
from .fixtures.complex_app import *  # noqa: F403


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """Configure pytest-cov for proper subprocess coverage."""
    if config.pluginmanager.hasplugin("pytest_cov"):
        # Ensure environment variables are set for subprocess coverage
        os.environ["COVERAGE_PROCESS_START"] = os.path.abspath(".coveragerc")

        # Set up environment for combinining coverage data from subprocesses
        os.environ["PYTHONPATH"] = os.path.abspath(".")

        # Make sure the pytest-cov plugin is active for subprocesses
        config.option.cov_fail_under = 0  # Disable fail under in the primary process


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Combine coverage data from subprocesses at the end of the test session."""
    cov_dir = os.path.abspath(".")
    if exitstatus == 0 and os.environ.get("COVERAGE_PROCESS_START"):
        try:
            cov = coverage.Coverage()
            cov.combine(data_paths=[cov_dir], strict=True)
            cov.save()
        except Exception as e:
            print(f"Error combining coverage data: {e}", file=sys.stderr)
