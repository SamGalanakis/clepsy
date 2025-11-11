from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from loguru import logger

from clepsy.db.db import get_db_connection
from clepsy.db.queries import (
    get_filtered_activity_specs_for_goal,
    insert_goal_result,
    is_goal_paused_at,
    select_goal_with_definition_active_at,
    select_goal_with_latest_definition_by_definition_id,
    select_latest_goal_definition_id_for_goal,
    select_latest_progress_updated_at_for_goal,
    select_tags_by_ids,
    upsert_goal_progress_current,
)
from clepsy.entities import (
    DBActivitySpecWithTags,
    DBGoal,
    DBGoalDefinition,
    DBTag,
    EvalState,
    GoalMetric,
    GoalPeriod,
    GoalResult,
    MetricOperator,
    ProductivityLevel,
)


def calculate_avg_productivity_level(
    filtered_specs: list[DBActivitySpecWithTags],
    period_start_utc: datetime,
    period_end_utc: datetime,
):
    # 3. For productivity, build a timeline of all intervals
    events = []
    for spec in filtered_specs:
        evs = sorted(spec.events, key=lambda e: e.event_time)
        open_time = None
        for e in evs:
            if e.event_type == "open":
                open_time = e.event_time
            elif e.event_type == "close" and open_time:
                start = max(open_time, period_start_utc)
                end = min(e.event_time, period_end_utc)
                if start < end:
                    events.append((start, +1, spec.activity.productivity_level))
                    events.append((end, -1, spec.activity.productivity_level))
                open_time = None
        if open_time and open_time < period_end_utc:
            start = max(open_time, period_start_utc)
            end = period_end_utc
            if start < end:
                events.append((start, +1, spec.activity.productivity_level))
                events.append((end, -1, spec.activity.productivity_level))

    # 4. Build timeline, compute time-weighted productivity
    prod_map = {
        ProductivityLevel.VERY_PRODUCTIVE: 1.0,
        ProductivityLevel.PRODUCTIVE: 0.75,
        ProductivityLevel.NEUTRAL: 0.5,
        ProductivityLevel.DISTRACTING: 0.25,
        ProductivityLevel.VERY_DISTRACTING: 0.0,
    }
    events.sort()
    active = []
    last_time = period_start_utc
    weighted_sum = 0.0
    total_time = 0.0
    for t, delta, prod in events:
        if t > last_time and active:
            dt = (t - last_time).total_seconds()
            avg_prod = sum(prod_map[p] for p in active) / len(active)
            weighted_sum += dt * avg_prod
            total_time += dt
        if delta == +1:
            active.append(prod)
        elif delta == -1:
            if prod in active:
                active.remove(prod)
        last_time = t
    if active and last_time < period_end_utc:
        dt = (period_end_utc - last_time).total_seconds()
        avg_prod = sum(prod_map[p] for p in active) / len(active)
        weighted_sum += dt * avg_prod
        total_time += dt
    avg = weighted_sum / total_time if total_time > 0 else 0.0

    return avg


def calculate_total_activity_duration_seconds(
    filtered_specs: list[DBActivitySpecWithTags],
    period_start_utc: datetime,
    period_end_utc: datetime,
) -> float:
    """Compute the union duration in seconds where at least one filtered activity is open.

    Builds a sweep-line over all open/close intervals clamped to [period_start_utc, period_end_utc].
    """
    events: list[tuple[datetime, int]] = []
    for spec in filtered_specs:
        evs = sorted(spec.events, key=lambda e: e.event_time)
        open_time: datetime | None = None
        for e in evs:
            if e.event_type == "open":
                open_time = e.event_time
            elif e.event_type == "close" and open_time:
                start = max(open_time, period_start_utc)
                end = min(e.event_time, period_end_utc)
                if start < end:
                    events.append((start, +1))
                    events.append((end, -1))
                open_time = None
        # Unclosed interval to the end of period
        if open_time and open_time < period_end_utc:
            start = max(open_time, period_start_utc)
            end = period_end_utc
            if start < end:
                events.append((start, +1))
                events.append((end, -1))

    if not events:
        return 0.0
    events.sort()
    active_count = 0
    last_time = events[0][0]
    total_seconds = 0.0
    for t, delta in events:
        if active_count > 0 and t > last_time:
            total_seconds += (t - last_time).total_seconds()
        active_count += delta
        last_time = t
    return total_seconds


