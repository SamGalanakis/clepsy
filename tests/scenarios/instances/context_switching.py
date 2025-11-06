from datetime import timedelta
from typing import List
from uuid import uuid4

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_context_switching(base_time) -> TestScenario:
    # 30s cadence within an app; switch at 5:00 (VSCode → Chrome) and 10:00 (Chrome → VSCode)
    STATIC_ID = uuid4()
    input_logs: List[E.AggregationInputEvent] = [
        # Backend dev in VSCode (0:00 → 4:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="backend.py - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Working on backend API endpoints in VS Code (SQLAlchemy integration).",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="backend.py - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Editing backend API code in backend.py.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="backend.py - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Continuing backend implementation in VS Code.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="backend.py - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Finalizing changes before switching contexts.",
        ),
        # React research (5:00 → 9:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="React Docs - Components and Props",
                app_name="Google Chrome",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Researching React components and props in Chrome.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="React Docs - State and Lifecycle",
                app_name="Google Chrome",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Reading React state and lifecycle docs.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="React Docs - Hooks Overview",
                app_name="Google Chrome",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="Reviewing React hooks overview.",
        ),
        # Frontend dev in VSCode (10:00)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="frontend.js - Visual Studio Code",
                app_name="Visual Studio Code",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Building React components in VS Code.",
        ),
    ]

    activities = {
        "backend_development": baml_types.ActivityMetadata(
            name="Backend Development",
            description="Working on backend API endpoints in VS Code.",
        ),
        "frontend_development": baml_types.ActivityMetadata(
            name="Frontend Development",
            description="Building React components in VS Code.",
        ),
        "react_research": baml_types.ActivityMetadata(
            name="React Research",
            description="Researching React documentation in Chrome.",
        ),
    }

    events = [
        baml_types.Event(
            activity_id="backend_development",
            event_type="open",
            t="0m0s",
        ),
        baml_types.Event(
            activity_id="backend_development",
            event_type="close",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="react_research",
            event_type="open",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="react_research",
            event_type="close",
            t="10m0s",
        ),
        baml_types.Event(
            activity_id="frontend_development",
            event_type="open",
            t="10m0s",
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
        name="context_switching",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Frequent context switching between backend, frontend, and research",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
