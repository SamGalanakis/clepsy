from datetime import datetime, timezone as dt_timezone
import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from htpy import div, p
from starlette import status

from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    delete_goal,
    insert_goal,
    insert_goal_definition,
    insert_goal_pause_event,
    insert_goal_tags,
    select_goals_with_latest_definition,
)
from clepsy.entities import (
    AvgProductivityOperators,
    DaysOfWeek,
    GoalMetric,
    GoalPeriod,
    IncludeMode,
    MetricOperator,
    ProductivityLevel,
    TotalActivityDurationOperators,
    UserSettings,
)
from clepsy.frontend.components import (
    create_base_page,
)
from clepsy.modules.goals.calculate_goals import update_current_progress_for_goal
from clepsy.scheduler import cron_trigger_given_period_and_created_at, scheduler

from .pages import (
    create_create_goal_form,
    create_create_goal_form_page,
    create_create_goal_page,
    create_edit_goal_page,
    create_goals_page,
    render_goal_row,
)


router = APIRouter(prefix="/goals")


# --- Helpers: metric slug mapping ---
_METRIC_SLUGS: dict[GoalMetric, str] = {
    GoalMetric.AVG_PRODUCTIVITY_LEVEL: "productivity-average",
    GoalMetric.TOTAL_ACTIVITY_DURATION: "total-activity-duration",
}


def metric_from_slug(slug: str) -> GoalMetric | None:
    for k, v in _METRIC_SLUGS.items():
        if v == slug:
            return k
    return None


@router.delete("/{goal_id}")
async def delete_goal_endpoint(
    goal_id: int,
) -> Response:
    try:
        async with get_db_connection(
            commit_on_exit=True, start_transaction=False
        ) as conn:
            await delete_goal(conn, goal_id)

        # Return 200 with empty body so hx-swap="outerHTML" clears the row element
        resp = HTMLResponse("", status_code=200)

        await scheduler.remove_schedule(id=f"periodic_goal_evaluation_{goal_id}")

        resp.headers["HX-Trigger"] = json.dumps(
            {
                "basecoat:toast": {
                    "config": {
                        "category": "success",
                        "title": "Goal deleted",
                        "description": "The goal was deleted.",
                    }
                }
            }
        )
        return resp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.put("/{goal_id}/pause-toggle")
async def set_goal_paused_endpoint(goal_id: int, enabled: bool = Form(...)) -> Response:
    """HTMX endpoint to pause/resume a goal by appending an event.

    Accepts form field 'enabled' (boolean). If true, we insert a 'resume' event; if false, a 'pause' event.
    """

    now_utc = datetime.now(dt_timezone.utc)
    event_type = "resume" if enabled else "pause"

    async with get_db_connection(commit_on_exit=True, start_transaction=True) as conn:
        await insert_goal_pause_event(
            conn, goal_id=goal_id, event_type=event_type, at=now_utc
        )
        # After updating, re-select latest goal state and render the row
        gwrs = await select_goals_with_latest_definition(conn, last_successes_limit=8)
        gwr = next((g for g in gwrs if g.goal.id == goal_id), None)
        if not gwr:
            return HTMLResponse("", status_code=404)
        row_el = await render_goal_row(conn, gwr)

    resp = HTMLResponse(row_el, status_code=200)
    resp.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Goal updated",
                    "description": f"Goal has been {'resumed' if enabled else 'paused'}.",
                }
            }
        }
    )
    return resp


@router.get("/")
async def goals_page(
    request: Request,
    user_settings: UserSettings = Depends(get_user_settings),
) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        goals_page_content = await create_goals_page(conn=conn)

    if request.state.is_htmx:
        return HTMLResponse(goals_page_content)

    return HTMLResponse(
        create_base_page(
            user_settings=user_settings,
            page_title="Goals",
            content=goals_page_content,
        )
    )


@router.get("/row/{goal_id}")
async def get_goal_row(_: Request, goal_id: int) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        gwrs = await select_goals_with_latest_definition(conn, last_successes_limit=8)
        gwr = next((g for g in gwrs if g.goal.id == goal_id), None)
        if not gwr:
            return HTMLResponse("", status_code=404)
        row_el = await render_goal_row(conn, gwr)
    return HTMLResponse(row_el)


