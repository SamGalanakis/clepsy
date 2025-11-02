from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import HTMLResponse

from clepsy import utils
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    select_last_aggregation,
    select_specs_with_tags_and_sessions_in_time_range,
)
from clepsy.entities import (
    DBActivitySpecWithTagsAndSessions,
    UserSettings,
    ViewMode,
)
from clepsy.frontend.components import create_base_page

# Import create_home_page from pages and create_timeline_content from home_components
from clepsy.modules.home.page import create_home_page

from .components import (
    create_unified_diagram_body,
)


router = APIRouter()


def filter_activities_by_tags(
    activities: list[DBActivitySpecWithTagsAndSessions], selected_tag_ids: list[int]
) -> list[DBActivitySpecWithTagsAndSessions]:
    if not selected_tag_ids:
        return activities

    no_tag_selected = -1 in selected_tag_ids
    filtered_activities = [
        activity
        for activity in activities
        if any(tag.id in selected_tag_ids for tag in activity.tags)
        or (no_tag_selected and not activity.tags)
    ]
    return filtered_activities


@router.get("/")
async def index_page(
    request: Request,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        is_htmx = request.state.is_htmx
        async with get_db_connection(include_uuid_func=False) as conn:
            home_page_content = await create_home_page(
                conn=conn, user_settings=user_settings
            )

        if is_htmx:
            # If this is an HTMX request, return the content directly
            return HTMLResponse(content=home_page_content)

        else:
            return HTMLResponse(
                create_base_page(
                    page_title="Clepsy",
                    content=home_page_content,
                    user_settings=user_settings,
                )
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/update-unified-diagram")
async def update_unified_diagram(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    parsed_selected_tag_ids = json.loads(selected_tag_ids)
    parsed_selected_tag_ids = [int(tag_id) for tag_id in parsed_selected_tag_ids]

    async with get_db_connection(include_uuid_func=False) as conn:
        user_tz = ZoneInfo(user_settings.timezone)

        # reference_date comes from the client as a timezone-less local string.
        # If it ever includes a timezone, respect it; otherwise, assume user_tz.
        parsed = datetime.fromisoformat(reference_date)
        assert parsed.tzinfo is None, "Should be naive"
        reference_date_user_tz = parsed.replace(tzinfo=user_tz)
        current_time_user_tz = datetime.now(user_tz)  # Get current time

        start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
            reference_date=reference_date_user_tz,
            offset=offset,
            view_mode=view_mode,
        )

        start_utc = start_user_tz.astimezone(timezone.utc)
        end_utc = end_user_tz.astimezone(timezone.utc)

        activity_specs = await select_specs_with_tags_and_sessions_in_time_range(
            conn=conn,
            start=start_utc,
            end=end_utc,
        )

        last_aggregation = await select_last_aggregation(conn=conn)

        # Filter activity specs by selected tags
    activity_specs = filter_activities_by_tags(activity_specs, parsed_selected_tag_ids)

    activity_specs_user_tz = [x.to_tz(user_tz) for x in activity_specs]

    if last_aggregation:
        last_aggregation_end_time_utc = last_aggregation.end_time
        last_aggregation_end_time_user_tz = last_aggregation_end_time_utc.astimezone(
            user_tz
        )
    else:
        last_aggregation_end_time_user_tz = None  # Corrected variable name

    element = create_unified_diagram_body(
        activity_specs=activity_specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_aggregation_end_time_user_tz,
        current_time_user_tz=current_time_user_tz,
    )

    return HTMLResponse(element)
