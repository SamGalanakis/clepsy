from datetime import timedelta
from typing import List
from uuid import uuid4

import baml_client.types as baml_types
from clepsy import utils
import clepsy.entities as E
from clepsy.entities import AggregatorCoreOutput

from ..types import TestScenario


def make_online_shopping_with_research(base_time) -> TestScenario:
    STATIC_ID = uuid4()
    # Screenshot cadence: 30s within domain; 5s at domain switches (Amazon → CNET at 5:00, CNET → Amazon at 10:00)
    input_logs: List[E.AggregationInputEvent] = [
        # Amazon browsing (0:00 → 4:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=0),
            active_window=E.WindowInfo(
                title="Laptops - Amazon.com",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Browsing laptops on Amazon.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(seconds=30),
            active_window=E.WindowInfo(
                title="Gaming Laptops - Amazon.com",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Viewing gaming laptops category on Amazon.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=1, seconds=0),
            active_window=E.WindowInfo(
                title="Lenovo Legion - Amazon.com",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Inspecting a specific laptop product page on Amazon.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=4, seconds=55),
            active_window=E.WindowInfo(
                title="Compare - Amazon.com",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Comparing laptop options on Amazon.",
        ),
        # CNET research (5:00 → 9:55)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=0),
            active_window=E.WindowInfo(
                title="Best Laptops 2025 - CNET",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reading CNET's Best Laptops 2025 article.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=5, seconds=30),
            active_window=E.WindowInfo(
                title="CNET - Laptop Buying Guide",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Reviewing laptop buying guide on CNET.",
        ),
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=9, seconds=55),
            active_window=E.WindowInfo(
                title="CNET - Editor's Picks",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Checking editor's picks on CNET.",
        ),
        # Return to Amazon (10:00)
        E.ProcessedDesktopCheckScreenshotEventVLM(
            id=STATIC_ID,
            timestamp=base_time + timedelta(minutes=10, seconds=0),
            active_window=E.WindowInfo(
                title="Shopping Cart - Amazon.com",
                app_name="Google Chrome",
                bbox=E.Bbox(left=50, top=25, width=1400, height=900),
            ),
            llm_description="Returned to Amazon to proceed with checkout.",
        ),
    ]

    activities = {
        "online_shopping": baml_types.ActivityMetadata(
            name="Online Shopping",
            description="Shopping for a laptop on Amazon.",
        ),
        "product_research": baml_types.ActivityMetadata(
            name="Product Research",
            description="Researching laptops on CNET.",
        ),
        # Separate activity for resumed Amazon session to comply with max pause constraints
        "online_shopping_checkout": baml_types.ActivityMetadata(
            name="Online Shopping Checkout",
            description="Returning to Amazon to proceed with checkout.",
        ),
    }

    events = [
        # Amazon session
        baml_types.Event(activity_id="online_shopping", event_type="open", t="0m0s"),
        baml_types.Event(activity_id="online_shopping", event_type="close", t="5m0s"),
        # CNET research
        baml_types.Event(activity_id="product_research", event_type="open", t="5m0s"),
        baml_types.Event(activity_id="product_research", event_type="close", t="10m0s"),
        # Return to Amazon at boundary (new activity continues)
        baml_types.Event(
            activity_id="online_shopping_checkout", event_type="open", t="10m0s"
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
        name="online_shopping_with_research",
        input_logs=input_logs,
        generated_timeline_activities=activities,
        generated_timeline_events=events,
        expected_aggregator_output=expected_aggregator_output,
        stitchable_activity_to_llm_id={},
        description="Online shopping with research (Amazon → CNET → Amazon) using frequent screenshots.",
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=aggregation_time_span.start_time,
        stitchable_closed_activities=[],
        open_auto_activities=[],
    )