@router.get("/row/{goal_id}/refresh")
async def refresh_goal_row(_: Request, goal_id: int) -> Response:
    async with get_db_connection(commit_on_exit=True, start_transaction=True) as conn:
        gwrs = await select_goals_with_latest_definition(conn, last_successes_limit=8)
        gwr = next((g for g in gwrs if g.goal.id == goal_id), None)
        if not gwr:
            return HTMLResponse("", status_code=404)
        now_utc = datetime.now(dt_timezone.utc)
        await update_current_progress_for_goal(
            conn=conn,
            goal=gwr.goal,
            definition=gwr.definition,
            include_tags=gwr.include_tags,
            exclude_tags=gwr.exclude_tags,
            now_utc=now_utc,
        )
        # After compute, re-render row with fresh data
        row_el = await render_goal_row(conn, gwr)
    return HTMLResponse(row_el)


@router.get("/{goal_id}/edit")
async def edit_goal_page(
    request: Request,
    goal_id: int,
    user_settings: UserSettings = Depends(get_user_settings),
) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        page_el = await create_edit_goal_page(conn=conn, goal_id=goal_id)

    if request.state.is_htmx:
        return HTMLResponse(page_el)

    return HTMLResponse(
        create_base_page(
            user_settings=user_settings,
            page_title="Edit Goal",
            content=page_el,
        )
    )


# --- EDIT (metric-specific) ---
async def submit_edit_goal_impl(
    *,
    goal_id: int,
    name: str,
    description: str,
    include_mode: IncludeMode,
    target_value: str | None,
    days: Optional[list[DaysOfWeek]],
    time_starts: Optional[list[str]],
    time_ends: Optional[list[str]],
    productivity_levels: Optional[list[ProductivityLevel]],
    metric_params: str | None,
) -> Response:
    errors: dict[str, str] = {}
    metric_params_json: str | None = None

    # Read current goal/definition and validate inputs
    async with get_db_connection(include_uuid_func=False) as conn:
        gwrs = await select_goals_with_latest_definition(conn, last_successes_limit=1)
        gwr = next((g for g in gwrs if g.goal.id == goal_id), None)
        if not gwr:
            return HTMLResponse("Goal not found", status_code=404)

        metric_enum = gwr.goal.metric
        inc_mode_enum = include_mode

        if not name.strip():
            errors["name"] = "Name is required"

        # Parse metric_params JSON if provided
        if metric_params and metric_params.strip():
            try:
                json.loads(metric_params)
                metric_params_json = metric_params
            except json.JSONDecodeError:
                errors["metric_params"] = "Must be valid JSON"

        # Target parsing depends on metric
        parsed_target: float | None = None
        if metric_enum == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            if target_value is None:
                errors["target_value"] = "Target value is required"
            else:
                try:
                    v = float(target_value)
                    if not (0.0 <= v <= 1.0):
                        raise ValueError()
                    parsed_target = v
                except (TypeError, ValueError):
                    errors["target_value"] = "Target must be a number between 0 and 1"
        elif metric_enum == GoalMetric.TOTAL_ACTIVITY_DURATION:
            if target_value is None or target_value.strip() == "":
                errors["target_value"] = "Target duration is required"
            else:
                try:
                    seconds = float(target_value)
                    if seconds <= 0:
                        raise ValueError()
                    parsed_target = seconds
                except (TypeError, ValueError):
                    errors["target_value"] = "Enter a positive duration (in seconds)"

        # Filters JSON
        day_filter_json = None
        if days:
            day_filter_json = json.dumps([str(d) for d in days])

        time_filter_json = None
        if time_starts and time_ends and len(time_starts) == len(time_ends):
            pairs: list[list[str]] = []
            for s, e in zip(time_starts, time_ends):
                if not s or not e:
                    continue
                pairs.append([s, e])
            if pairs:
                time_filter_json = json.dumps(pairs)

        productivity_filter_json = None
        if productivity_levels:
            productivity_filter_json = json.dumps(
                [pl.value for pl in productivity_levels]
            )

        if errors:
            # Re-render edit page with inline errors and posted values using explicit params
            async with get_db_connection(include_uuid_func=False) as conn2:
                name_error = errors.get("name")
                description_error = errors.get("description")
                include_mode_error = errors.get("include_mode")
                metric_params_error = errors.get("metric_params")
                target_value_error = errors.get("target_value")

                days_list = list(days or [])
                time_pairs_list = list(zip(time_starts or [], (time_ends or [])))
                prod_levels_list = list(productivity_levels or [])

                target_seconds_value = None
                target_value_value = None
                if metric_enum == GoalMetric.TOTAL_ACTIVITY_DURATION:
                    target_seconds_value = target_value or ""
                else:
                    target_value_value = target_value or ""

                page_el = await create_edit_goal_page(
                    conn=conn2,
                    goal_id=goal_id,
                    name_error=name_error,
                    description_error=description_error,
                    include_mode_error=include_mode_error,
                    metric_params_error=metric_params_error,
                    target_value_error=target_value_error,
                    target_seconds_error=None,
                    name_value=name,
                    description_value=description,
                    include_mode_value=inc_mode_enum.value,
                    metric_params_value=metric_params or "",
                    target_value_value=target_value_value,
                    target_seconds_value=target_seconds_value,
                    days_value=[str(d) for d in days_list],
                    time_pairs_value=time_pairs_list,
                    productivity_levels_value=[pl.value for pl in prod_levels_list],
                )
            return HTMLResponse(page_el)

    # Success: insert new definition, preserve goal tags as-is
    async with get_db_connection(commit_on_exit=True, start_transaction=True) as w:
        eff_from = datetime.now(dt_timezone.utc)
        _ = await insert_goal_definition(
            w,
            goal_id=goal_id,
            name=name,
            description=description or None,
            target_value=parsed_target or 0.0,
            include_mode=inc_mode_enum,  # already IncludeMode
            day_filter_json=day_filter_json,
            time_filter_json=time_filter_json,
            productivity_filter_json=productivity_filter_json,
            effective_from=eff_from,
            metric_params_json=metric_params_json,
        )

    response = JSONResponse(content="", status_code=200)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Goal updated",
                    "description": "Your changes have been saved.",
                }
            }
        }
    )
    response.headers["HX-Redirect"] = "/s/goals"
    return response


