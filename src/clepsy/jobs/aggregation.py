from __future__ import annotations
# ruff: noqa: I001

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from dateutil.parser import isoparse
from loguru import logger

import clepsy.entities as E
from clepsy.aggregator_worker import do_aggregation, do_empty_aggregation
from clepsy.config import config
from clepsy.entities import TimeSpan
from clepsy.infra.streams import xrange_source_events


def current_window(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(tz=timezone.utc)
    interval = config.aggregation_interval
    start = now - timedelta(seconds=now.timestamp() % interval.total_seconds())
    end = start + interval
    return start, end


def aggregate_window(start_iso: str | None = None, end_iso: str | None = None) -> None:
    """RQ Job: aggregate a specific time window.

    - If start/end are not provided, compute the current window.
    - This function intentionally remains synchronous so it can be used as an RQ job.
    - It delegates to do_aggregation within an asyncio loop under the hood where needed.
    """
    start: datetime
    end: datetime
    if start_iso and end_iso:
        start = isoparse(start_iso)
        end = isoparse(end_iso)
    else:
        start, end = current_window()

    logger.info("[RQ] aggregate_window start={} end={}", start, end)

    # Query durable source events and run the existing aggregation pipeline.

    def map_source_event(row) -> E.AggregationInputEvent | None:
        etype = row["event_type"]
        payload = row["payload_json"]
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse payload_json for source_event id={} type={}",
                row.get("id"),
                etype,
            )
            return None

        ts = isoparse(data.get("timestamp"))

        match etype:
            case "desktop_screenshot_ocr":
                return E.ProcessedDesktopCheckScreenshotEventOCR(
                    image_text=data.get("image_text", ""),
                    active_window=E.WindowInfo(
                        title=data["active_window"]["title"],
                        app_name=data["active_window"]["app_name"],
                        is_active=data["active_window"].get("is_active", True),
                        bbox=E.Bbox(
                            left=data["active_window"]["bbox"]["left"],
                            top=data["active_window"]["bbox"]["top"],
                            width=data["active_window"]["bbox"]["width"],
                            height=data["active_window"]["bbox"]["height"],
                        ),
                    ),
                    timestamp=ts,
                    image_text_post_processed_by_llm=data.get(
                        "image_text_post_processed_by_llm", False
                    ),
                )
            case "desktop_screenshot_vlm":
                return E.ProcessedDesktopCheckScreenshotEventVLM(
                    llm_description=data.get("llm_description", ""),
                    active_window=E.WindowInfo(
                        title=data["active_window"]["title"],
                        app_name=data["active_window"]["app_name"],
                        is_active=data["active_window"].get("is_active", True),
                        bbox=E.Bbox(
                            left=data["active_window"]["bbox"]["left"],
                            top=data["active_window"]["bbox"]["top"],
                            width=data["active_window"]["bbox"]["width"],
                            height=data["active_window"]["bbox"]["height"],
                        ),
                    ),
                    timestamp=ts,
                )
            case "mobile_app_usage":
                return E.MobileAppUsageEvent(
                    app_label=data.get("app_label", ""),
                    package_name=data.get("package_name", ""),
                    activity_name=data.get("activity_name", ""),
                    media_metadata=data.get("media_metadata"),
                    notification_text=data.get("notification_text"),
                    timestamp=ts,
                )
            case _:
                logger.warning("Unknown source_event type encountered: {}", etype)
                return None

    async def run_aggregation():
        rows = await asyncio.to_thread(xrange_source_events, start=start, end=end)

        window_span = TimeSpan(start_time=start, end_time=end)
        if not rows:
            logger.info("[RQ] No source events in window; running empty aggregation")
            await do_empty_aggregation()
            return

        input_logs: list[E.AggregationInputEvent] = []
        for row in rows:
            mapped = map_source_event(row)
            if mapped is not None:
                input_logs.append(mapped)

        if not input_logs:
            logger.info(
                "[RQ] No mappable source events in window; running empty aggregation"
            )
            await do_empty_aggregation()
            return

        await do_aggregation(input_logs=input_logs, aggregation_time_span=window_span)

    asyncio.run(run_aggregation())
