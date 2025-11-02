from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import ManualReconciliationCase, TestScenario


def make_interrupted_design_work(base_time) -> TestScenario:
    input_logs: List[E.AggregationInputEvent] = [
        # Figma: 0:00 → 4:55 at 30s cadence, then a 5s gap before switch
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating wireframes for a new mobile app in Figma.",
        ),
        # Slack: 5:00 → 9:55 at 30s cadence
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6, seconds=30),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=30),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=30),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=30),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="design-team - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User checking messages from the design team on Slack.",
        ),
        # Return to Figma at 10:00
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10),
            active_window=E.WindowInfo(
                title="Mobile App Wireframes - Figma",
                app_name="Figma",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User returned to working on the wireframes in Figma.",
        ),
    ]

    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Design Work",
                description="Working on a design in Figma.",
                productivity_level=E.ProductivityLevel.PRODUCTIVE,
                last_manual_action_time=None,
                source=E.Source.AUTO,
            ),
            latest_event=E.DBActivityEvent(
                id=1,
                event_time=base_time - timedelta(minutes=3),
                event_type=E.ActivityEventType.CLOSE,
                aggregation_id=1,
                activity_id=1,
                last_manual_action_time=None,
            ),
            latest_aggregation=E.DBAggregation(
                start_time=base_time - timedelta(minutes=13),
                end_time=base_time - timedelta(minutes=3),
                first_timestamp=base_time - timedelta(minutes=13),
                last_timestamp=base_time - timedelta(minutes=3),
                id=1,
            ),
        )
    ]

    generated_timeline_activities = {
        "llm_design_work": baml_types.ActivityMetadata(
            name="Design Work",
            description="Working on a design in Figma.",
        ),
        "communication": baml_types.ActivityMetadata(
            name="Communication",
            description="Checking messages on Slack.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(activity_id="llm_design_work", event_type="open", t="0m0s"),
        baml_types.Event(activity_id="llm_design_work", event_type="close", t="5m0s"),
        baml_types.Event(activity_id="communication", event_type="open", t="5m0s"),
        baml_types.Event(activity_id="communication", event_type="close", t="10m0s"),
        baml_types.Event(activity_id="llm_design_work", event_type="open", t="10m0s"),
    ]
    generated_timeline_events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    new_activities = {
        "communication": baml_types.ActivityMetadata(
            name="Communication",
            description="Checking messages on Slack.",
        ),
    }

    new_events = [
        baml_types.Event(
            activity_id="communication",
            event_type="open",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="communication",
            event_type="close",
            t="10m0s",
        ),
    ]
    new_events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    events_to_insert = [
        E.NewActivityEventExistingActivity(
            event_time=base_time,
            event_type=E.ActivityEventType.OPEN,
            activity_id=1,
        ),
        E.NewActivityEventExistingActivity(
            event_time=base_time + timedelta(minutes=5),
            event_type=E.ActivityEventType.CLOSE,
            activity_id=1,
        ),
        E.NewActivityEventExistingActivity(
            event_time=base_time + timedelta(minutes=10),
            event_type=E.ActivityEventType.OPEN,
            activity_id=1,
        ),
    ]

    expected_aggregator_output = AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_events,
        stitched_activities_events=events_to_insert,
        unstitched_activities_close_events=[],
        activities_to_update=[
            (1, {"name": "Design Work", "description": "Working on a design in Figma."})
        ],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    # Manual specs for cases
    manual_non_overlap_activity = E.DBActivity(
        id=6101,
        name="Personal Task",
        description="Manual personal activity",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_non_overlap_events = [
        E.DBActivityEvent(
            id=21,
            event_time=base_time - timedelta(minutes=25),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=22,
            event_time=base_time - timedelta(minutes=20),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_non_overlap_specs = [
        E.DBActivitySpec(
            activity=manual_non_overlap_activity, events=manual_non_overlap_events
        )
    ]

    manual_overlap_no_match_activity = E.DBActivity(
        id=6102,
        name="Cooking",
        description="Totally unrelated",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_no_match_events = [
        E.DBActivityEvent(
            id=23,
            event_time=base_time + timedelta(minutes=2),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=24,
            event_time=base_time + timedelta(minutes=9),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_overlap_no_match_specs = [
        E.DBActivitySpec(
            activity=manual_overlap_no_match_activity,
            events=manual_overlap_no_match_events,
        )
    ]

    manual_overlap_match_activity = E.DBActivity(
        id=6103,
        name="Design Work",
        description="Working on a design in Figma.",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_match_events = [
        E.DBActivityEvent(
            id=25,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=26,
            event_time=base_time + timedelta(minutes=9),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_overlap_match_specs = [
        E.DBActivitySpec(
            activity=manual_overlap_match_activity, events=manual_overlap_match_events
        )
    ]

    # 4) Ambiguous overlap that shares tokens with 'Design Work' but not exact
    manual_llm_ambiguous_activity = E.DBActivity(
        id=6104,
        name="Designing Work",
        description="Similar but not exact",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_llm_ambiguous_events = [
        E.DBActivityEvent(
            id=27,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_llm_ambiguous_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=28,
            event_time=base_time + timedelta(minutes=9),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_llm_ambiguous_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_llm_ambiguous_specs = [
        E.DBActivitySpec(
            activity=manual_llm_ambiguous_activity,
            events=manual_llm_ambiguous_events,
        )
    ]

    return TestScenario(
        name="interrupted_design_work",
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={1: "llm_design_work"},
        stitchable_closed_activities=stitchable_closed_activities,
        description="Design work session interrupted by team communication.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        manual_reconciliation_cases=[
            ManualReconciliationCase(
                name="non_overlap",
                manual_activity_specs=manual_non_overlap_specs,
                expected_after_manual_activities=generated_timeline_activities,
                expected_after_manual_events=generated_timeline_events,
            ),
            ManualReconciliationCase(
                name="overlap_no_match",
                manual_activity_specs=manual_overlap_no_match_specs,
                expected_after_manual_activities={},
                expected_after_manual_events=[],
            ),
            ManualReconciliationCase(
                name="overlap_match",
                manual_activity_specs=manual_overlap_match_specs,
                expected_after_manual_activities={
                    "communication": baml_types.ActivityMetadata(
                        name="Communication",
                        description="Checking messages on Slack.",
                    ),
                },
                expected_after_manual_events=[
                    baml_types.Event(
                        activity_id="communication", event_type="open", t="5m0s"
                    ),
                    baml_types.Event(
                        activity_id="communication", event_type="close", t="10m0s"
                    ),
                ],
            ),
            ManualReconciliationCase(
                name="llm_overlap_ambiguous",
                manual_activity_specs=manual_llm_ambiguous_specs,
                expected_after_manual_activities={
                    "communication": baml_types.ActivityMetadata(
                        name="Communication",
                        description="Checking messages on Slack.",
                    )
                },
                expected_after_manual_events=[
                    baml_types.Event(
                        activity_id="communication", event_type="open", t="5m0s"
                    ),
                    baml_types.Event(
                        activity_id="communication", event_type="close", t="10m0s"
                    ),
                ],
            ),
        ],
        open_auto_activities=[],
    )
