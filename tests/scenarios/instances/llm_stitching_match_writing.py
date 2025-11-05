from datetime import timedelta
from typing import List

import baml_client.types as baml_types
import clepsy.entities as E

from ..types import TestScenario


def make_llm_stitching_match_writing(base_time) -> TestScenario:
    """
    Test scenario that requires LLM-based stitching for writing activities.

    The stitchable activity is "Writing Article" but the new activity
    is "Composing Blog Content" - semantically the same but worded differently.
    """
    input_logs: List[E.AggregationInputEvent] = [
        # 0:00 → 3:00: Writing/composing content
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Draft Post - WordPress",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User composing blog post in WordPress editor.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Draft Post - WordPress",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User typing blog content.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="New Post - WordPress",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing blog post content.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Draft - WordPress",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User composing article text.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="WordPress Editor",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User creating blog content.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="WordPress",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User writing post content.",
        ),
        # 3:00 → 10:00: Social media browsing
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="Twitter",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User browsing Twitter feed.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="Twitter",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User scrolling through social media.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="Facebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User browsing Facebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="LinkedIn",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User viewing LinkedIn feed.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="Twitter",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User browsing social media.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="Instagram",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User scrolling Instagram.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="Twitter",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User browsing social media feed.",
        ),
    ]

    # Previous activity that should be stitched with writing/composing activity
    # "Writing Article" vs "Composing Blog Content" - semantically identical
    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Writing Article",
                description="Creating written content for blog publication.",
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
        "llm_writing": baml_types.ActivityMetadata(
            name="Composing Blog Content",
            description="Writing and editing blog post text in WordPress.",
        ),
        "llm_social": baml_types.ActivityMetadata(
            name="Social Media Browsing",
            description="Scrolling through various social media platforms.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(
            t="0m0s",
            event_type="open",
            activity_id="llm_writing",
        ),
        baml_types.Event(
            t="3m0s",
            event_type="close",
            activity_id="llm_writing",
        ),
        baml_types.Event(
            t="3m0s",
            event_type="open",
            activity_id="llm_social",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_social",
        ),
    ]

    # New activities (not stitched)
    new_activities = {
        "llm_social": baml_types.ActivityMetadata(
            name="Social Media Browsing",
            description="Scrolling through various social media platforms.",
        ),
    }

    # Events for new activities
    new_activity_events = [
        baml_types.Event(
            t="3m0s",
            event_type="open",
            activity_id="llm_social",
        ),
        baml_types.Event(
            t="10m0s",
            event_type="close",
            activity_id="llm_social",
        ),
    ]

    # Events for stitched activities
    stitched_activities_events = [
        E.NewActivityEventExistingActivity(
            event_time=base_time,
            event_type=E.ActivityEventType.OPEN,
            activity_id=1,
        ),
        E.NewActivityEventExistingActivity(
            event_time=base_time + timedelta(minutes=3),
            event_type=E.ActivityEventType.CLOSE,
            activity_id=1,
        ),
    ]

    # Expected output: Writing Article should be stitched with Composing Blog Content
    expected_aggregator_output = E.AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_activity_events,
        stitched_activities_events=stitched_activities_events,
        unstitched_activities_close_events=[],
        activities_to_update=[
            # LLM should merge appropriately
            (
                1,
                {
                    "name": "Writing Article",
                    "description": "Creating written content for blog publication.",
                },
            ),
        ],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time,
        end_time=base_time + timedelta(minutes=10),
    )

    return TestScenario(
        name="llm_stitching_match_writing",
        description=(
            "Tests LLM-based stitching for semantically identical activities with different wording. "
            "'Writing Article' should be stitched with 'Composing Blog Content' "
            "as they describe the same activity."
        ),
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={1: "llm_writing"},
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=base_time - timedelta(minutes=1),
        stitchable_closed_activities=stitchable_closed_activities,
        open_auto_activities=[],
    )