async def calculate_eval_state(
    conn: aiosqlite.Connection,
    include_tags: list[DBTag] | None,
    exclude_tags: list[DBTag] | None,
    period_end_utc: datetime,
) -> tuple[EvalState, str | None]:
    # Tag deletion check for eval_state
    eval_state = EvalState.OK

    include_tag_ids = [t.id for t in include_tags] if include_tags else None
    exclude_tag_ids = [t.id for t in exclude_tags] if exclude_tags else None
    eval_state_reason = None
    relevant_tag_ids = (include_tag_ids or []) + (exclude_tag_ids or [])
    deleted_tags = []
    if relevant_tag_ids:
        tag_rows = await select_tags_by_ids(
            conn, relevant_tag_ids, include_deleted=True
        )
        for tag in tag_rows:
            deleted_at = tag.get("deleted_at")
            if deleted_at is not None:
                deleted_time = deleted_at
                # If deleted before or during the period (in UTC)
                if deleted_time <= period_end_utc:
                    deleted_tags.append(tag["name"])
        if deleted_tags:
            eval_state = EvalState.PARTIAL
            eval_state_reason = f"Relevant tag(s) deleted during or before this period: {', '.join(deleted_tags)}"
            return eval_state, eval_state_reason
    return eval_state, eval_state_reason


def determine_success(
    goal: DBGoal, definition: DBGoalDefinition, result: float, is_full_period: bool
) -> bool | None:
    match goal.metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            if is_full_period:
                match goal.operator:
                    case MetricOperator.GREATER_THAN:
                        # definition.target_value is float for this metric
                        return result > definition.target_value  # type: ignore[arg-type]
                    case MetricOperator.LESS_THAN:
                        return result < definition.target_value  # type: ignore[arg-type]
                    case _:
                        raise ValueError(
                            f"Unsupported operator for AVG_PRODUCTIVITY_LEVEL: {goal.operator}"
                        )
            else:
                return None  # Partial periods don't determine success

        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            if hasattr(definition.target_value, "total_seconds"):
                target_seconds = definition.target_value.total_seconds()  # type: ignore[union-attr]
            else:
                # Stored as numeric seconds
                target_seconds = float(definition.target_value)  # type: ignore[arg-type]
            if is_full_period:
                match goal.operator:
                    case MetricOperator.GREATER_THAN:
                        return result > target_seconds
                    case MetricOperator.LESS_THAN:
                        return result < target_seconds
                    case _:
                        raise ValueError(
                            f"Unsupported operator for TOTAL_ACTIVITY_DURATION: {goal.operator}"
                        )
            else:
                # Partial period semantics:
                # - GREATER_THAN: if already reached or surpassed target, success (True), else unknown (None)
                # - LESS_THAN: if already reached or surpassed target, fail (False), else unknown (None)
                match goal.operator:
                    case MetricOperator.GREATER_THAN:
                        return True if result >= target_seconds else None
                    case MetricOperator.LESS_THAN:
                        return False if result >= target_seconds else None
                    case _:
                        raise ValueError(
                            f"Unsupported operator for TOTAL_ACTIVITY_DURATION: {goal.operator}"
                        )
        case _:
            raise ValueError(f"Unsupported goal metric: {goal.metric}")


