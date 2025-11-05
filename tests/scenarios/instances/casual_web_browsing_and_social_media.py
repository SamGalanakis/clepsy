from datetime import timedelta
from typing import List

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_casual_web_browsing_and_social_media(base_time) -> TestScenario:
    # Screenshot cadence: 30s within a domain, 5s at domain switches (BBC → Facebook at 5:00, Facebook → YouTube at 10:00)
    input_logs: List[E.AggregationInputEvent] = [
        # BBC News (0:00 → 4:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="BBC News - Home",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reading news on BBC News homepage.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="BBC News - World",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reading a world news article on BBC News.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="BBC News - Politics",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Scrolling through politics coverage on BBC News.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="BBC News - Technology",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Checking technology headlines on BBC News.",
        ),
        # Facebook (5:00 → 9:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="Facebook - News Feed",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Browsing Facebook news feed.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="Facebook - Notifications",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Checking notifications on Facebook.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="Facebook - Messages",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reading messages on Facebook.",
        ),
        # YouTube (10:00)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="YouTube - Tech Reviews",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Watching a tech review video on YouTube.",
        ),
    ]

    # Activities split by domain family changes (BBC → Facebook → YouTube)
    activities = {
        "news_browsing": baml_types.ActivityMetadata(
            name="News Browsing",
            description="Reading news articles on BBC.",
        ),
        "social_media": baml_types.ActivityMetadata(
            name="Social Media",
            description="Browsing Facebook feed and notifications.",
        ),
        "youtube_watching": baml_types.ActivityMetadata(
            name="YouTube Watching",
            description="Watching videos on YouTube.",
        ),
    }

    events = [
        # BBC News session
        baml_types.Event(activity_id="news_browsing", event_type="open", t="0m0s"),
        baml_types.Event(activity_id="news_browsing", event_type="close", t="5m0s"),
        # Facebook session
        baml_types.Event(activity_id="social_media", event_type="open", t="5m0s"),
        baml_types.Event(activity_id="social_media", event_type="close", t="10m0s"),
        # YouTube session continues beyond aggregation (no close at boundary)
        baml_types.Event(activity_id="youtube_watching", event_type="open", t="10m0s"),
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
        name="casual_web_browsing_and_social_media",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Casual web browsing across BBC, Facebook, then YouTube, with frequent screenshots.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
