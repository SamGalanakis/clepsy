from __future__ import annotations

from datetime import datetime
import json

from htpy import div, script

from clepsy import utils
from clepsy.entities import DBActivitySpecWithTags
from clepsy.modules.activities.json_serializers import (
    db_activity_spec_with_tags_to_json_serializable,
)


def build_insights_payload(
    activity_specs: list[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: datetime | None,
    current_time_user_tz: datetime,
) -> str:
    unique_tag_ids = {
        tag.id for spec in activity_specs for tag in getattr(spec, "tags", [])
    }
    total_window_seconds = max(
        0,
        int((end_time_user_tz - start_time_user_tz).total_seconds()),
    )

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
            "metadata": {
                "activity_count": len(activity_specs),
                "tag_count": len(unique_tag_ids),
                "window_seconds": total_window_seconds,
            },
        }
    )


def create_time_spent_per_tag_body(
    activity_specs: list[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: datetime | None,
    current_time_user_tz: datetime,
):
    payload = build_insights_payload(
        activity_specs,
        start_time_user_tz,
        end_time_user_tz,
        last_aggregation_end_time_user_tz,
        current_time_user_tz,
    )

    return div(
        id="time-spent-per-tag",
        # Allow vertical expansion but prevent horizontal overflow from affecting flex width.
        class_="relative w-full h-auto min-h-[320px] overflow-x-hidden overflow-y-visible",
        x_init="window.initInsightsTimeSpentPerTagFromJson($el.dataset.insights)",
        **{"data-insights": payload},
    )


def create_time_spent_per_tag_container(
    activity_specs: list[DBActivitySpecWithTags],
    start_time_user_tz: datetime,
    end_time_user_tz: datetime,
    last_aggregation_end_time_user_tz: datetime | None,
    current_time_user_tz: datetime,
):
    """HTMX-enabled container that refreshes on 'update_insights_diagrams' events."""
    body = create_time_spent_per_tag_body(
        activity_specs,
        start_time_user_tz,
        end_time_user_tz,
        last_aggregation_end_time_user_tz,
        current_time_user_tz,
    )

    # Wrapper classes:
    # - w-full so it spans its grid/flex cell
    # - "insight-graph" hook for potential future shared styling
    return div(
        id="time-spent-per-tag-wrapper",
        class_="insight-graph w-full min-w-0",
        **{
            "hx-get": "/s/insights/update-time-spent-per-tag",
            "hx-trigger": "update_insights_diagrams from:body",
            "hx-target": "#time-spent-per-tag",
            "hx-swap": "outerHTML",
            "x-bind:hx-vals": (
                "JSON.stringify({reference_date: reference_date, "
                "view_mode: view_mode, offset: offset, "
                "selected_tag_ids: JSON.stringify(selected_tag_ids)})"
            ),
        },
    )[
        script(src="/static/custom_scripts/utils.js"),
        script(src="/static/custom_scripts/chart_utils.js"),
        script(src="/static/custom_scripts/insights_time_spent_per_tag.js"),
        body,
    ]
