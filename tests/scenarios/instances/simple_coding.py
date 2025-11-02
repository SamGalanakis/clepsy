from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import ManualReconciliationCase, TestScenario


def make_simple_coding_session(base_time) -> TestScenario:
    # Screenshot cadence: 30s within the same app (VSCode); no app/domain switches
    input_logs: List[E.AggregationInputEvent] = [
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Opening VS Code and loading main.py for implementation work.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing main.py in VS Code.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Actively coding in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Typing and navigating within main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Writing code in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Continuing development work in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Working through implementation details in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing and scrolling in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Actively coding in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Making changes and reviewing code in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Continuing coding session in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing functions in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Coding continues in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Refactoring code in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Implementing additional logic in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing and scrolling in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reviewing recent changes in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Minor edits in main.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=0),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Coding in main.py before switching to tests.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=30),
            active_window=E.WindowInfo(
                title="main.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Preparing to write tests.",
        ),
        # Switch to tests at 10:00 within the same repo/workspace
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="test.py - Visual Studio Code",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Switched to test.py to write unit tests for the new functionality.",
        ),
    ]

    activities = {
        "python_development": baml_types.ActivityMetadata(
            name="Python Development",
            description="Working on Python code in VS Code.",
        ),
    }

    events = [
        baml_types.Event(
            activity_id="python_development",
            event_type="open",
            t="0m0s",
        ),
    ]
    events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    expected_aggregator_output = AggregatorCoreOutput(
        new_activities=activities,
        new_activity_events=events,
        stitched_activities_events=[],
        unstitched_activities_close_events=[],
        activities_to_update=[],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    # Manual specs for different cases
    # 1) Non-overlapping manual session before the aggregation window
    manual_non_overlap_activity = E.DBActivity(
        id=5001,
        name="Manual Coding",
        description="Manually tracked coding session",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_non_overlap_events = [
        E.DBActivityEvent(
            id=1,
            event_time=base_time - timedelta(minutes=15),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=2,
            event_time=base_time - timedelta(minutes=12),
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

    # 2) Overlapping manual session with no match (different name tokens)
    manual_overlap_no_match_activity = E.DBActivity(
        id=5002,
        name="Gardening",
        description="Unrelated manual activity",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_no_match_events = [
        E.DBActivityEvent(
            id=3,
            event_time=base_time + timedelta(minutes=2),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=4,
            event_time=base_time + timedelta(minutes=8),
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

    # 3) Overlapping manual session with exact name match -> should remove auto activity
    manual_overlap_match_activity = E.DBActivity(
        id=5003,
        name="Python Development",
        description="Same as auto activity",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_match_events = [
        E.DBActivityEvent(
            id=5,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=6,
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

    # 4) Ambiguous manual that shares tokens but not an exact name -> triggers LLM
    manual_llm_ambiguous_activity = E.DBActivity(
        id=5004,
        name="Python Coding",
        description="Similar to auto but not exact",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_llm_ambiguous_events = [
        E.DBActivityEvent(
            id=7,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_llm_ambiguous_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=8,
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

    # 5) Plausible multitasking: Listening to Podcast while coding -> keep auto
    manual_plausible_podcast_activity = E.DBActivity(
        id=5005,
        name="Podcast Listening",
        description="Listening to a podcast",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_plausible_podcast_events = [
        E.DBActivityEvent(
            id=9,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_plausible_podcast_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=10,
            event_time=base_time + timedelta(minutes=9),
            event_type=E.ActivityEventType.CLOSE,
            aggregation_id=None,
            activity_id=manual_plausible_podcast_activity.id,
            last_manual_action_time=None,
        ),
    ]
    manual_plausible_podcast_specs = [
        E.DBActivitySpec(
            activity=manual_plausible_podcast_activity,
            events=manual_plausible_podcast_events,
        )
    ]
    return TestScenario(
        name="simple_coding_session",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Simple coding session in VS Code with frequent screenshots (30s cadence)",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        manual_reconciliation_cases=[
            ManualReconciliationCase(
                name="non_overlap",
                manual_activity_specs=manual_non_overlap_specs,
                expected_after_manual_activities=activities,
                expected_after_manual_events=events,
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
                expected_after_manual_activities={},
                expected_after_manual_events=[],
            ),
            ManualReconciliationCase(
                name="llm_overlap_ambiguous",
                manual_activity_specs=manual_llm_ambiguous_specs,
                expected_after_manual_activities={},
                expected_after_manual_events=[],
            ),
            ManualReconciliationCase(
                name="plausible_overlap_podcast",
                manual_activity_specs=manual_plausible_podcast_specs,
                expected_after_manual_activities=activities,
                expected_after_manual_events=events,
            ),
        ],
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
