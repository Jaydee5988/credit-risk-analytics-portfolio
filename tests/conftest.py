import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from credit_risk import data_generation  # noqa: E402


@pytest.fixture(scope="session")
def small_portfolio():
    """A small deterministic portfolio for fast tests."""
    return data_generation.generate_portfolio(n=1500, seed=7)