@router.post("/{goal_id}/edit/productivity-average")
async def submit_edit_goal_productivity(
    goal_id: int,
    name: Annotated[str, Form()],
    include_mode: Annotated[IncludeMode, Form()],
    description: Annotated[str, Form()] = "",
    target_value: Annotated[str | None, Form()] = None,
    days: Annotated[Optional[list[DaysOfWeek]], Form(alias="days[]")] = None,
    time_starts: Annotated[Optional[list[str]], Form(alias="time_starts[]")] = None,
    time_ends: Annotated[Optional[list[str]], Form(alias="time_ends[]")] = None,
    productivity_levels: Annotated[
        Optional[list[ProductivityLevel]], Form(alias="productivity_levels[]")
    ] = None,
    metric_params: Annotated[str | None, Form()] = None,
) -> Response:
    return await submit_edit_goal_impl(
        goal_id=goal_id,
        name=name,
        description=description,
        include_mode=include_mode,
        target_value=target_value,
        days=days,
        time_starts=time_starts,
        time_ends=time_ends,
        productivity_levels=productivity_levels,
        metric_params=metric_params,
    )


@router.post("/{goal_id}/edit/total-activity-duration")
async def submit_edit_goal_total_duration(
    goal_id: int,
    name: Annotated[str, Form()],
    include_mode: Annotated[IncludeMode, Form()],
    # target (seconds from duration picker; required)
    target_seconds: Annotated[int, Form()],
    description: Annotated[str, Form()] = "",
    days: Annotated[Optional[list[DaysOfWeek]], Form(alias="days[]")] = None,
    time_starts: Annotated[Optional[list[str]], Form(alias="time_starts[]")] = None,
    time_ends: Annotated[Optional[list[str]], Form(alias="time_ends[]")] = None,
    productivity_levels: Annotated[
        Optional[list[ProductivityLevel]], Form(alias="productivity_levels[]")
    ] = None,
    metric_params: Annotated[str | None, Form()] = None,
) -> Response:
    return await submit_edit_goal_impl(
        goal_id=goal_id,
        name=name,
        description=description,
        include_mode=include_mode,
        target_value=str(target_seconds),
        days=days,
        time_starts=time_starts,
        time_ends=time_ends,
        productivity_levels=productivity_levels,
        metric_params=metric_params,
    )


@router.get("/create-goal")
async def create_goal_page(
    request: Request,
    user_settings: UserSettings = Depends(get_user_settings),
) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        page_content = await create_create_goal_page(conn=conn)

    if request.state.is_htmx:
        return HTMLResponse(page_content)

    return HTMLResponse(
        create_base_page(
            user_settings=user_settings,
            page_title="Create Goal",
            content=page_content,
        )
    )


