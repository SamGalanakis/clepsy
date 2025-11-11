from datetime import datetime, timezone as dt_timezone
import json
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from clepsy import utils
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    select_last_aggregation,
    select_specs_with_tags_in_time_range,
)
from clepsy.entities import DBActivitySpecWithTags, UserSettings, ViewMode
from clepsy.frontend.components import create_base_page
from clepsy.modules.insights.components.focus_sessions import (
    create_focus_sessions_calendar_body,
    create_focus_sessions_histogram_body,
    create_focus_sessions_stats_body,
)
from clepsy.modules.insights.components.productivity_donut import (
    create_productivity_donut_body,
)
from clepsy.modules.insights.components.productivity_time_slice import (
    create_productivity_time_slice_body,
)
from clepsy.modules.insights.components.tag_transition_chord import (
    create_tag_transition_chord_body,
)
from clepsy.modules.insights.components.time_spent_per_tag import (
    create_time_spent_per_tag_body,
)

from .pages.home import create_insights_page


router = APIRouter(prefix="/insights")


@router.get("/")
async def insights_home(
    request: Request,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        async with get_db_connection(include_uuid_func=False) as _:
            page_el = await create_insights_page(user_settings=user_settings)

        if request.state.is_htmx:
            return HTMLResponse(page_el)

        return HTMLResponse(
            create_base_page(
                page_title="Insights",
                content=page_el,
                user_settings=user_settings,
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


def filter_activities_by_tags(
    activities: list[DBActivitySpecWithTags], selected_tag_ids: list[int]
) -> list[DBActivitySpecWithTags]:
    if not selected_tag_ids:
        return activities
    no_tag_selected = -1 in selected_tag_ids
    filtered = []
    for spec in activities:
        has_match = any(tag.id in selected_tag_ids for tag in spec.tags)
        if has_match or (no_tag_selected and not spec.tags):
            filtered.append(spec)
    return filtered


@router.get("/update-time-spent-per-tag")
async def update_time_spent_per_tag(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    # Parse incoming values
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]

    user_tz = ZoneInfo(user_settings.timezone)
    # reference_date is an ISO string without tz; interpret it as user_tz
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)

    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref,
        offset=offset,
        view_mode=view_mode,
    )

    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        # Convert to user TZ
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        # Filter by tags
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)

    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None

    body = create_time_spent_per_tag_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
    )
    return HTMLResponse(body)


@router.get("/update-productivity-time-slice")
async def update_productivity_time_slice(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]

    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)

    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref,
        offset=offset,
        view_mode=view_mode,
    )

    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)

    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None

    body = create_productivity_time_slice_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
        view_mode=view_mode,
    )
    return HTMLResponse(body)


@router.get("/update-productivity-donut")
async def update_productivity_donut(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]

    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)

    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref,
        offset=offset,
        view_mode=view_mode,
    )

    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)

    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None

    body = create_productivity_donut_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
        view_mode=view_mode,
    )
    return HTMLResponse(body)


@router.get("/update-focus-sessions-calendar")
async def update_focus_sessions_calendar(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]
    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)
    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref, offset=offset, view_mode=view_mode
    )
    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)
    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None
    body = create_focus_sessions_calendar_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
        view_mode=view_mode,
    )
    return HTMLResponse(body)


@router.get("/update-focus-sessions-histogram")
async def update_focus_sessions_histogram(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]
    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)
    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref, offset=offset, view_mode=view_mode
    )
    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)
    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None
    body = create_focus_sessions_histogram_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
        view_mode=view_mode,
    )
    return HTMLResponse(body)


@router.get("/update-focus-sessions-stats")
async def update_focus_sessions_stats(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]
    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)
    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref, offset=offset, view_mode=view_mode
    )
    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )
        last_agg = await select_last_aggregation(conn)
    last_agg_end_user_tz = last_agg.end_time.astimezone(user_tz) if last_agg else None
    body = create_focus_sessions_stats_body(
        activity_specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
        last_aggregation_end_time_user_tz=last_agg_end_user_tz,
        current_time_user_tz=datetime.now(user_tz),
        view_mode=view_mode,
    )
    return HTMLResponse(body)


@router.get("/update-tag-transition-chord")
async def update_tag_transition_chord(
    offset: int,
    reference_date: str,
    selected_tag_ids: str,
    view_mode: ViewMode,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    try:
        parsed_ids_raw = json.loads(selected_tag_ids) if selected_tag_ids else []
    except json.JSONDecodeError:
        parsed_ids_raw = []
    parsed_selected_tag_ids = [int(x) for x in parsed_ids_raw]

    user_tz = ZoneInfo(user_settings.timezone)
    parsed_ref = datetime.fromisoformat(reference_date)
    if parsed_ref.tzinfo is None:
        parsed_ref = parsed_ref.replace(tzinfo=user_tz)

    start_user_tz, end_user_tz = utils.calculate_date_based_on_view_mode(
        reference_date=parsed_ref,
        offset=offset,
        view_mode=view_mode,
    )

    async with get_db_connection(include_uuid_func=False) as conn:
        specs = await select_specs_with_tags_in_time_range(
            conn=conn,
            start=start_user_tz.astimezone(dt_timezone.utc),
            end=end_user_tz.astimezone(dt_timezone.utc),
        )
        specs_user_tz = [s.to_tz(user_tz) for s in specs]
        specs_user_tz = filter_activities_by_tags(
            specs_user_tz, parsed_selected_tag_ids
        )

    body = create_tag_transition_chord_body(
        specs=specs_user_tz,
        start_time_user_tz=start_user_tz,
        end_time_user_tz=end_user_tz,
    )
    return HTMLResponse(body)
