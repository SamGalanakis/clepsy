from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_coding_then_afk(base_time) -> TestScenario:
    # Screenshot events every 30 seconds within the same app; no logs after 5:00 to indicate AFK
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
    ]

    activities = {
        "python_development": baml_types.ActivityMetadata(
            name="Python Development",
            description="Working on Python code in VS Code.",
        )
    }

    events = [
        baml_types.Event(
            activity_id="python_development",
            event_type="open",
            t="0m0s",
        ),
        baml_types.Event(
            activity_id="python_development",
            event_type="close",
            t="4m35s",
        ),
    ]
    events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    expected_aggregator_output = AggregatorCoreOutput(
        new_activities=activities,
        activities_to_update=[],
        new_activity_events=events,
        stitched_activities_events=[],
        unstitched_activities_close_events=[],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    return TestScenario(
        name="coding_then_afk",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Coding session followed by an AFK period.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