async def calculate_goal_result(
    *,
    goal: DBGoal,
    definition: DBGoalDefinition,
    include_tags: list[DBTag] | None,
    exclude_tags: list[DBTag] | None,
    period_start: date,
    period_end: date,
    conn: aiosqlite.Connection,
    is_full_period: bool,
) -> GoalResult:
    """
    Calculate a GoalResult for the given goal and period.
    Only implements AvgProductivityLevelGoalDefinition for now.
    """
    # --- Timezone handling ---

    # Use goal timezone
    user_tz = ZoneInfo(goal.timezone)

    # Convert period_start and period_end (date) to UTC datetimes for the full days in user tz
    user_period_start_dt = datetime.combine(period_start, time.min).replace(
        tzinfo=user_tz
    )
    user_period_end_dt = datetime.combine(period_end, time.max).replace(tzinfo=user_tz)
    period_start_utc = user_period_start_dt.astimezone(timezone.utc)
    period_end_utc = user_period_end_dt.astimezone(timezone.utc)

    # Prepare filters
    include_tag_ids = [t.id for t in (include_tags or []) if t.id is not None] or None
    exclude_tag_ids = [t.id for t in (exclude_tags or []) if t.id is not None] or None
    include_mode = (
        definition.include_mode.value
        if hasattr(definition.include_mode, "value")
        else definition.include_mode
    )
    productivity_levels = [
        p.value if hasattr(p, "value") else p
        for p in (definition.productivity_filter or [])
    ]

    # Day filter: convert user days to UTC days for the query
    if definition.day_filter:
        # For each user day, find all UTC days that overlap with that user day in the user's tz
        # For simplicity, pass user days as strings, and handle in SQL as UTC (may miss edge cases)
        day_filter = [str(d) for d in definition.day_filter]
    else:
        day_filter = None

    # Time filter: convert user local times (HH:MM) to UTC times (HH:MM) for the query
    if definition.time_filter:
        time_filter = []
        for start_str, end_str in definition.time_filter:
            # Parse as user local time, only HH:MM
            start_h, start_m = map(int, start_str.split(":")[:2])
            end_h, end_m = map(int, end_str.split(":")[:2])
            start_local = datetime.combine(
                datetime.today(), time(start_h, start_m)
            ).replace(tzinfo=user_tz)
            end_local = datetime.combine(datetime.today(), time(end_h, end_m)).replace(
                tzinfo=user_tz
            )
            # Convert to UTC and format as HH:MM
            start_utc = start_local.astimezone(timezone.utc).time().strftime("%H:%M")
            end_utc = end_local.astimezone(timezone.utc).time().strftime("%H:%M")
            time_filter.append((start_utc, end_utc))
    else:
        time_filter = None

    filtered_specs: list[
        DBActivitySpecWithTags
    ] = await get_filtered_activity_specs_for_goal(
        conn=conn,
        start=period_start_utc,
        end=period_end_utc,
        include_tag_ids=include_tag_ids,
        exclude_tag_ids=exclude_tag_ids,
        include_mode=include_mode,
        productivity_levels=productivity_levels,
        day_filter=day_filter,
        time_filter=time_filter,
    )

    match goal.metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            result = calculate_avg_productivity_level(
                filtered_specs=filtered_specs,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            )
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            result = calculate_total_activity_duration_seconds(
                filtered_specs=filtered_specs,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            )
        case _:
            raise ValueError(f"Unsupported goal metric: {goal.metric}")

    eval_state, eval_state_reason = await calculate_eval_state(
        conn=conn,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        period_end_utc=period_end_utc,
    )

    success = determine_success(
        goal=goal, definition=definition, result=result, is_full_period=is_full_period
    )
    result = GoalResult(
        goal_definition_id=definition.id,
        period_start=period_start_utc,
        period_end=period_end_utc,
        metric_value=result,
        success=success,
        eval_state=eval_state,
        eval_state_reason=eval_state_reason,
    )
    return result


# Time period helpers (weeks start on Monday)


def get_current_period_bounds(
    period: str | GoalPeriod, tz_str: str, now_utc: datetime
) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_str)
    now_local = now_utc.astimezone(tz)
    p = period.value if isinstance(period, GoalPeriod) else period
    if p == "day":
        start_local = datetime.combine(now_local.date(), time.min).replace(tzinfo=tz)
    elif p == "week":
        monday = now_local.date() - timedelta(days=now_local.weekday())
        start_local = datetime.combine(monday, time.min).replace(tzinfo=tz)
    elif p == "month":
        # Keep tz-aware datetime at first day of month 00:00
        start_local = now_local.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        raise ValueError(f"Unknown period: {period}")
    return start_local.astimezone(timezone.utc), now_utc


