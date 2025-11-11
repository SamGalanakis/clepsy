from datetime import datetime
import json

from htpy import div, script
from loguru import logger

from clepsy import utils
from clepsy.entities import DBActivitySpecWithTagsAndSessions
from clepsy.modules.activities.json_serializers import (
    db_activity_spec_with_tags_and_sessions_to_json_serializable,
)


def _event_type_value(event) -> str:
    return str(getattr(event.event_type, "value", event.event_type))


def _is_open_event(event) -> bool:
    return _event_type_value(event) in {"open", "start"}


def _is_close_event(event) -> bool:
    return _event_type_value(event) in {"close", "end"}


def _interval_overlaps(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> bool:
    if end <= start:
        return False
    return end > window_start and start < window_end


def _spec_overlaps_window(
    spec: DBActivitySpecWithTagsAndSessions,
    window_start: datetime,
    window_end: datetime,
) -> bool:
    events = sorted(getattr(spec, "events", []), key=lambda e: e.event_time)
    open_time: datetime | None = None

    for event in events:
        if _is_open_event(event):
            open_time = event.event_time
        elif _is_close_event(event) and open_time:
            if _interval_overlaps(
                open_time, event.event_time, window_start, window_end
            ):
                return True
            open_time = None

    if open_time:
        return open_time < window_end

    return False


def build_unified_diagram_payload(
    activity_specs,
    start_time_user_tz,
    end_time_user_tz,
    last_aggregation_end_time_user_tz,
    current_time_user_tz,
):
    windowed_specs = [
        spec
        for spec in activity_specs
        if _spec_overlaps_window(spec, start_time_user_tz, end_time_user_tz)
    ]
    window_seconds = max(
        0, int((end_time_user_tz - start_time_user_tz).total_seconds())
    )

    return json.dumps(
        {
            "activity_specs": [
                db_activity_spec_with_tags_and_sessions_to_json_serializable(s)
                for s in windowed_specs
            ],
            "start_date": utils.datetime_to_iso_8601(start_time_user_tz),
            "end_date": utils.datetime_to_iso_8601(end_time_user_tz),
            "last_aggregation_end_time": utils.datetime_to_iso_8601(
                last_aggregation_end_time_user_tz
            )
            if last_aggregation_end_time_user_tz
            else None,
            "current_time": utils.datetime_to_iso_8601(current_time_user_tz),
            "metadata": {
                "activity_count": len(windowed_specs),
                "original_activity_count": len(activity_specs),
                "window_seconds": window_seconds,
            },
        }
    )


def create_unified_diagram_body(
    activity_specs: list[DBActivitySpecWithTagsAndSessions],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: datetime | None,
    current_time_user_tz: datetime,
):
    unified_payload = build_unified_diagram_payload(
        activity_specs,
        start_time_user_tz,
        end_time_user_tz,
        last_aggregation_end_time_user_tz,
        current_time_user_tz,
    )

    return div(
        id="unified-diagrams-container",
        # Removed fixed h-[1000px] so fullscreen can expand; use h-full + min height baseline
        class_="relative w-full h-full min-h-[600px] overflow-auto p-4 sm:p-6",
        x_init="window.initUnifiedDiagramFromJson($el.dataset.unified)",
        **{"data-unified": unified_payload},
    )


def create_unified_diagram_container(
    activity_specs: list[DBActivitySpecWithTagsAndSessions],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: datetime | None,
    current_time_user_tz: datetime,
):
    logger.info(
        "Creating unified diagram container with {} activity specs",
        len(activity_specs),
    )

    body = create_unified_diagram_body(
        activity_specs,
        start_time_user_tz,
        end_time_user_tz,
        last_aggregation_end_time_user_tz,
        current_time_user_tz,
    )

    return div(
        id="unified-diagrams-wrapper",
        **{
            "hx-get": "/s/update-unified-diagram",
            "hx-trigger": "update_unified_diagram from:body",
            "hx-swap": "innerHTML",  # only swap the body
            "x-bind:hx-vals": (
                "JSON.stringify({reference_date: reference_date, "
                "view_mode: view_mode, offset: offset, "
                "selected_tag_ids: JSON.stringify(selected_tag_ids)})"
            ),
        },
        # Note: fullscreen resizing handled in JS; wrapper must stretch to screen
        class_="h-full w-full",
    )[
        script(src="/static/custom_scripts/utils.js"),
        script(src="/static/custom_scripts/chart_utils.js"),
        script(src="/static/custom_scripts/unified_diagram.js"),
        body,  # ← initial graphs / empty-state
    ]
