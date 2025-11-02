from datetime import datetime, timedelta
from typing import List

from pydantic import BaseModel, Field, model_validator

import baml_client.types as baml_types
from clepsy.config import config
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput
from clepsy.modules.aggregator.programmatic_timeline_validation import (
    validate_aggregator_core_output,
    validate_timeline_programmatically,
)


class ManualReconciliationCase(BaseModel):
    """A single manual reconciliation test case for a scenario.

    It bundles the manual specs to apply and the expected timeline after reconciliation.
    """

    name: str
    manual_activity_specs: List[E.DBActivitySpec]
    expected_after_manual_activities: dict[str, baml_types.ActivityMetadata]
    expected_after_manual_events: list[baml_types.Event]


class TestScenario(BaseModel):
    """Test scenario with input desktop checks and expected timeline output"""

    __test__ = False
    name: str
    input_logs: List[E.AggregationInputEvent]
    generated_timeline_activities: dict[str, baml_types.ActivityMetadata]
    generated_timeline_events: list[baml_types.Event]
    expected_aggregator_output: AggregatorCoreOutput
    stitchable_activity_to_llm_id: dict[int, str]
    description: str
    aggregation_time_span: E.TimeSpan
    previous_aggregation_end_time: datetime | None = Field(
        description="End time of the previous aggregation, if any."
    )
    manual_reconciliation_cases: List[ManualReconciliationCase] = []
    stitchable_closed_activities: List[E.DBActivityWithLatestEvent]
    open_auto_activities: List[E.DBActivityWithLatestEvent]

    @model_validator(mode="after")
    def validate_input_logs(self) -> "TestScenario":
        input_logs = self.input_logs
        time_span = self.aggregation_time_span
        expected_output = self.expected_aggregator_output

        error_strings = validate_aggregator_core_output(
            expected_output,
            aggregation_time_span=time_span,
            stitchable_activities=self.stitchable_closed_activities
            + self.open_auto_activities,
        )

        if error_strings:
            raise ValueError(
                f"Validation errors in expected_aggregator_output: {', '.join(error_strings)}"
            )

        stitched_ids = self.stitchable_activity_to_llm_id.keys()
        updated_ids = {
            activity_id for activity_id, _ in expected_output.activities_to_update
        }

        if stitched_ids != updated_ids:
            raise ValueError(
                f"Stitched activity IDs {stitched_ids} do not match updated activity IDs {updated_ids}"
            )

        five_seconds = timedelta(seconds=5)
        if abs(time_span.duration - config.aggregation_interval) > five_seconds:
            raise ValueError(
                f"Aggregation time span must be within 5 seconds of {config.aggregation_interval_minutes} minutes"
            )

        if not input_logs or not time_span:
            raise ValueError("Input checks and aggregation time span must not be empty")

        # If manual reconciliation cases provided, ensure they are well-formed
        for c in self.manual_reconciliation_cases:
            if not c.manual_activity_specs:
                raise ValueError(
                    f"Manual reconciliation case '{c.name}' must include manual_activity_specs"
                )

        # Check order
        for i in range(len(input_logs) - 1):
            if input_logs[i].timestamp > input_logs[i + 1].timestamp:
                raise ValueError("Input checks are not sorted by timestamp")

        # Check if within time span
        for check in input_logs:
            if not (time_span.start_time <= check.timestamp <= time_span.end_time):
                raise ValueError(
                    f"Input check timestamp {check.timestamp} is outside of aggregation time span"
                )

        return self


class IsolatedTestScenario(BaseModel):
    """Scenario slice for isolated timeline generation only.

    Contains only the inputs and expected outputs for the isolated step.
    """

    __test__ = False
    name: str
    input_logs: List[E.AggregationInputEvent]
    generated_timeline_activities: dict[str, baml_types.ActivityMetadata]
    generated_timeline_events: list[baml_types.Event]
    aggregation_time_span: E.TimeSpan
    description: str

    @model_validator(mode="after")
    def validate_isolated(self) -> "IsolatedTestScenario":
        # Reuse programmatic validator for quick sanity checks
        timeline = baml_types.Timeline(
            activities=self.generated_timeline_activities,
            events=self.generated_timeline_events,
        )
        errors = validate_timeline_programmatically(
            timeline=timeline, aggregation_time_span=self.aggregation_time_span
        )
        if errors:
            raise ValueError(
                f"Validation errors in isolated scenario '{self.name}': {', '.join(errors)}"
            )
        return self


class StitchingTestScenario(BaseModel):
    """Scenario slice for stitching only.

    Inputs: generated activities/events and stitchable activities.
    Expected: stitched and unstitched close events plus activities_to_update.
    """

    __test__ = False
    name: str
    generated_timeline_activities: dict[str, baml_types.ActivityMetadata]
    generated_timeline_events: list[baml_types.Event]
    stitchable_closed_activities: List[E.DBActivityWithLatestEvent]
    open_auto_activities: List[E.DBActivityWithLatestEvent]
    aggregation_time_span: E.TimeSpan
    previous_aggregation_end_time: datetime | None
    # Expectations
    expected_stitched_activities_events: list[E.NewActivityEventExistingActivity]
    expected_unstitched_activities_close_events: list[
        E.NewActivityEventExistingActivity
    ]
    expected_activities_to_update: list[tuple[int, dict[str, str]]]
    stitchable_activity_to_llm_id: dict[int, str]


def as_isolated(s: TestScenario) -> IsolatedTestScenario:
    """Derive an IsolatedTestScenario from the canonical TestScenario."""
    return IsolatedTestScenario(
        name=s.name,
        input_logs=s.input_logs,
        generated_timeline_activities=s.generated_timeline_activities,
        generated_timeline_events=s.generated_timeline_events,
        aggregation_time_span=s.aggregation_time_span,
        description=s.description,
    )


def as_stitching(s: TestScenario) -> StitchingTestScenario:
    """Derive a StitchingTestScenario from the canonical TestScenario."""
    expected = s.expected_aggregator_output
    return StitchingTestScenario(
        name=s.name,
        generated_timeline_activities=s.generated_timeline_activities,
        generated_timeline_events=s.generated_timeline_events,
        stitchable_closed_activities=s.stitchable_closed_activities,
        open_auto_activities=s.open_auto_activities,
        aggregation_time_span=s.aggregation_time_span,
        previous_aggregation_end_time=s.previous_aggregation_end_time,
        expected_stitched_activities_events=expected.stitched_activities_events,
        expected_unstitched_activities_close_events=expected.unstitched_activities_close_events,
        expected_activities_to_update=expected.activities_to_update,
        stitchable_activity_to_llm_id=s.stitchable_activity_to_llm_id,
    )