def last_complete_periods(
    period: str | GoalPeriod, tz_str: str, now_utc: datetime, n: int
) -> list[tuple[datetime, datetime]]:
    tz = ZoneInfo(tz_str)
    now_local = now_utc.astimezone(tz)
    p = period.value if isinstance(period, GoalPeriod) else period
    out: list[tuple[datetime, datetime]] = []
    if p == "day":
        for i in range(n):
            d = now_local.date() - timedelta(days=i + 1)
            s = datetime.combine(d, time.min).replace(tzinfo=tz)
            e = datetime.combine(d, time.max).replace(tzinfo=tz)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
    elif p == "week":
        this_monday = now_local.date() - timedelta(days=now_local.weekday())
        for i in range(n):
            start_date = this_monday - timedelta(weeks=i + 1)
            end_date = start_date + timedelta(days=6)
            s = datetime.combine(start_date, time.min).replace(tzinfo=tz)
            e = datetime.combine(end_date, time.max).replace(tzinfo=tz)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
    elif p == "month":
        y = now_local.year
        m = now_local.month
        for i in range(n):
            mm = m - (i + 1)
            yy = y
            while mm <= 0:
                mm += 12
                yy -= 1
            s = datetime(yy, mm, 1, 0, 0, 0, tzinfo=tz)
            if mm == 12:
                nm = datetime(yy + 1, 1, 1, 0, 0, 0, tzinfo=tz)
            else:
                nm = datetime(yy, mm + 1, 1, 0, 0, 0, tzinfo=tz)
            e = nm - timedelta(seconds=1)
            out.append((s.astimezone(timezone.utc), e.astimezone(timezone.utc)))
    else:
        raise ValueError(f"Unknown period: {period}")
    return out


def is_progress_stale(
    updated_at_utc: datetime | None, now_utc: datetime, ttl_seconds: int = 60
) -> bool:
    if updated_at_utc is None:
        return True
    return (now_utc - updated_at_utc).total_seconds() > ttl_seconds


async def calculate_goal_progress_current(
    *,
    goal: DBGoal,
    definition: DBGoalDefinition,
    include_tags: list[DBTag] | None,
    exclude_tags: list[DBTag] | None,
    start_utc: datetime,
    end_utc: datetime,
    conn: aiosqlite.Connection,
) -> GoalResult:
    """Compute a partial-period GoalResult between start_utc and end_utc.

    Reuses calculation logic; sets is_full_period=False.
    """
    # Build a GoalResult by reusing the same code paths: we emulate date boundaries via exact datetimes
    # Prepare filters and compute based on metric
    include_tag_ids = [t.id for t in (include_tags or []) if t.id is not None] or None
    exclude_tag_ids = [t.id for t in (exclude_tags or []) if t.id is not None] or None
    include_mode = (
        definition.include_mode.value
        if hasattr(definition.include_mode, "value")
        else definition.include_mode
    )
    productivity_levels = [
        p.value if hasattr(p, "value") else p
        for p in (definition.productivity_filter or [])
    ]
    # Convert time filters to UTC HH:MM using the goal definition's timezone
    goal_tz = ZoneInfo(goal.timezone)
    if definition.time_filter:
        time_filter = []
        for start_str, end_str in definition.time_filter:
            start_h, start_m = map(int, start_str.split(":")[:2])
            end_h, end_m = map(int, end_str.split(":")[:2])
            start_local = datetime.combine(
                datetime.today(), time(start_h, start_m)
            ).replace(tzinfo=goal_tz)
            end_local = datetime.combine(datetime.today(), time(end_h, end_m)).replace(
                tzinfo=goal_tz
            )
            start_utc_hm = start_local.astimezone(timezone.utc).time().strftime("%H:%M")
            end_utc_hm = end_local.astimezone(timezone.utc).time().strftime("%H:%M")
            time_filter.append((start_utc_hm, end_utc_hm))
    else:
        time_filter = None

    day_filter = (
        [str(d) for d in (definition.day_filter or [])]
        if definition.day_filter
        else None
    )

    filtered_specs: list[
        DBActivitySpecWithTags
    ] = await get_filtered_activity_specs_for_goal(
        conn=conn,
        start=start_utc,
        end=end_utc,
        include_tag_ids=include_tag_ids,
        exclude_tag_ids=exclude_tag_ids,
        include_mode=include_mode,
        productivity_levels=productivity_levels,
        day_filter=day_filter,
        time_filter=time_filter,
    )

    match goal.metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            metric_val = calculate_avg_productivity_level(
                filtered_specs=filtered_specs,
                period_start_utc=start_utc,
                period_end_utc=end_utc,
            )
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            metric_val = calculate_total_activity_duration_seconds(
                filtered_specs=filtered_specs,
                period_start_utc=start_utc,
                period_end_utc=end_utc,
            )
        case _:
            raise ValueError(f"Unsupported goal metric: {goal.metric}")

    eval_state, eval_state_reason = await calculate_eval_state(
        conn=conn,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        period_end_utc=end_utc,
    )
    success = determine_success(
        goal=goal, definition=definition, result=metric_val, is_full_period=False
    )

    return GoalResult(
        goal_definition_id=definition.id,
        period_start=start_utc,
        period_end=end_utc,
        metric_value=metric_val,
        success=success,
        eval_state=eval_state,
        eval_state_reason=eval_state_reason,
    )


