from datetime import datetime

import pytest

from .instances import all_scenario_creation_funcs
from .types import TestScenario


@pytest.fixture
def base_timestamp():
    """Base timestamp for all mock events"""
    return datetime(2025, 5, 29, 9, 0, 0)


def create_test_scenarios() -> list[TestScenario]:
    """Create test scenarios for timeline aggregation"""
    base_time = datetime(2024, 1, 15, 9, 0, 0)

    return [scenario_func(base_time) for scenario_func in all_scenario_creation_funcs]


all_scenarios = create_test_scenarios()