@router.get("/create-goal/{metric_slug}")
async def create_goal_for_metric(
    request: Request,
    metric_slug: str,
    user_settings: UserSettings = Depends(get_user_settings),
) -> Response:
    metric = metric_from_slug(metric_slug)
    if metric is None:
        # Unknown slug, send back to selector
        return RedirectResponse(
            url="/s/goals/create-goal", status_code=status.HTTP_303_SEE_OTHER
        )

    async with get_db_connection(include_uuid_func=False) as conn:
        # For HTMX requests return just the form container; otherwise wrap as full page
        if request.state.is_htmx:
            form_container = await create_create_goal_form(conn=conn, metric=metric)
            return HTMLResponse(form_container)
        else:
            page_el = await create_create_goal_form_page(conn=conn, metric=metric)
            return HTMLResponse(
                create_base_page(
                    user_settings=user_settings,
                    page_title="Create Goal",
                    content=page_el,
                )
            )
    # unreachable


@router.post("/create-goal/select-metric")
async def select_goal_metric(metric: str = Form(...)) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        # Enforce enum mapping; will raise on invalid
        metric_enum = GoalMetric(metric)
        form_container = await create_create_goal_form(conn=conn, metric=metric_enum)
    return HTMLResponse(form_container)


# --- CREATE helpers (common parts) ---
def build_filter_jsons(
    *,
    days: Optional[list[DaysOfWeek]],
    time_starts: Optional[list[str]],
    time_ends: Optional[list[str]],
    productivity_levels: Optional[list[ProductivityLevel]],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    day_filter_json: Optional[str] = None
    if days:
        day_filter_json = json.dumps([str(d) for d in days])

    time_filter_json: Optional[str] = None
    if time_starts and time_ends and len(time_starts) == len(time_ends):
        pairs: list[list[str]] = []
        for s, e in zip(time_starts, time_ends):
            if not s or not e:
                continue
            pairs.append([s, e])
        if pairs:
            time_filter_json = json.dumps(pairs)

    productivity_filter_json: Optional[str] = None
    if productivity_levels:
        productivity_filter_json = json.dumps([pl.value for pl in productivity_levels])

    return day_filter_json, time_filter_json, productivity_filter_json


async def render_create_form_error_response(metric: GoalMetric) -> HTMLResponse:
    async with get_db_connection(include_uuid_func=False) as conn:
        form_container = await create_create_goal_form(conn=conn, metric=metric)

    content = div(id="create-goal-container", class_="card")[
        div(
            class_="p-2 m-2 text-sm text-red-700 bg-red-100 border border-red-400 rounded"
        )[p["Please correct the errors and try again."]],
        form_container,
    ]
    return HTMLResponse(content)


async def persist_created_goal(
    *,
    metric: GoalMetric,
    operator: MetricOperator,
    name: str,
    description: str,
    target_value: float,
    include_mode: IncludeMode,
    day_filter_json: Optional[str],
    time_filter_json: Optional[str],
    productivity_filter_json: Optional[str],
    period: GoalPeriod,
    timezone_str: str,
    include_tag_ids: list[int],
    exclude_tag_ids: list[int],
) -> Response:
    async with get_db_connection(commit_on_exit=True, start_transaction=True) as conn:
        goal_id = await insert_goal(
            conn,
            metric=metric,
            operator=operator,
            period=period,
            timezone=timezone_str,
        )

        eff_from = datetime.now(dt_timezone.utc)
        def_id = await insert_goal_definition(
            conn,
            goal_id=goal_id,
            name=name,
            description=description or None,
            target_value=target_value,
            include_mode=include_mode,
            day_filter_json=day_filter_json,
            time_filter_json=time_filter_json,
            productivity_filter_json=productivity_filter_json,
            effective_from=eff_from,
        )
        await insert_goal_tags(
            conn,
            goal_definition_id=def_id,
            include_tag_ids=include_tag_ids,
            exclude_tag_ids=exclude_tag_ids,
        )

    await scheduler.add_schedule(
        id=f"periodic_goal_evaluation_{goal_id}",
        func_or_task_id="update_previous_full_period_goal_result",
        kwargs={"goal_id": goal_id},
        trigger=cron_trigger_given_period_and_created_at(
            period=period, created_at=eff_from
        ),
    )

    response = RedirectResponse(url="/s/goals", status_code=200)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Goal created",
                    "description": "Your goal was created successfully.",
                }
            }
        }
    )
    response.headers["HX-Redirect"] = "/s/goals"
    return response


