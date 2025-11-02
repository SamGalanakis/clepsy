from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E

from ..types import ManualReconciliationCase, TestScenario


def make_interrupted_content_creation(base_time) -> TestScenario:
    input_logs: List[E.AggregationInputEvent] = [
        # Google Docs in Chrome: 0:00 → 4:55 at 30s cadence, then a 5s gap before switch
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing a blog post in Google Docs.",
        ),
        # Slack: 5:00 → 9:55 at 30s cadence
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6, seconds=30),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=30),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=30),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=30),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="Video Call - Slack",
                app_name="Slack",
                is_active=True,
                bbox=E.Bbox(left=200, top=100, width=1000, height=700),
            ),
            llm_description="User on a video call in Slack.",
        ),
        # Return to Google Docs at 10:00
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10),
            active_window=E.WindowInfo(
                title="My Blog Post - Google Docs",
                app_name="Google Chrome",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User returned to writing the blog post in Google Docs.",
        ),
    ]

    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Content Creation",
                description="Writing a blog post in Google Docs.",
                productivity_level=E.ProductivityLevel.PRODUCTIVE,
                last_manual_action_time=None,
                source=E.Source.AUTO,
            ),
            latest_event=E.DBActivityEvent(
                id=1,
                event_time=base_time - timedelta(minutes=2),
                event_type=E.ActivityEventType.CLOSE,
                aggregation_id=1,
                activity_id=1,
                last_manual_action_time=None,
            ),
            latest_aggregation=E.DBAggregation(
                start_time=base_time - timedelta(minutes=12),
                end_time=base_time - timedelta(minutes=2),
                first_timestamp=base_time - timedelta(minutes=12),
                last_timestamp=base_time - timedelta(minutes=2),
                id=1,
            ),
        )
    ]

    generated_timeline_activities = {
        "llm_content_creation": baml_types.ActivityMetadata(
            name="Content Creation",
            description="Writing a blog post in Google Docs.",
        ),
        "communication": baml_types.ActivityMetadata(
            name="Communication",
            description="Video call in Slack.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(
            activity_id="llm_content_creation", event_type="open", t="0m0s"
        ),
        baml_types.Event(
            activity_id="llm_content_creation", event_type="close", t="5m0s"
        ),
        baml_types.Event(activity_id="communication", event_type="open", t="5m0s"),
        baml_types.Event(activity_id="communication", event_type="close", t="10m0s"),
        baml_types.Event(
            activity_id="llm_content_creation", event_type="open", t="10m0s"
        ),
    ]
    generated_timeline_events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    new_activities = {
        "communication": baml_types.ActivityMetadata(
            name="Communication",
            description="Video call in Slack.",
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

    expected_aggregator_output = E.AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_events,
        stitched_activities_events=events_to_insert,
        unstitched_activities_close_events=[],
        activities_to_update=[
            (
                1,
                {
                    "name": "Content Creation",
                    "description": "Writing a blog post in Google Docs.",
                },
            )
        ],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    # Manual specs for cases
    # 1) Non-overlapping manual activity entirely before the window
    manual_non_overlap_activity = E.DBActivity(
        id=6001,
        name="Personal Task",
        description="Manual personal activity",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_non_overlap_events = [
        E.DBActivityEvent(
            id=11,
            event_time=base_time - timedelta(minutes=25),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_non_overlap_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=12,
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

    # 2) Overlapping but unrelated manual activity (no shared tokens with auto activities)
    manual_overlap_no_match_activity = E.DBActivity(
        id=6002,
        name="Cooking",
        description="Totally unrelated",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_no_match_events = [
        E.DBActivityEvent(
            id=13,
            event_time=base_time + timedelta(minutes=2),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_no_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=14,
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

    # 3) Overlapping with exact name match to auto 'Content Creation' activity
    manual_overlap_match_activity = E.DBActivity(
        id=6003,
        name="Content Creation",
        description="Writing a blog post in Google Docs.",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_overlap_match_events = [
        E.DBActivityEvent(
            id=15,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_overlap_match_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=16,
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

    # 4) Ambiguous overlap that shares tokens with 'Content Creation' but not exact
    manual_llm_ambiguous_activity = E.DBActivity(
        id=6004,
        name="Content Writing",
        description="Similar but not exact",
        productivity_level=E.ProductivityLevel.PRODUCTIVE,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_llm_ambiguous_events = [
        E.DBActivityEvent(
            id=17,
            event_time=base_time + timedelta(minutes=1),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_llm_ambiguous_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=18,
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

    # 5) Plausible overlap (e.g., Podcast Listening) during content creation
    manual_plausible_podcast_activity = E.DBActivity(
        id=6005,
        name="Podcast Listening",
        description="Listening to a podcast while working",
        productivity_level=E.ProductivityLevel.NEUTRAL,
        last_manual_action_time=None,
        source=E.Source.MANUAL,
    )
    manual_plausible_podcast_events = [
        E.DBActivityEvent(
            id=19,
            event_time=base_time + timedelta(minutes=2),
            event_type=E.ActivityEventType.OPEN,
            aggregation_id=None,
            activity_id=manual_plausible_podcast_activity.id,
            last_manual_action_time=None,
        ),
        E.DBActivityEvent(
            id=20,
            event_time=base_time + timedelta(minutes=4),
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
        name="interrupted_content_creation",
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={1: "llm_content_creation"},
        stitchable_closed_activities=stitchable_closed_activities,
        description="Content creation session interrupted by a video call.",
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
                expected_after_manual_activities={
                    "communication": baml_types.ActivityMetadata(
                        name="Communication",
                        description="Video call in Slack.",
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
            ManualReconciliationCase(
                name="overlap_match",
                manual_activity_specs=manual_overlap_match_specs,
                expected_after_manual_activities={
                    # Only 'communication' remains
                    "communication": baml_types.ActivityMetadata(
                        name="Communication",
                        description="Video call in Slack.",
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
                        description="Video call in Slack.",
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
            ManualReconciliationCase(
                name="plausible_overlap_podcast",
                manual_activity_specs=manual_plausible_podcast_specs,
                expected_after_manual_activities=generated_timeline_activities,
                expected_after_manual_events=generated_timeline_events,
            ),
        ],
        open_auto_activities=[],
    )
