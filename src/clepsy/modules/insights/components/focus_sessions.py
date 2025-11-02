from __future__ import annotations

from datetime import datetime
import json
from typing import List, Optional

from htpy import div, input as htpy_input

from clepsy import utils
from clepsy.entities import DBActivitySpecWithTags, ViewMode
from clepsy.modules.activities.json_serializers import (
    db_activity_spec_with_tags_to_json_serializable,
)


# ---------------------------------------------------------------------------
# Payload builder (shared across calendar / histogram / stats)
# ---------------------------------------------------------------------------


def _build_payload(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    return json.dumps(
        {
            "activity_specs": [
                db_activity_spec_with_tags_to_json_serializable(s)
                for s in activity_specs
            ],
            "start_date": utils.datetime_to_iso_8601(start_time_user_tz),
            "end_date": utils.datetime_to_iso_8601(end_time_user_tz),
            "last_aggregation_end_time": utils.datetime_to_iso_8601(
                last_aggregation_end_time_user_tz
            )
            if last_aggregation_end_time_user_tz
            else None,
            "current_time": utils.datetime_to_iso_8601(current_time_user_tz),
            "view_mode": view_mode.value,
        }
    )


# ---------------------------------------------------------------------------
# Leaf bodies (HTMX swap targets)
# ---------------------------------------------------------------------------


def create_focus_sessions_calendar_body(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    payload = _build_payload(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus_sessions_calendar_chart",
        class_="relative w-full h-auto min-h-[340px] overflow-visible",
        x_init="window.initInsightsFocusSessionsCalendarFromJson($el.dataset.focus)",
        **{"data-focus": payload},
    )


def create_focus_sessions_histogram_body(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    payload = _build_payload(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus_sessions_histogram_chart",
        class_="relative w-full h-auto min-h-[340px] overflow-visible",
        x_init="window.initInsightsFocusSessionsHistogramFromJson($el.dataset.focus)",
        **{"data-focus": payload},
    )


def create_focus_sessions_stats_body(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    payload = _build_payload(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus_sessions_stats_panel",
        class_="relative w-full h-auto min-h-[54px] overflow-visible",
        x_init="window.initInsightsFocusSessionsStatsFromJson($el.dataset.focus)",
        **{"data-focus": payload},
    )


# ---------------------------------------------------------------------------
# Containers (HTMX wrappers around bodies)
# ---------------------------------------------------------------------------


def _hx_common():  # keep hx-vals expression aligned across containers
    return "JSON.stringify({reference_date: reference_date, view_mode: view_mode, offset: offset, selected_tag_ids: JSON.stringify(selected_tag_ids)})"


def create_focus_sessions_calendar_container(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    body = create_focus_sessions_calendar_body(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus-sessions-calendar-wrapper",
        class_=(
            "focus-sessions-subchart w-full flex-1 basis-2/3 min-w-[480px] max-w-[1600px]"
        ),
        **{
            "hx-get": "/s/insights/update-focus-sessions-calendar",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#focus_sessions_calendar_chart",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": _hx_common(),
        },
    )[body]


def create_focus_sessions_histogram_container(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    body = create_focus_sessions_histogram_body(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus-sessions-histogram-wrapper",
        class_=(
            "focus-sessions-subchart w-full flex-1 basis-1/3 min-w-[320px] max-w-[640px]"
        ),
        **{
            "hx-get": "/s/insights/update-focus-sessions-histogram",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#focus_sessions_histogram_chart",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": _hx_common(),
        },
    )[body]


def create_focus_sessions_stats_container(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    body = create_focus_sessions_stats_body(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    return div(
        id="focus-sessions-stats-wrapper",
        class_=(
            "focus-sessions-stats flex flex-row flex-wrap gap-8 items-center text-xs px-0 py-0"
        ),
        **{
            "hx-get": "/s/insights/update-focus-sessions-stats",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#focus_sessions_stats_panel",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": _hx_common(),
        },
    )[body]


# ---------------------------------------------------------------------------
# Unified Section (title centered, stats & settings as peers)
# ---------------------------------------------------------------------------


def _settings_inputs():
    # Inputs share class focus-session-setting so JS can re-read values.
    return [
        div(class_="flex flex-col")[
            div(class_="text-[10px] uppercase tracking-wide opacity-60 mb-0.5")[
                "Min Duration (min)"
            ],
            htpy_input(
                id="fs-min-duration",
                type="number",
                min="1",
                step="1",
                value="20",
                class_="focus-session-setting input input-xs bg-base-900 w-20",
            ),
        ],
        div(class_="flex flex-col")[
            div(class_="text-[10px] uppercase tracking-wide opacity-60 mb-0.5")[
                "Productive Threshold"
            ],
            htpy_input(
                id="fs-prod-threshold",
                type="number",
                min="0",
                max="1",
                step="0.05",
                value="0.8",
                class_="focus-session-setting input input-xs bg-base-900 w-20",
            ),
        ],
        div(class_="flex flex-col")[
            div(class_="text-[10px] uppercase tracking-wide opacity-60 mb-0.5")[
                "Max Single Interruption (s)"
            ],
            htpy_input(
                id="fs-max-interruption",
                type="number",
                min="10",
                step="10",
                value="120",
                class_="focus-session-setting input input-xs bg-base-900 w-24",
            ),
        ],
        div(class_="flex flex-col")[
            div(class_="text-[10px] uppercase tracking-wide opacity-60 mb-0.5")[
                "Max Disruption (%)"
            ],
            htpy_input(
                id="fs-max-disruption",
                type="number",
                min="0",
                max="1",
                step="0.01",
                value="0.10",
                class_="focus-session-setting input input-xs bg-base-900 w-20",
            ),
        ],
    ]


def create_focus_sessions_section(
    *,
    activity_specs: List[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: Optional[datetime],
    current_time_user_tz: datetime,
    view_mode: ViewMode,
):
    stats = create_focus_sessions_stats_container(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    calendar = create_focus_sessions_calendar_container(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )
    histogram = create_focus_sessions_histogram_container(
        activity_specs=activity_specs,
        start_time_user_tz=start_time_user_tz,
        end_time_user_tz=end_time_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
        view_mode=view_mode,
    )

    settings_panel = div(
        id="focus-sessions-settings",
        class_="flex flex-row flex-wrap gap-4 items-center text-xs",
    )[_settings_inputs()]

    # Use CSS grid to center title irrespective of dynamic widths of stats/settings.
    top_bar = div(
        class_=(
            "grid gap-6 items-center px-4 py-3 rounded-md border border-base-300/40 "
            "bg-base-950/40 w-full "
            "grid-cols-[1fr_auto_1fr]"
        )
    )[
        div(class_="flex flex-row flex-wrap gap-8 items-center justify-start")[stats],
        div(class_="text-base font-semibold tracking-tight text-center px-4")[
            "Focus Sessions"
        ],
        div(class_="flex flex-row flex-wrap gap-5 justify-end items-center")[
            settings_panel
        ],
    ]

    charts_row = div(
        class_="flex flex-wrap xl:flex-nowrap gap-4 md:gap-6 w-full items-stretch"
    )[
        calendar,
        histogram,
    ]

    return div(
        id="focus-sessions-section",
        class_="insight-graph w-full flex flex-col gap-5 focus-sessions-section",
    )[
        top_bar,
        charts_row,
    ]
