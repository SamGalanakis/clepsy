import pytest

from clepsy.aggregator_worker import manual_activity_reconciliation
import clepsy.entities as E
from tests.scenarios import scenarios


pytestmark = pytest.mark.llm

# Expand scenarios into (scenario, case) pairs for all manual reconciliation cases
scenario_case_pairs: list[tuple] = []
for s in scenarios:
    for c in getattr(s, "manual_reconciliation_cases", []) or []:
        scenario_case_pairs.append((s, c))

param_ids = [f"{sc.name}::{case.name}" for sc, case in scenario_case_pairs] or [
    "no-cases"
]


@pytest.mark.parametrize(
    "scenario,case",
    scenario_case_pairs,
    ids=param_ids,
)
@pytest.mark.asyncio
async def test_manual_reconciliation_cases(scenario, case, mock_user_settings):
    # Defensive: ensure generated data exists
    if (
        not scenario.generated_timeline_activities
        or not scenario.generated_timeline_events
    ):
        pytest.skip("Scenario has no generated data")

    # Use manual specs from the case
    manual_specs: list[E.DBActivitySpec] = list(case.manual_activity_specs)

    activities_after, events_after = await manual_activity_reconciliation(
        manual_activities=manual_specs,
        generated_timeline_activities=dict(scenario.generated_timeline_activities),
        generated_timeline_events=list(scenario.generated_timeline_events),
        aggregation_time_span=scenario.aggregation_time_span,
        text_model_config=mock_user_settings.text_model_config,
    )

    assert activities_after == case.expected_after_manual_activities
    assert events_after == case.expected_after_manual_events