async def update_current_progress_for_goal(
    conn: aiosqlite.Connection,
    goal: DBGoal,
    definition: DBGoalDefinition,
    include_tags: list[DBTag] | None,
    exclude_tags: list[DBTag] | None,
    now_utc: datetime,
) -> None:
    # If goal is currently paused, skip computing current progress.
    if await is_goal_paused_at(conn, goal_id=goal.id, at_utc=now_utc):
        logger.info(
            f"Goal {goal.id} is paused at {now_utc.isoformat()}, skipping current progress update."
        )
        return

    start_utc, end_utc = get_current_period_bounds(goal.period, goal.timezone, now_utc)
    res = await calculate_goal_progress_current(
        goal=goal,
        definition=definition,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        start_utc=start_utc,
        end_utc=end_utc,
        conn=conn,
    )
    await upsert_goal_progress_current(
        conn,
        goal_definition_id=definition.id,
        period_start_utc=res.period_start,
        period_end_utc=res.period_end,
        metric_value=float(res.metric_value)
        if isinstance(res.metric_value, (int, float))
        else 0.0,
        success=res.success,
        eval_state=res.eval_state,
        eval_state_reason=res.eval_state_reason,
        updated_at_utc=now_utc,
    )


async def update_current_progress_job(goal_id: int, ttl: timedelta) -> None:
    """Background job: recompute current progress for a goal if stale.

    Behavior:
    - Find the most recently created goal_definition for the goal.
    - Check goal_progress_current.updated_at for that definition; if present and fresh (now - updated_at <= ttl), log and return.
    - Otherwise, compute current progress and upsert.
    """
    async with get_db_connection(commit_on_exit=True, start_transaction=True) as conn:
        # Early-exit freshness check for the latest definition's current-progress row
        latest_updated_at = await select_latest_progress_updated_at_for_goal(
            conn, goal_id=goal_id
        )
        now_utc = datetime.now(timezone.utc)
        if latest_updated_at is not None:
            age = now_utc - latest_updated_at
            if age <= ttl:
                # Fresh enough; do nothing
                return

        # Resolve latest definition id for this goal
        latest_def_id = await select_latest_goal_definition_id_for_goal(
            conn, goal_id=goal_id
        )
        if latest_def_id is None:
            return

        # Build Goal object using latest definition
        gwr = await select_goal_with_latest_definition_by_definition_id(
            conn, goal_definition_id=latest_def_id
        )
        if gwr is None:
            return
        await update_current_progress_for_goal(
            conn=conn,
            goal=gwr.goal,
            definition=gwr.definition,
            include_tags=gwr.include_tags,
            exclude_tags=gwr.exclude_tags,
            now_utc=now_utc,
        )


