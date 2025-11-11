import pytest

from clepsy.config import config
import clepsy.entities as E
from clepsy.llm import create_client_registry
from clepsy.modules.aggregator.stitching import stitch_timeline
from tests.scenarios import scenarios
from tests.scenarios.types import StitchingTestScenario, as_stitching


stitching_scenarios = [
    as_stitching(s)
    for s in scenarios
    if s.stitchable_closed_activities or s.open_auto_activities
]


pytestmark = pytest.mark.llm


@pytest.mark.parametrize(
    "scenario",
    stitching_scenarios,
    ids=[scenario.name for scenario in stitching_scenarios],
)
async def test_stitch_timeline(
    scenario: StitchingTestScenario, mock_llm_config: E.LLMConfig
):
    stitchable_activities = (
        scenario.stitchable_closed_activities + scenario.open_auto_activities
    )

    stitch_output = await stitch_timeline(
        generated_timeline_activites=scenario.generated_timeline_activities,
        generated_timeline_events=scenario.generated_timeline_events,
        aggregation_time_span=scenario.aggregation_time_span,
        previous_aggregation_end_time=scenario.previous_aggregation_end_time,
        stitchable_activities=stitchable_activities,
        max_activity_pause_time=config.max_activity_pause_time,
        baml_client_registry=create_client_registry(
            llm_config=mock_llm_config,
            name="TextClient",
            set_primary=True,
        ),
    )

    # Expected values carried in the derived scenario

    # Check that the same activities are stitched
    assert (
        stitch_output.stitchable_activity_to_llm_id
        == scenario.stitchable_activity_to_llm_id
    ), "Stitched LLM IDs do not match"
    # Check that the stitched activities events match the expected output
    stitchable_activity_to_llm_id = scenario.stitchable_activity_to_llm_id
    stitched_activity_ids = stitchable_activity_to_llm_id.keys()

    for stitched_activity_id in stitched_activity_ids:
        expected_stitched_activity_events = [
            x
            for x in scenario.expected_stitched_activities_events
            if x.activity_id == stitched_activity_id
        ]

        actual_stitched_activity_events = [
            x
            for x in stitch_output.stitched_activities_events
            if x.activity_id == stitched_activity_id
        ]

        actual_stitched_activity_events.sort(key=lambda x: x.event_time)
        expected_stitched_activity_events.sort(key=lambda x: x.event_time)
        for actual, expected in zip(
            actual_stitched_activity_events, expected_stitched_activity_events
        ):
            assert actual.event_time == expected.event_time, "Event times do not match"
            assert actual.event_type == expected.event_type, "Event types do not match"

    # Check unstitched activities close events

    expected_not_stitched_close_events = (
        scenario.expected_unstitched_activities_close_events
    )
    expected_not_stitched_close_events.sort(key=lambda x: x.event_time)
    actual_not_stitched_close_events = stitch_output.unstitched_activities_close_events
    actual_not_stitched_close_events.sort(key=lambda x: x.event_time)
    for actual, expected in zip(
        actual_not_stitched_close_events, expected_not_stitched_close_events
    ):
        assert (
            actual.event_time == expected.event_time
        ), "Close event times do not match"
        assert (
            actual.event_type == expected.event_type
        ), "Close event types do not match"

    ##Check that the correct activities are updated
    expected_activities_to_update = scenario.expected_activities_to_update
    actual_activities_to_update = stitch_output.activities_to_update
    expected_activities_to_update_keys = {x[0] for x in expected_activities_to_update}
    actual_activities_to_update_keys = {x[0] for x in actual_activities_to_update}
    assert (
        expected_activities_to_update_keys == actual_activities_to_update_keys
    ), "Activities to update do not match"
