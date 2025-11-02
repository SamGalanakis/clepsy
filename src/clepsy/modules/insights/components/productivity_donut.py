from __future__ import annotations

from datetime import datetime
import json
from typing import List, Optional

from htpy import div

from clepsy import utils
from clepsy.entities import DBActivitySpecWithTags, ViewMode
from clepsy.modules.activities.json_serializers import (
    db_activity_spec_with_tags_to_json_serializable,
)


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


def create_productivity_donut_body(
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
        id="productivity_donut_chart",
        class_="relative w-full h-auto min-h-[300px] overflow-visible",
        x_init="window.initInsightsProductivityDonutFromJson($el.dataset.productivity)",
        **{"data-productivity": payload},
    )
