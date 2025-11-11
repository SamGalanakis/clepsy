from datetime import timedelta
from typing import List
from uuid import uuid4

import baml_client.types as baml_types
import clepsy.entities as E

from ..types import TestScenario


def make_llm_stitching_no_match(base_time) -> TestScenario:
    STATIC_ID = uuid4()
    """
    Test scenario where LLM should NOT stitch activities.

    The stitchable activity is "Data Analysis" but the new activity
    is "Email Communication" - completely different activities that
    shouldn't be stitched even though they occurred close together.
    """
    input_logs: List[E.AggregationInputEvent] = [
        # 0:00 → 2:00: Email communication
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Inbox - Gmail",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User reading and responding to emails in Gmail.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Compose Email - Gmail",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User composing an email message.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="Inbox - Gmail",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User managing email inbox.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Gmail",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User working with emails.",
        ),
        # 2:00 → 10:00: Video editing work
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing video in Premiere Pro.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User working on video timeline.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing video content.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User applying effects to video.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing video project.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User working on video editing.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User editing video timeline.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="Project.mp4 - Adobe Premiere",
                app_name="Adobe Premiere Pro",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User working on video project.",
        ),
    ]

    # Previous activity that should NOT be stitched with email
    # "Data Analysis" is completely different from "Email Communication"
    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Data Analysis",
                description="Analyzing dataset and creating visualizations in Python.",
                productivity_level=E.ProductivityLevel.PRODUCTIVE,
                last_manual_action_time=None,
                source=E.Source.AUTO,
            ),
            latest_event=E.DBActivityEvent(
                id=1,
                event_time=base_time - timedelta(minutes=1),
                event_type=E.ActivityEventType.CLOSE,
                aggregation_id=1,
                activity_id=1,
                last_manual_action_time=None,
            ),
            latest_aggregation=E.DBAggregation(
                start_time=base_time - timedelta(minutes=11),
                end_time=base_time - timedelta(minutes=1),
                first_timestamp=base_time - timedelta(minutes=11),
                last_timestamp=base_time - timedelta(minutes=1),
                id=1,
            ),
        )
    ]

    # Generated timeline activities
    generated_timeline_activities = {
        "llm_email": baml_types.ActivityMetadata(
            name="Email Communication",
            description="Reading and responding to emails in Gmail.",
        ),
        "llm_video": baml_types.ActivityMetadata(
            name="Video Editing",
            description="Editing video content in Adobe Premiere Pro.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(
            t="0m0s",
            event_type="open",
            activity_id="llm_email",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="close",
            activity_id="llm_email",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="open",
            activity_id="llm_video",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_video",
        ),
    ]

    # New activities (neither should stitch)
    new_activities = {
        "llm_email": baml_types.ActivityMetadata(
            name="Email Communication",
            description="Reading and responding to emails in Gmail.",
        ),
        "llm_video": baml_types.ActivityMetadata(
            name="Video Editing",
            description="Editing video content in Adobe Premiere Pro.",
        ),
    }

    # Events for new activities
    new_activity_events = [
        baml_types.Event(
            t="0m0s",
            event_type="open",
            activity_id="llm_email",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="close",
            activity_id="llm_email",
        ),
        baml_types.Event(
            t="2m0s",
            event_type="open",
            activity_id="llm_video",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_video",
        ),
    ]

    # Expected output: Data Analysis was already closed, so no events for it
    # The new activities start fresh with no stitching
    expected_aggregator_output = E.AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_activity_events,
        stitched_activities_events=[],  # No stitching!
        unstitched_activities_close_events=[],  # Already closed before window
        activities_to_update=[],  # No updates since nothing was stitched
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time,
        end_time=base_time + timedelta(minutes=10),
    )

    return TestScenario(
        name="llm_stitching_no_match",
        description=(
            "Tests that LLM correctly rejects stitching semantically different activities. "
            "'Data Analysis' should NOT be stitched with 'Email Communication' even though "
            "they occurred close together in time."
        ),
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},  # Nothing stitched
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=base_time - timedelta(minutes=1),
        stitchable_closed_activities=stitchable_closed_activities,
        open_auto_activities=[],
    )
