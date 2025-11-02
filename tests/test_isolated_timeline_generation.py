from baml_py import Collector
from loguru import logger
import pytest

from baml_client.async_client import b
from clepsy.aggregator_worker import (
    generate_isolated_timeline,
    prepare_timeline_aggregator_inputs,
)
from clepsy.config import config
import clepsy.entities as E
from clepsy.llm import create_client_registry
from tests.scenarios import scenarios
from tests.scenarios.types import IsolatedTestScenario, as_isolated


isolated_scenarios = [as_isolated(s) for s in scenarios]

pytestmark = pytest.mark.llm


@pytest.mark.parametrize(
    "qc_policy", list(E.IsolatedTimelineQCPolicy), ids=lambda p: f"qc={p.name}"
)
@pytest.mark.parametrize(
    "scenario", isolated_scenarios, ids=[s.name for s in isolated_scenarios]
)
async def test_isolated_timeline_generation(
    scenario: IsolatedTestScenario,
    mock_user_settings: E.UserSettings,
    qc_policy: E.IsolatedTimelineQCPolicy,
):
    collector = Collector()
    new_activities, new_events = await generate_isolated_timeline(
        input_logs=scenario.input_logs,
        aggregation_time_span=scenario.aggregation_time_span,
        text_model_config=mock_user_settings.text_model_config,
        collector=collector,
        qc_policy=qc_policy,
        max_desktop_screenshot_log_interval_seconds=config.max_desktop_screenshot_log_interval_seconds,
        max_pause_time_seconds=config.max_pause_time_seconds,
        aggregation_interval_seconds=int(config.aggregation_interval.total_seconds()),
    )

    client = create_client_registry(
        llm_config=mock_user_settings.text_model_config,
        name="TextClient",
        set_primary=True,
    )

    inputs = prepare_timeline_aggregator_inputs(
        input_logs=scenario.input_logs,
        aggregation_time_span=scenario.aggregation_time_span,
    )
    validation_result = await b.ValidateTimelineAgainstExpected(
        input_logs=inputs.logs,
        generated_activities=new_activities,
        generated_events=new_events,
        expected_generated_activities=scenario.generated_timeline_activities,
        expected_generated_events=scenario.generated_timeline_events,
        duration_seconds=int(config.aggregation_interval.total_seconds()),
        max_pause_time_seconds=config.max_pause_time_seconds,
        max_desktop_screenshot_log_interval_seconds=config.max_desktop_screenshot_log_interval_seconds,
        baml_options={"client_registry": client},
    )

    is_valid = validation_result.validation_result.grade >= 0.5

    logger.info(f"LLM Validation Result: {is_valid}")
    logger.debug(f"LLM Reasoning: {validation_result.reasoning}")

    assert is_valid, (
        f"LLM validation failed for scenario {scenario.name}: "
        f"{validation_result.validation_result.error_description}"
    )

    if validation_result.validation_result.grade < 0.7:
        logger.warning(
            f"LLM validation for scenario {scenario.name} is <0.7"
            f"{validation_result.validation_result.error_description}"
        )

    logger.info(f"✓ Scenario {scenario.name} passed validation")
    logger.info(f"Reasoning: {validation_result.reasoning}")
