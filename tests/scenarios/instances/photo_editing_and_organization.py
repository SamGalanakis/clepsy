from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_photo_editing_and_organization(base_time) -> TestScenario:
    # Screenshot cadence: 30s within app; 5s at switches (Photoshop → Explorer at 5:00, Explorer → Photoshop at 10:00)
    input_logs: List[E.AggregationInputEvent] = [
        # Photoshop editing (0:00 → 4:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="photo.jpg - Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing photo.jpg in Adobe Photoshop.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="photo.jpg - Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Adjusting layers and filters in Photoshop.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="photo.jpg - Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Cropping and color correcting in Photoshop.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="photo.jpg - Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Final tweaks before organizing files.",
        ),
        # File Explorer organization (5:00 → 9:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="Pictures",
                app_name="File Explorer",
                is_active=True,
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Organizing photos in File Explorer.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="Pictures",
                app_name="File Explorer",
                is_active=True,
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Renaming and moving files in File Explorer.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="Pictures",
                app_name="File Explorer",
                is_active=True,
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Final folder organization in File Explorer.",
        ),
        # Back to Photoshop (10:00)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="photo2.jpg - Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing photo2.jpg in Adobe Photoshop.",
        ),
    ]

    # Split activities by app; use a new activity for the second Photoshop session
    activities = {
        "photo_editing": baml_types.ActivityMetadata(
            name="Photo Editing",
            description="Editing photos in Adobe Photoshop.",
        ),
        "photo_organization": baml_types.ActivityMetadata(
            name="Photo Organization",
            description="Organizing photos in File Explorer.",
        ),
        "photo_editing_second_session": baml_types.ActivityMetadata(
            name="Photo Editing (Second Session)",
            description="Editing another photo in Adobe Photoshop.",
        ),
    }

    events = [
        baml_types.Event(activity_id="photo_editing", event_type="open", t="0m0s"),
        baml_types.Event(activity_id="photo_editing", event_type="close", t="5m0s"),
        baml_types.Event(activity_id="photo_organization", event_type="open", t="5m0s"),
        baml_types.Event(
            activity_id="photo_organization", event_type="close", t="10m0s"
        ),
        baml_types.Event(
            activity_id="photo_editing_second_session", event_type="open", t="10m0s"
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
    return TestScenario(
        name="photo_editing_and_organization",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Photo editing, then file organization, then editing again; frequent screenshots.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