@router.post("/create-goal/submit/productivity-average")
async def submit_create_goal_productivity(
    # required basics and typed operator
    name: Annotated[str, Form()],
    operator: Annotated[AvgProductivityOperators, Form()],
    period: Annotated[GoalPeriod, Form()],
    include_mode: Annotated[IncludeMode, Form()],
    # optional/basic
    description: Annotated[str, Form()] = "",
    # target
    target_value: Annotated[str | None, Form()] = None,
    # filters (optional)
    include_tag_ids: Annotated[Optional[list[int]], Form()] = None,
    exclude_tag_ids: Annotated[Optional[list[int]], Form()] = None,
    days: Annotated[Optional[list[DaysOfWeek]], Form(alias="days[]")] = None,
    time_starts: Annotated[Optional[list[str]], Form(alias="time_starts[]")] = None,
    time_ends: Annotated[Optional[list[str]], Form(alias="time_ends[]")] = None,
    productivity_levels: Annotated[
        Optional[list[ProductivityLevel]], Form(alias="productivity_levels[]")
    ] = None,
    timezone: Annotated[str, Form()] = "",
) -> Response:
    # Common validations (inline)
    errors: dict[str, str] = {}
    inc_mode_enum = include_mode
    if not name.strip():
        errors["name"] = "Name is required"

    # Metric-specific target parsing (0.0 - 1.0)
    parsed_target: Optional[float] = None
    if target_value is None:
        errors["target_value"] = "Target value is required"
    else:
        try:
            v = float(target_value)
            if not (0.0 <= v <= 1.0):
                raise ValueError()
            parsed_target = v
        except (TypeError, ValueError):
            errors["target_value"] = "Target must be a number between 0 and 1"

    day_filter_json, time_filter_json, productivity_filter_json = build_filter_jsons(
        days=days,
        time_starts=time_starts,
        time_ends=time_ends,
        productivity_levels=productivity_levels,
    )

    if errors or parsed_target is None:
        return await render_create_form_error_response(
            GoalMetric.AVG_PRODUCTIVITY_LEVEL
        )

    return await persist_created_goal(
        metric=GoalMetric.AVG_PRODUCTIVITY_LEVEL,
        operator=operator,
        name=name,
        description=description,
        target_value=parsed_target,
        include_mode=inc_mode_enum,
        day_filter_json=day_filter_json,
        time_filter_json=time_filter_json,
        productivity_filter_json=productivity_filter_json,
        period=period,
        timezone_str=timezone,
        include_tag_ids=include_tag_ids or [],
        exclude_tag_ids=exclude_tag_ids or [],
    )


@router.post("/create-goal/submit/total-activity-duration")
async def submit_create_goal_duration(
    # required basics and typed operator
    name: Annotated[str, Form()],
    operator: Annotated[TotalActivityDurationOperators, Form()],
    period: Annotated[GoalPeriod, Form()],
    include_mode: Annotated[IncludeMode, Form()],
    # target (seconds from duration picker; required)
    target_seconds: Annotated[int, Form()],
    # optional/basic
    description: Annotated[str, Form()] = "",
    # filters (optional)
    include_tag_ids: Annotated[Optional[list[int]], Form()] = None,
    exclude_tag_ids: Annotated[Optional[list[int]], Form()] = None,
    days: Annotated[Optional[list[DaysOfWeek]], Form(alias="days[]")] = None,
    time_starts: Annotated[Optional[list[str]], Form(alias="time_starts[]")] = None,
    time_ends: Annotated[Optional[list[str]], Form(alias="time_ends[]")] = None,
    productivity_levels: Annotated[
        Optional[list[ProductivityLevel]], Form(alias="productivity_levels[]")
    ] = None,
    timezone: Annotated[str, Form()] = "",
) -> Response:
    # Common validations (inline)
    errors: dict[str, str] = {}
    inc_mode_enum = include_mode
    if not name.strip():
        errors["name"] = "Name is required"

    # Metric-specific target parsing (seconds > 0)
    parsed_target: Optional[float] = None
    try:
        sec = float(target_seconds)
        if sec <= 0:
            raise ValueError()
        parsed_target = sec
    except (TypeError, ValueError):
        errors["target_seconds"] = "Enter a positive duration in seconds"

    day_filter_json, time_filter_json, productivity_filter_json = build_filter_jsons(
        days=days,
        time_starts=time_starts,
        time_ends=time_ends,
        productivity_levels=productivity_levels,
    )

    if errors or parsed_target is None:
        return await render_create_form_error_response(
            GoalMetric.TOTAL_ACTIVITY_DURATION
        )

    return await persist_created_goal(
        metric=GoalMetric.TOTAL_ACTIVITY_DURATION,
        operator=operator,
        name=name,
        description=description,
        target_value=parsed_target,
        include_mode=inc_mode_enum,
        day_filter_json=day_filter_json,
        time_filter_json=time_filter_json,
        productivity_filter_json=productivity_filter_json,
        period=period,
        timezone_str=timezone,
        include_tag_ids=include_tag_ids or [],
        exclude_tag_ids=exclude_tag_ids or [],
    )
