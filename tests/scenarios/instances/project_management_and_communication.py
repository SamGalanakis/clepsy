from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_project_management_and_communication(base_time) -> TestScenario:
    input_logs: List[E.AggregationInputEvent] = [
        # Asana in Chrome: 0:00 → 4:55 at 30s cadence, then a 5s gap before switch
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="Project Plan - Asana",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User updating the project plan in Asana.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User responding to project-related emails in Outlook.",
        ),
        # Teams: open at 10:00
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10),
            active_window=E.WindowInfo(
                title="Project Chat - Microsoft Teams",
                app_name="Microsoft Teams",
                bbox=E.Bbox(left=150, top=75, width=1100, height=750),
            ),
            llm_description="User coordinating with team in Microsoft Teams chat.",
        ),
        # Teams: open at 10:00
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10),
            active_window=E.WindowInfo(
                title="Project Chat - Microsoft Teams",
                app_name="Microsoft Teams",
                bbox=E.Bbox(left=150, top=75, width=1100, height=700),
            ),
            llm_description="User discussing project details in Microsoft Teams.",
        ),
    ]

    activities = {
        "project_planning": baml_types.ActivityMetadata(
            name="Project Planning",
            description="Updating the project plan in Asana.",
        ),
        "email_communication": baml_types.ActivityMetadata(
            name="Email Communication",
            description="Responding to project-related emails in Outlook.",
        ),
        "team_chat": baml_types.ActivityMetadata(
            name="Team Chat",
            description="Discussing project details in Microsoft Teams.",
        ),
    }

    events = [
        baml_types.Event(
            activity_id="project_planning",
            event_type="open",
            t="0m0s",
        ),
        baml_types.Event(
            activity_id="project_planning",
            event_type="close",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="email_communication",
            event_type="open",
            t="5m0s",
        ),
        baml_types.Event(
            activity_id="email_communication",
            event_type="close",
            t="10m0s",
        ),
        baml_types.Event(
            activity_id="team_chat",
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
        name="project_management_and_communication",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Project management session with communication.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