async def update_previous_full_period_goal_result_job(goal_id: int) -> None:
    """Compute and insert the last completed period's goal result.

    Uses the goal definition that was active at the end of that period. If the
    goal does not yet have a full period since creation, this is a no-op.
    """
    now_utc = datetime.now(timezone.utc)
    logger.info(
        f"[goals] Recomputing previous full-period result for goal_id={goal_id}"
    )
    async with get_db_connection(commit_on_exit=True, start_transaction=True) as conn:
        # Find the currently latest definition to recover base goal shape (period/tz/op)
        latest_def_id = await select_latest_goal_definition_id_for_goal(
            conn, goal_id=goal_id
        )
        if latest_def_id is None:
            logger.debug(
                f"[goals] No goal definitions found; skipping previous full-period recompute for goal_id={goal_id}"
            )
            return
        gwr_latest = await select_goal_with_latest_definition_by_definition_id(
            conn, goal_definition_id=latest_def_id
        )
        if gwr_latest is None:
            logger.warning(
                f"[goals] Latest goal definition (id={latest_def_id}) missing details; skipping for goal_id={goal_id}"
            )
            return

        goal = gwr_latest.goal
        # Identify the most recent completed period in the goal's timezone
        periods = last_complete_periods(goal.period, goal.timezone, now_utc, n=1)
        if not periods:
            # No full period yet
            logger.debug(
                f"[goals] No fully completed period yet; skipping goal_id={goal_id}"
            )
            return
        period_start_utc, period_end_utc = periods[0]
        goal_tz = ZoneInfo(goal.timezone)
        period_label = (
            goal.period.value if hasattr(goal.period, "value") else goal.period
        )
        period_start_local = period_start_utc.astimezone(goal_tz).date()
        period_end_local = period_end_utc.astimezone(goal_tz).date()

        logger.info(
            f"[goals] Computing previous full-period result for goal_id={goal_id} "
            f"period={period_label} period_start_local={period_start_local} "
            f"period_end_local={period_end_local} period_start_utc={period_start_utc.isoformat()} "
            f"period_end_utc={period_end_utc.isoformat()}"
        )

        # Resolve the definition active at the end of that period
        gwr_active = await select_goal_with_definition_active_at(
            conn, goal_id=goal_id, active_at_utc=period_end_utc
        )
        if gwr_active is None:
            logger.debug(
                f"[goals] No active definition at period end ({period_end_utc.isoformat()}); skipping goal_id={goal_id}"
            )
            return

        # If goal was paused at the end of that period, insert a PAUSED placeholder result
        if await is_goal_paused_at(conn, goal_id=goal_id, at_utc=period_end_utc):
            logger.info(
                f"[goals] Goal paused at period end; inserting PAUSED result for goal_id={goal_id} "
                f"period={period_label} period_start={period_start_utc.isoformat()} "
                f"period_end={period_end_utc.isoformat()}"
            )
            await insert_goal_result(
                conn,
                goal_definition_id=gwr_active.definition.id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
                metric_value=0.0,
                success=None,
                eval_state=EvalState.PAUSED,
                eval_state_reason="Goal paused at period end",
            )
            return

        # Compute full-period result using the correct definition and tags
        full_res = await calculate_goal_result(
            goal=goal,
            definition=gwr_active.definition,
            include_tags=gwr_active.include_tags,
            exclude_tags=gwr_active.exclude_tags,
            period_start=period_start_local,
            period_end=period_end_local,
            conn=conn,
            is_full_period=True,
        )

        # Persist into goal_results idempotently
        logger.info(
            f"[goals] Upserting previous full-period result for goal_id={goal_id} "
            f"goal_definition_id={gwr_active.definition.id} period={period_label} "
            f"period_start={full_res.period_start.isoformat()} "
            f"period_end={full_res.period_end.isoformat()} "
            f"metric_value={float(full_res.metric_value)} success={full_res.success}"
        )
        await insert_goal_result(
            conn,
            goal_definition_id=gwr_active.definition.id,
            period_start_utc=full_res.period_start,
            period_end_utc=full_res.period_end,
            metric_value=float(full_res.metric_value),
            success=full_res.success,
            eval_state=full_res.eval_state,
            eval_state_reason=full_res.eval_state_reason,
        )
