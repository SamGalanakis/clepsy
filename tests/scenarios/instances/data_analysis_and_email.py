from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E

from ..types import TestScenario


def make_data_analysis_and_email(base_time) -> TestScenario:
    input_logs: List[E.AggregationInputEvent] = [
        # Jupyter (Chrome): 0:00 → 4:55 at 30s cadence, then 5s gap before switch
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time,
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=30),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=2, seconds=30),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=3, seconds=30),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=30),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User analyzing sales data in a Jupyter Notebook.",
        ),
        # Outlook: 5:00 → 9:55 at 30s cadence
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=6, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=7, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=8, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=30),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="Inbox - Outlook",
                app_name="Microsoft Outlook",
                bbox=E.Bbox(left=100, top=50, width=1200, height=800),
            ),
            llm_description="User checking and responding to emails in Outlook.",
        ),
        # Return to Jupyter at 10:00
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10),
            active_window=E.WindowInfo(
                title="Sales_Data_Analysis.ipynb - Jupyter Notebook",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="User returned to analyzing sales data in the Jupyter Notebook.",
        ),
    ]

    stitchable_closed_activities = [
        E.DBActivityWithLatestEvent(
            activity=E.DBActivity(
                id=1,
                name="Data Analysis",
                description="Analyzing data in a Jupyter Notebook.",
                productivity_level=E.ProductivityLevel.PRODUCTIVE,
                last_manual_action_time=None,
                source=E.Source.AUTO,
            ),
            latest_event=E.DBActivityEvent(
                id=1,
                event_time=base_time - timedelta(minutes=4),
                event_type=E.ActivityEventType.CLOSE,
                aggregation_id=1,
                activity_id=1,
                last_manual_action_time=None,
            ),
            latest_aggregation=E.DBAggregation(
                start_time=base_time - timedelta(minutes=14),
                end_time=base_time - timedelta(minutes=4),
                first_timestamp=base_time - timedelta(minutes=14),
                last_timestamp=base_time - timedelta(minutes=4),
                id=1,
            ),
        )
    ]

    generated_timeline_activities = {
        "llm_data_analysis": baml_types.ActivityMetadata(
            name="Data Analysis",
            description="Analyzing data in a Jupyter Notebook.",
        ),
        "email_communication": baml_types.ActivityMetadata(
            name="Email Communication",
            description="Checking and responding to emails in Outlook.",
        ),
    }

    generated_timeline_events = [
        baml_types.Event(activity_id="llm_data_analysis", event_type="open", t="0m0s"),
        baml_types.Event(activity_id="llm_data_analysis", event_type="close", t="5m0s"),
        baml_types.Event(
            activity_id="email_communication", event_type="open", t="5m0s"
        ),
        baml_types.Event(
            activity_id="email_communication", event_type="close", t="10m0s"
        ),
        baml_types.Event(activity_id="llm_data_analysis", event_type="open", t="10m0s"),
    ]
    generated_timeline_events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    new_activities = {
        "email_communication": baml_types.ActivityMetadata(
            name="Email Communication",
            description="Checking and responding to emails in Outlook.",
        ),
    }

    new_events = [
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
                    "name": "Data Analysis",
                    "description": "Analyzing data in a Jupyter Notebook.",
                },
            )
        ],
    )

    aggregation_time_span = E.TimeSpan(
        start_time=base_time, end_time=base_time + timedelta(minutes=10)
    )
    return TestScenario(
        name="data_analysis_and_email",
        input_logs=input_logs,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={1: "llm_data_analysis"},
        stitchable_closed_activities=stitchable_closed_activities,
        description="Data analysis session interrupted by email.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        open_auto_activities=[],
    )
