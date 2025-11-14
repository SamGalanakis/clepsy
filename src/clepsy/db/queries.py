from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
import json
from typing import Any, List, Optional, Sequence, cast

import aiosqlite
from loguru import logger

from clepsy.auth.auth import decrypt_secret
from clepsy.config import config
from clepsy.entities import (
    AADS,
    Activity,
    ActivityEventInsert,
    Aggregation,
    AnthropicConfig,
    AvgProductivityOperators,
    CandidateSession,
    CandidateSessionToActivity,
    DBActivity,
    DBActivityEvent,
    DBActivitySpec,
    DBActivitySpecWithTags,
    DBActivitySpecWithTagsAndSessions,
    DBActivityWithLatestEvent,
    DBAggregation,
    DBAvgProductivityGoal,
    DBAvgProductivityGoalDefinition,
    DBCandidateSession,
    DBCandidateSessionSpec,
    DBDeviceSource,
    DBGoal,
    DBGoalDefinition,
    DBGoalResult,
    DBScheduledJob,
    DBSession,
    DBSessionizationRun,
    DBTag,
    DBTotalActivityDurationGoal,
    DBTotalActivityDurationGoalDefinition,
    EvalState,
    GoalMetric,
    GoalPeriod,
    GoalProgressCurrent,
    GoalWithLatestResult,
    GoogleAIConfig,
    ImageProcessingApproach,
    IncludeMode,
    JobType,
    MetricOperator,
    ModelProvider,
    OpenAIConfig,
    OpenAIGenericConfig,
    ProductivityGoalProgressCurrent,
    ProductivityLevel,
    ScheduledJob,
    ScheduleStatus,
    Session,
    SessionizationRun,
    SourceEnrollmentCode,
    SourceStatus,
    SourceType,
    Tag,
    TagMapping,
    TotalActivityDurationGoalProgressCurrent,
    TotalActivityDurationOperators,
    UserSettings,
)


async def get_filtered_activity_specs_for_goal(
    conn: aiosqlite.Connection,
    start: datetime,
    end: datetime,
    include_tag_ids: Optional[List[int]] = None,
    exclude_tag_ids: Optional[List[int]] = None,
    include_mode: str = "any",
    productivity_levels: Optional[List[str]] = None,
    day_filter: Optional[List[str]] = None,
    time_filter: Optional[List[tuple[str, str]]] = None,
) -> List[DBActivitySpecWithTags]:
    """
    Get activity specs with tags, filtered by time, tags, productivity, day, and time filters as much as possible in SQL.
    - include_tag_ids: only include activities with these tags (all or any, per include_mode)
    - exclude_tag_ids: exclude activities with any of these tags
    - productivity_levels: only include activities with these productivity levels
    - day_filter: only include activities with events on these weekdays (e.g. ["monday", ...])
    - time_filter: only include activities with events overlapping these time ranges (list of (start, end) in HH:MM:SS)
    """
    # Build base query
    query = """
    SELECT a.id AS activity_id, a.name, a.description, a.productivity_level, a.source, a.last_manual_action_time AS activity_last_manual_action_time,
           e.id AS event_id, e.event_time, e.event_type, e.aggregation_id, e.last_manual_action_time AS event_last_manual_action_time
    FROM activities a
    JOIN activity_events e ON a.id = e.activity_id
    LEFT JOIN tag_mappings tm ON a.id = tm.activity_id
    LEFT JOIN tags t ON tm.tag_id = t.id AND t.deleted_at IS NULL
    WHERE datetime(e.event_time) >= datetime(?) AND datetime(e.event_time) <= datetime(?)
    """
    params: list[Any] = [start, end]
    # Productivity filter
    if productivity_levels:
        query += (
            " AND a.productivity_level IN ("
            + ",".join(["?"] * len(productivity_levels))
            + ")"
        )
        params.extend(productivity_levels)
    # Exclude tags
    if exclude_tag_ids:
        query += (
            " AND a.id NOT IN (SELECT activity_id FROM tag_mappings WHERE tag_id IN ("
            + ",".join(["?"] * len(exclude_tag_ids))
            + "))"
        )
        params.extend(exclude_tag_ids)
    # Include tags (any or all)
    if include_tag_ids:
        if include_mode == "all":
            for tag_id in include_tag_ids:
                query += " AND a.id IN (SELECT activity_id FROM tag_mappings WHERE tag_id = ?)"
                params.append(tag_id)
        else:
            query += (
                " AND a.id IN (SELECT activity_id FROM tag_mappings WHERE tag_id IN ("
                + ",".join(["?"] * len(include_tag_ids))
                + "))"
            )
            params.extend(include_tag_ids)
    # Day filter (event weekday)
    if day_filter:
        # SQLite: strftime('%w', e.event_time) gives 0=Sunday ... 6=Saturday
        weekday_map = {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }
        weekday_nums = [
            str(weekday_map[d.lower()]) for d in day_filter if d.lower() in weekday_map
        ]
        if weekday_nums:
            query += (
                " AND CAST(strftime('%w', e.event_time) AS INTEGER) IN ("
                + ",".join(["?"] * len(weekday_nums))
                + ")"
            )
            params.extend(weekday_nums)
    # Time filter (event time overlaps any range)
    if time_filter:
        # Each time range is (start, end) in HH:MM:SS
        time_clauses = []
        for start_str, end_str in time_filter:
            time_clauses.append("(time(e.event_time) >= ? AND time(e.event_time) <= ?)")
            params.extend([start_str, end_str])
        if time_clauses:
            query += " AND (" + " OR ".join(time_clauses) + ")"
    # Run query and group by activity
    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    grouped = defaultdict(list)
    for row in rows:
        activity_id = row["activity_id"]
        grouped[activity_id].append(row)
    # Now fetch tags for each activity
    activity_ids = list(grouped.keys())
    tags_by_activity = {}
    if activity_ids:
        placeholders = ",".join("?" for _ in activity_ids)
        tag_query = f"""
        SELECT a.id AS activity_id, t.id AS tag_id, t.name, t.description
        FROM activities a
        LEFT JOIN tag_mappings tm ON a.id = tm.activity_id
        LEFT JOIN tags t ON tm.tag_id = t.id AND t.deleted_at IS NULL
        WHERE a.id IN ({placeholders})
        """
        async with conn.execute(tag_query, activity_ids) as cursor:
            tag_rows = await cursor.fetchall()
        for row in tag_rows:
            activity_id = row["activity_id"]
            tag_id = row["tag_id"]
            if activity_id not in tags_by_activity:
                tags_by_activity[activity_id] = []
            if tag_id is not None:
                tag = DBTag(id=tag_id, name=row["name"], description=row["description"])
                tags_by_activity[activity_id].append(tag)
    # Build DBActivitySpecWithTags objects
    result = []
    for activity_id, rows in grouped.items():
        db_activity = DBActivity(
            id=activity_id,
            name=rows[0]["name"],
            description=rows[0]["description"],
            productivity_level=rows[0]["productivity_level"],
            source=rows[0]["source"],
            last_manual_action_time=rows[0]["activity_last_manual_action_time"],
        )
        events = []
        for row in rows:
            db_activity_event = DBActivityEvent(
                event_time=row["event_time"],
                event_type=row["event_type"],
                id=row["event_id"],
                activity_id=activity_id,
                aggregation_id=row["aggregation_id"],
                last_manual_action_time=row["event_last_manual_action_time"],
            )
            events.append(db_activity_event)
        tags = tags_by_activity.get(activity_id, [])
        spec_with_tags = DBActivitySpecWithTags(
            activity=db_activity, events=events, tags=tags
        )
        result.append(spec_with_tags)
    return result


def row_to_scheduled_job(row: aiosqlite.Row) -> DBScheduledJob:
    payload_raw = row["payload"]
    payload: dict[str, Any] | None = None
    if payload_raw is not None:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            logger.warning(
                "Scheduled job {} has invalid payload JSON; ignoring payload",
                row["id"],
            )

    enabled_value = row["enabled"]
    enabled = (
        bool(enabled_value) if not isinstance(enabled_value, bool) else enabled_value
    )

    status_value = row["status"]
    try:
        status = ScheduleStatus(status_value)
    except ValueError:
        logger.warning(
            "Scheduled job {} has unknown status '{}'; defaulting to idle",
            row["id"],
            status_value,
        )
        status = ScheduleStatus.IDLE

    job_type_value = row["job_type"]
    try:
        job_type = JobType(job_type_value)
    except ValueError as exc:
        raise ValueError(
            f"Scheduled job {row['id']} has unknown job_type '{job_type_value}'"
        ) from exc

    return DBScheduledJob(
        id=row["id"],
        schedule_key=row["schedule_key"],
        job_type=job_type,
        cron_expr=row["cron_expr"],
        next_run_at=row["next_run_at"],
        enabled=enabled,
        payload=payload,
        running_count=row["running_count"],
        max_concurrent=row["max_concurrent"],
        last_started_at=row["last_started_at"],
        status=status,
    )


async def upsert_scheduled_job(
    conn: aiosqlite.Connection,
    *,
    job: ScheduledJob,
) -> DBScheduledJob:
    payload_json = json.dumps(job.payload) if job.payload is not None else None
    cursor = await conn.execute(
        """
        INSERT INTO scheduled_jobs (
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        )
        VALUES (:schedule_key, :job_type, :cron_expr, :next_run_at, :enabled, :payload, :running_count, :max_concurrent, :last_started_at, :status)
        ON CONFLICT(schedule_key) DO UPDATE SET
            job_type = excluded.job_type,
            cron_expr = excluded.cron_expr,
            next_run_at = CASE
                WHEN scheduled_jobs.next_run_at > excluded.next_run_at THEN scheduled_jobs.next_run_at
                ELSE excluded.next_run_at
            END,
            enabled = excluded.enabled,
            payload = excluded.payload,
            max_concurrent = excluded.max_concurrent
        RETURNING
            id,
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        """,
        {
            "schedule_key": job.schedule_key,
            "job_type": job.job_type.value,
            "cron_expr": job.cron_expr,
            "next_run_at": job.next_run_at,
            "enabled": 1 if job.enabled else 0,
            "payload": payload_json,
            "running_count": job.running_count,
            "max_concurrent": job.max_concurrent,
            "last_started_at": job.last_started_at,
            "status": job.status.value,
        },
    )

    row = await cursor.fetchone()
    assert row is not None, "scheduled_job upsert did not return a row"
    return row_to_scheduled_job(row)


async def select_scheduled_job_by_id(
    conn: aiosqlite.Connection, *, schedule_id: int
) -> DBScheduledJob | None:
    async with conn.execute(
        """
        SELECT
            id,
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        FROM scheduled_jobs
        WHERE id = :schedule_id
        """,
        {"schedule_id": schedule_id},
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return row_to_scheduled_job(row)


async def select_scheduled_job_by_key(
    conn: aiosqlite.Connection, *, schedule_key: str
) -> DBScheduledJob | None:
    async with conn.execute(
        """
        SELECT
            id,
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        FROM scheduled_jobs
        WHERE schedule_key = :schedule_key
        """,
        {"schedule_key": schedule_key},
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return row_to_scheduled_job(row)


async def select_due_scheduled_jobs(
    conn: aiosqlite.Connection,
    *,
    now: datetime,
    include_disabled: bool = False,
    limit: int | None = None,
) -> list[DBScheduledJob]:
    query = """
        SELECT
            id,
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        FROM scheduled_jobs
        WHERE enabled = 1
          AND next_run_at <= :now
          AND running_count < max_concurrent
    """

    if not include_disabled:
        query += "\n          AND status != 'disabled'"

    query += "\n        ORDER BY next_run_at ASC, id ASC"

    params: dict[str, Any] = {"now": now}

    if limit is not None:
        query += "\n        LIMIT :limit"
        params["limit"] = limit

    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()

    return [row_to_scheduled_job(row) for row in rows]


async def select_next_scheduled_run_after(
    conn: aiosqlite.Connection,
    *,
    now: datetime,
) -> datetime | None:
    async with conn.execute(
        """
        SELECT
            next_run_at
        FROM scheduled_jobs
        WHERE enabled = 1
          AND status != 'disabled'
          AND next_run_at > :now
        ORDER BY next_run_at ASC, id ASC
        LIMIT 1
        """,
        {"now": now},
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return row["next_run_at"]


async def release_timed_out_scheduled_jobs(
    conn: aiosqlite.Connection,
    *,
    timeout_threshold: datetime,
    now: datetime,
) -> list[DBScheduledJob]:
    async with conn.execute(
        """
        UPDATE scheduled_jobs
        SET
            running_count = 0,
            status = 'error',
            next_run_at = CASE
                WHEN next_run_at <= :now THEN next_run_at
                ELSE :now
            END
        WHERE running_count > 0
          AND last_started_at IS NOT NULL
          AND last_started_at <= :timeout_threshold
          AND status != 'disabled'
        RETURNING
            id,
            schedule_key,
            job_type,
            cron_expr,
            next_run_at,
            enabled,
            payload,
            running_count,
            max_concurrent,
            last_started_at,
            status
        """,
        {"timeout_threshold": timeout_threshold, "now": now},
    ) as cursor:
        rows = await cursor.fetchall()

    return [row_to_scheduled_job(row) for row in rows]


async def mark_scheduled_job_started(
    conn: aiosqlite.Connection,
    *,
    schedule_id: int,
    expected_next_run_at: datetime,
    started_at: datetime,
    new_next_run_at: datetime,
) -> bool:
    cursor = await conn.execute(
        """
        UPDATE scheduled_jobs
        SET
            running_count = running_count + 1,
            last_started_at = :started_at,
            next_run_at = :new_next_run_at,
            status = CASE WHEN status = 'disabled' THEN status ELSE 'idle' END
        WHERE id = :schedule_id
          AND enabled = 1
          AND status != 'disabled'
          AND running_count < max_concurrent
          AND next_run_at = :expected_next_run_at
        """,
        {
            "schedule_id": schedule_id,
            "started_at": started_at,
            "new_next_run_at": new_next_run_at,
            "expected_next_run_at": expected_next_run_at,
        },
    )

    return cursor.rowcount == 1


async def decrement_scheduled_job_running_count(
    conn: aiosqlite.Connection,
    *,
    schedule_id: int,
    new_status: ScheduleStatus | None = None,
) -> None:
    set_clauses = [
        "running_count = CASE WHEN running_count > 0 THEN running_count - 1 ELSE 0 END"
    ]
    params: dict[str, Any] = {"schedule_id": schedule_id}

    if new_status is not None:
        set_clauses.append("status = :status")
        params["status"] = new_status.value

    sql = """
        UPDATE scheduled_jobs
        SET {set_clause}
        WHERE id = :schedule_id
    """.format(set_clause=", ".join(set_clauses))

    await conn.execute(sql, params)


async def delete_scheduled_job_by_key(
    conn: aiosqlite.Connection, *, schedule_key: str
) -> None:
    await conn.execute(
        "DELETE FROM scheduled_jobs WHERE schedule_key = :schedule_key",
        {"schedule_key": schedule_key},
    )


async def is_goal_paused_at(
    conn: aiosqlite.Connection, *, goal_id: int, at_utc: datetime
) -> bool:
    """Return True if the goal is paused at the given UTC timestamp.

    Looks up the last pause/resume event at or before the timestamp; if it's a
    'pause' event, consider the goal paused; otherwise not paused. If no event
    exists, it's considered active (not paused).
    """
    async with conn.execute(
        """
        SELECT event_type
        FROM goal_pause_events
        WHERE goal_id = ? AND datetime(at) <= datetime(?)
        ORDER BY datetime(at) DESC, id DESC
        LIMIT 1
        """,
        (goal_id, at_utc),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return False
    try:
        return row["event_type"] == "pause"
    except (KeyError, TypeError, IndexError):
        # Fallback for row indexing differences
        return (row[0] if row else None) == "pause"


async def select_tags_by_ids(
    conn: aiosqlite.Connection, tag_ids: List[int], include_deleted: bool = False
) -> list[dict]:
    """
    Select tags by a list of IDs. If include_deleted is True, include soft-deleted tags.
    Returns a list of dicts with id, name, description, and deleted_at.
    """
    if not tag_ids:
        return []
    placeholders = ",".join(["?"] * len(tag_ids))
    query = (
        f"SELECT id, name, description, deleted_at FROM tags WHERE id IN ({placeholders})"
        if include_deleted
        else f"SELECT id, name, description, deleted_at FROM tags WHERE id IN ({placeholders}) AND deleted_at IS NULL"
    )
    async with conn.execute(query, tag_ids) as cursor:
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@lru_cache
def simple_insert_query(
    table_name: str, columns: tuple[str], returning_columns: tuple[str] = tuple()
) -> str:
    insert_statemnent = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({','.join([f':{col}' for col in columns])})"
    if returning_columns:
        return f"{insert_statemnent} RETURNING {','.join(returning_columns)};"
    else:
        return f"{insert_statemnent};"


@lru_cache
def set_clause_query(table_name: str, columns: tuple[str]) -> str:
    return f"UPDATE {table_name} SET {','.join([f'{col} = :{col}' for col in columns])}"


# (source_events moved to Valkey Streams; DB helpers removed)


async def insert_user_settings(
    conn: aiosqlite.Connection,
    timezone: str,
    username: str,
    image_processing_approach: str = ImageProcessingApproach.OCR.value,
    image_model_provider: str = "",
    image_model_base_url: str | None = None,
    image_model: str = "",
    image_model_api_key_enc: bytes | None = None,
    text_model_provider: str = "",
    text_model_base_url: str | None = None,
    text_model: str = "",
    text_model_api_key_enc: bytes | None = None,
    productivity_prompt: str = "",
) -> None:
    sql = simple_insert_query(
        "user_settings",
        (
            "timezone",
            "image_processing_approach",
            "image_model_provider",
            "image_model_base_url",
            "image_model",
            "image_model_api_key_enc",
            "text_model_provider",
            "text_model_base_url",
            "text_model",
            "text_model_api_key_enc",
            "username",
            "productivity_prompt",  # Add column name
        ),
    )

    await conn.execute(
        sql,
        {
            "timezone": timezone,
            "image_processing_approach": image_processing_approach,
            "image_model_provider": image_model_provider,
            "image_model_base_url": image_model_base_url,
            "image_model": image_model,
            "image_model_api_key_enc": image_model_api_key_enc,
            "text_model_provider": text_model_provider,
            "text_model_base_url": text_model_base_url,
            "text_model": text_model,
            "text_model_api_key_enc": text_model_api_key_enc,
            "username": username,
            "productivity_prompt": productivity_prompt,  # Add parameter value
        },
    )


def build_user_settings_from_row(row: Any) -> UserSettings:
    """Construct a UserSettings object (with decrypted API keys) from a DB row.

    Expects columns:
        username, timezone,
    image_processing_approach,
    image_model_provider, image_model_base_url, image_model, image_model_api_key_enc,
    text_model_provider, text_model_base_url, text_model, text_model_api_key_enc,
    productivity_prompt
    """
    # Decrypt image model key (if present)
    if row["image_model_api_key_enc"]:
        try:
            image_model_api_key = decrypt_secret(
                row["image_model_api_key_enc"],
                config.master_key.get_secret_value(),
                aad=AADS.LLM_API_KEY,
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to decrypt image model API key, did you change the master key?"
            ) from exc
    else:
        image_model_api_key = None

    # Decrypt text model key (if present)
    if row["text_model_api_key_enc"]:
        try:
            text_model_api_key = decrypt_secret(
                row["text_model_api_key_enc"],
                config.master_key.get_secret_value(),
                aad=AADS.LLM_API_KEY,
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to decrypt text model API key, did you change the master key?"
            ) from exc
    else:
        text_model_api_key = None

    # Determine the correct provider class based on the model_provider string
    image_provider = row["image_model_provider"]
    if image_provider == ModelProvider.GOOGLE_AI:
        image_model_config = GoogleAIConfig(
            model_base_url=row["image_model_base_url"],
            model=row["image_model"],
            api_key=image_model_api_key,
        )
    elif image_provider == ModelProvider.OPENAI:
        image_model_config = OpenAIConfig(
            model_base_url=row["image_model_base_url"],
            model=row["image_model"],
            api_key=image_model_api_key,
        )
    elif image_provider == ModelProvider.OPENAI_GENERIC:
        image_model_config = OpenAIGenericConfig(
            model_base_url=row["image_model_base_url"],
            model=row["image_model"],
            api_key=image_model_api_key,
        )
    elif image_provider == ModelProvider.ANTHROPIC:
        image_model_config = AnthropicConfig(
            model_base_url=row["image_model_base_url"],
            model=row["image_model"],
            api_key=image_model_api_key,
        )
    else:
        raise ValueError(f"Unknown image model provider: {image_provider}")

    # Determine the correct provider class based on the model_provider string
    text_provider = row["text_model_provider"]
    if text_provider == ModelProvider.GOOGLE_AI:
        text_model_config = GoogleAIConfig(
            model_base_url=row["text_model_base_url"],
            model=row["text_model"],
            api_key=text_model_api_key,
        )
    elif text_provider == ModelProvider.OPENAI:
        text_model_config = OpenAIConfig(
            model_base_url=row["text_model_base_url"],
            model=row["text_model"],
            api_key=text_model_api_key,
        )
    elif text_provider == ModelProvider.OPENAI_GENERIC:
        text_model_config = OpenAIGenericConfig(
            model_base_url=row["text_model_base_url"],
            model=row["text_model"],
            api_key=text_model_api_key,
        )
    elif text_provider == ModelProvider.ANTHROPIC:
        text_model_config = AnthropicConfig(
            model_base_url=row["text_model_base_url"],
            model=row["text_model"],
            api_key=text_model_api_key,
        )
    else:
        raise ValueError(f"Unknown text model provider: {text_provider}")

    image_processing_approach = ImageProcessingApproach(
        row["image_processing_approach"]
    )

    return UserSettings(
        timezone=row["timezone"],
        image_model_config=image_model_config,
        text_model_config=text_model_config,
        username=row["username"],
        productivity_prompt=row["productivity_prompt"],
        image_processing_approach=image_processing_approach,
    )


async def select_user_settings(conn) -> UserSettings | None:
    async with conn.execute(
        """SELECT username, timezone,
           image_processing_approach,
           image_model_provider, image_model_base_url, image_model, image_model_api_key_enc,
           text_model_provider, text_model_base_url, text_model, text_model_api_key_enc,
           productivity_prompt
           FROM user_settings LIMIT 1"""
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return build_user_settings_from_row(row)


async def select_user_auth(conn: aiosqlite.Connection) -> Optional[dict]:
    async with conn.execute(
        "SELECT id, password_hash, created_at FROM user_auth WHERE id='default' LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_user_password(conn: aiosqlite.Connection, password_hash: str) -> None:
    logger.debug("Updating password for user")
    sql = "UPDATE user_auth SET password_hash = :password_hash WHERE id='default'"
    params = {"password_hash": password_hash}
    try:
        await conn.execute(sql, params)
        logger.info("Password updated successfully for user")
    except Exception as e:  # noqa: BLE001 - propagate as runtime error with context
        raise RuntimeError("Error updating password for user") from e


async def create_user_auth(conn: aiosqlite.Connection, password_hash: str) -> None:
    sql = "INSERT INTO user_auth (id, password_hash) VALUES ('default', :password_hash)"
    try:
        await conn.execute(sql, {"password_hash": password_hash})
        logger.info("Initialized user_auth with bootstrap password")
    except Exception as e:
        raise RuntimeError("Error initializing user_auth") from e


async def get_user_settings_draft(
    conn: aiosqlite.Connection, *, wizard_id: str
) -> dict | None:
    async with conn.execute(
        """
        SELECT *
        FROM user_settings_draft
        WHERE wizard_id = ?
        LIMIT 1
        """,
        (wizard_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_user_settings_draft_basics(
    conn: aiosqlite.Connection,
    *,
    wizard_id: str,
    username: str,
    timezone: str,
    description: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO user_settings_draft (
            wizard_id, username, timezone, description
        ) VALUES (:wizard_id, :username, :timezone, :description)
        ON CONFLICT(wizard_id) DO UPDATE SET
            username = excluded.username,
            timezone = excluded.timezone,
            description = excluded.description
        """,
        {
            "wizard_id": wizard_id,
            "username": username,
            "timezone": timezone,
            "description": description,
        },
    )


async def update_user_settings_draft_productivity(
    conn: aiosqlite.Connection, *, wizard_id: str, productivity_prompt: str
) -> None:
    await conn.execute(
        """
        INSERT INTO user_settings_draft (wizard_id, productivity_prompt)
        VALUES (:wizard_id, :productivity_prompt)
        ON CONFLICT(wizard_id) DO UPDATE SET
            productivity_prompt = excluded.productivity_prompt
        """,
        {"wizard_id": wizard_id, "productivity_prompt": productivity_prompt},
    )


async def update_user_settings_draft_tags(
    conn: aiosqlite.Connection, *, wizard_id: str, tags_json: str | None
) -> None:
    await conn.execute(
        """
        INSERT INTO user_settings_draft (wizard_id, tags_json)
        VALUES (:wizard_id, :tags_json)
        ON CONFLICT(wizard_id) DO UPDATE SET
            tags_json = excluded.tags_json
        """,
        {"wizard_id": wizard_id, "tags_json": tags_json},
    )


async def update_user_settings_draft_llm_configs(
    conn: aiosqlite.Connection,
    *,
    wizard_id: str,
    image_model_provider: str | None,
    image_model_base_url: str | None,
    image_model: str | None,
    image_model_api_key_enc: bytes | None,
    text_model_provider: str | None,
    text_model_base_url: str | None,
    text_model: str | None,
    text_model_api_key_enc: bytes | None,
    image_processing_approach: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO user_settings_draft (
            wizard_id,
            image_model_provider,
            image_model_base_url,
            image_model,
            image_model_api_key_enc,
            text_model_provider,
            text_model_base_url,
            text_model,
            text_model_api_key_enc,
            image_processing_approach
        ) VALUES (
            :wizard_id,
            :image_model_provider,
            :image_model_base_url,
            :image_model,
            :image_model_api_key_enc,
            :text_model_provider,
            :text_model_base_url,
            :text_model,
            :text_model_api_key_enc,
            :image_processing_approach
        )
        ON CONFLICT(wizard_id) DO UPDATE SET
            image_model_provider = excluded.image_model_provider,
            image_model_base_url = excluded.image_model_base_url,
            image_model = excluded.image_model,
            image_model_api_key_enc = excluded.image_model_api_key_enc,
            text_model_provider = excluded.text_model_provider,
            text_model_base_url = excluded.text_model_base_url,
            text_model = excluded.text_model,
            text_model_api_key_enc = excluded.text_model_api_key_enc,
            image_processing_approach = excluded.image_processing_approach
        """,
        {
            "wizard_id": wizard_id,
            "image_model_provider": image_model_provider,
            "image_model_base_url": image_model_base_url,
            "image_model": image_model,
            "image_model_api_key_enc": image_model_api_key_enc,
            "text_model_provider": text_model_provider,
            "text_model_base_url": text_model_base_url,
            "text_model": text_model,
            "text_model_api_key_enc": text_model_api_key_enc,
            "image_processing_approach": (
                image_processing_approach or ImageProcessingApproach.OCR.value
            ),
        },
    )


async def delete_user_settings_draft(
    conn: aiosqlite.Connection, *, wizard_id: str
) -> None:
    await conn.execute(
        "DELETE FROM user_settings_draft WHERE wizard_id = ?", (wizard_id,)
    )


async def finalize_user_settings_from_draft(
    conn: aiosqlite.Connection, *, wizard_id: str
) -> None:
    """Promote draft to user_settings and create initial tags if provided.

    Assumes that no user_settings row exists yet (single-user system).
    """
    draft = await get_user_settings_draft(conn, wizard_id=wizard_id)
    if not draft:
        raise ValueError("Draft not found")

    username = (draft.get("username") or "").strip()
    if not username:
        raise ValueError("Username is required to finalize account creation")

    # Insert user_settings
    await insert_user_settings(
        conn=conn,
        timezone=(draft.get("timezone") or "UTC"),
        image_processing_approach=(
            draft.get("image_processing_approach") or ImageProcessingApproach.OCR.value
        ),
        image_model_provider=(draft.get("image_model_provider") or ""),
        image_model_base_url=(draft.get("image_model_base_url") or None),
        image_model=(draft.get("image_model") or ""),
        image_model_api_key_enc=(draft.get("image_model_api_key_enc") or None),
        text_model_provider=(draft.get("text_model_provider") or ""),
        text_model_base_url=(draft.get("text_model_base_url") or None),
        text_model=(draft.get("text_model") or ""),
        text_model_api_key_enc=(draft.get("text_model_api_key_enc") or None),
        username=username,
        productivity_prompt=(draft.get("productivity_prompt") or ""),
    )

    # Create initial tags if provided
    try:
        tags_json = draft.get("tags_json")
        if tags_json:
            data = json.loads(tags_json)
            if isinstance(data, list) and data:
                # Prepare rows for bulk insert
                rows = []
                for item in data:
                    name = (item or {}).get("name") or ""
                    description = (item or {}).get("description") or ""
                    if name.strip():
                        rows.append({"name": name.strip(), "description": description})
                if rows:
                    sql = simple_insert_query("tags", ("name", "description"))
                    await conn.executemany(sql, rows)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.exception(
            "Failed to parse or insert initial tags from draft: {error}",
            error=exc,
        )

    # Remove the draft
    await delete_user_settings_draft(conn, wizard_id=wizard_id)


async def update_user_settings(
    conn: aiosqlite.Connection, settings: dict[str, Any]
) -> UserSettings:
    """
    Update user settings from a dictionary and return the full user_settings row
    using a RETURNING clause. Password changes should be handled separately.

    Returns the updated UserSettings object, or None if no row was updated.
    """
    if "password" in settings:
        raise ValueError("Password updates are not allowed through this function.")
    assert settings, "update_user_settings called with no settings to update."

    logger.debug(f"Updating user settings with keys: {list(settings.keys())}")

    # Build the SET clause dynamically from the dictionary keys
    set_clause = ", ".join(f"{key} = :{key}" for key in settings.keys())

    # Explicitly list columns to return to build a proper UserSettings
    returning_cols = (
        "username, timezone, image_processing_approach, "
        "image_model_provider, image_model_base_url, image_model, image_model_api_key_enc, "
        "text_model_provider, text_model_base_url, text_model, text_model_api_key_enc, "
        "productivity_prompt"
    )

    sql = f"UPDATE user_settings SET {set_clause} RETURNING {returning_cols}"

    params = {**settings}

    try:
        cursor = await conn.execute(sql, params)
        row = await cursor.fetchone()
        assert row is not None, "No user_settings row returned after update."

        updated = build_user_settings_from_row(row)

        logger.debug("User settings updated successfully with RETURNING")
        return updated
    except Exception as exc:
        logger.exception("Error updating user settings: {error}", error=exc)
        raise

    # Note: update_user_password moved above to user_auth section


async def insert_activity_events(
    conn: aiosqlite.Connection, events: Sequence[ActivityEventInsert]
) -> None:
    # Use INSERT OR IGNORE to provide idempotency when a unique index exists
    # on (activity_id, event_time, event_type). This prevents duplicate events
    # from causing IntegrityError on retries or replays.
    sql = (
        "INSERT OR IGNORE INTO activity_events (activity_id,event_time,event_type,aggregation_id,last_manual_action_time) "
        "VALUES (:activity_id,:event_time,:event_type,:aggregation_id,:last_manual_action_time);"
    )

    dicts = [
        {
            "activity_id": event.activity_id,
            "event_time": event.event_time,
            "event_type": event.event_type,
            "aggregation_id": event.aggregation_id,
            "last_manual_action_time": event.last_manual_action_time,
        }
        for event in events
    ]
    await conn.executemany(sql, dicts)


async def select_open_activities_with_last_event(
    conn: aiosqlite.Connection,
) -> list[DBActivityWithLatestEvent]:
    query = """
    SELECT
    a.id, a.name, a.description, a.productivity_level, a.source, -- Select specific columns
        a.last_manual_action_time AS activity_last_manual_action_time, -- Alias activity time
        le.event_type AS state,
        le.event_time,
        le.aggregation_id,
        le.id AS last_event_id,
        ag.start_time as aggregation_start_time,
        ag.end_time as aggregation_end_time,
        ag.first_timestamp as aggregation_first_timestamp,
        ag.last_timestamp as aggregation_last_timestamp,
        le.last_manual_action_time AS event_last_manual_action_time -- Alias event time

    FROM activities a
    JOIN (
        SELECT *
        FROM activity_events ae
        WHERE ae.id = (
            SELECT ae2.id
            FROM activity_events ae2
            WHERE ae2.activity_id = ae.activity_id
            ORDER BY ae2.event_time DESC
            LIMIT 1
        )
    ) le ON le.activity_id = a.id
    LEFT JOIN aggregations ag ON le.aggregation_id = ag.id
    WHERE le.event_type <> 'close';
    """

    return_list = []
    async with conn.execute(query) as cursor:
        rows = await cursor.fetchall()
    for row in rows:
        db_activity = DBActivity(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            productivity_level=row["productivity_level"],
            source=row["source"],  # Assign source here
            last_manual_action_time=row[
                "activity_last_manual_action_time"
            ],  # Use aliased activity time
            # source=row["source"], # Removed source from here
        )

        db_activity_event = DBActivityEvent(
            event_time=row["event_time"],
            event_type=row["state"],
            id=row["last_event_id"],
            activity_id=row["id"],
            aggregation_id=row["aggregation_id"],
            last_manual_action_time=row[
                "event_last_manual_action_time"
            ],  # Use aliased event time
        )
        latest_aggregation = DBAggregation(
            id=row["aggregation_id"],
            start_time=row["aggregation_start_time"],
            end_time=row["aggregation_end_time"],
            first_timestamp=row["aggregation_first_timestamp"],
            last_timestamp=row["aggregation_last_timestamp"],
        )
        return_list.append(
            DBActivityWithLatestEvent(
                activity=db_activity,
                latest_event=db_activity_event,
                latest_aggregation=latest_aggregation,
            )
        )
    return return_list


async def select_open_auto_activities_with_last_event(
    conn: aiosqlite.Connection,
) -> list[DBActivityWithLatestEvent]:
    query = """
    SELECT
    a.id, a.name, a.description, a.productivity_level, a.source, -- Select specific columns
        a.last_manual_action_time AS activity_last_manual_action_time, -- Alias activity time
        le.event_type AS state,
        le.event_time,
        le.aggregation_id,
        le.id AS last_event_id,
        ag.start_time as aggregation_start_time,
        ag.end_time as aggregation_end_time,
        ag.first_timestamp as aggregation_first_timestamp,
        ag.last_timestamp as aggregation_last_timestamp,
        le.last_manual_action_time AS event_last_manual_action_time -- Alias event time

    FROM activities a
    JOIN (
        SELECT *
        FROM activity_events ae
        WHERE ae.id = (
            SELECT ae2.id
            FROM activity_events ae2
            WHERE ae2.activity_id = ae.activity_id
            ORDER BY ae2.event_time DESC
            LIMIT 1
        )
    ) le ON le.activity_id = a.id
    LEFT JOIN aggregations ag ON le.aggregation_id = ag.id
    WHERE le.event_type <> 'close' AND a.source = 'auto';
    """

    return_list = []
    async with conn.execute(query) as cursor:
        rows = await cursor.fetchall()
    for row in rows:
        db_activity = DBActivity(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            productivity_level=row["productivity_level"],
            source=row["source"],  # Assign source here
            last_manual_action_time=row[
                "activity_last_manual_action_time"
            ],  # Use aliased activity time
        )

        db_activity_event = DBActivityEvent(
            event_time=row["event_time"],
            event_type=row["state"],
            id=row["last_event_id"],
            activity_id=row["id"],
            aggregation_id=row["aggregation_id"],
            last_manual_action_time=row[
                "event_last_manual_action_time"
            ],  # Use aliased event time
        )
        latest_aggregation = DBAggregation(
            id=row["aggregation_id"],
            start_time=row["aggregation_start_time"],
            end_time=row["aggregation_end_time"],
            first_timestamp=row["aggregation_first_timestamp"],
            last_timestamp=row["aggregation_last_timestamp"],
        )
        return_list.append(
            DBActivityWithLatestEvent(
                activity=db_activity,
                latest_event=db_activity_event,
                latest_aggregation=latest_aggregation,
            )
        )
    return return_list


async def insert_activities(
    conn: aiosqlite.Connection, activities: list[Activity]
) -> list[int]:
    if not activities:
        return []

    sql = simple_insert_query(
        "activities",
        (
            "name",
            "description",
            "productivity_level",
            "source",
            "last_manual_action_time",
        ),
    )

    insert_dicts = [
        {
            "name": activity.name,
            "description": activity.description,
            "productivity_level": activity.productivity_level,
            "source": activity.source,
            "last_manual_action_time": activity.last_manual_action_time,
        }
        for activity in activities
    ]

    await conn.executemany(sql, insert_dicts)

    max_id_cursor = await conn.execute(
        f"SELECT id FROM activities ORDER BY id DESC LIMIT {len(activities)}"
    )
    max_id_rows = await max_id_cursor.fetchall()
    assert max_id_rows is not None, "No activities were inserted"
    ids = [row["id"] for row in max_id_rows]
    ids.reverse()

    return ids


async def insert_aggregation(
    conn: aiosqlite.Connection, aggregation: Aggregation
) -> int:
    sql = simple_insert_query(
        "aggregations", ("start_time", "end_time", "first_timestamp", "last_timestamp")
    )

    cursor = await conn.execute(
        sql,
        {key: val for key, val in aggregation.model_dump().items() if key != "id"},
    )
    last_row_id = cursor.lastrowid
    assert last_row_id is not None, "No row was inserted"
    return last_row_id


async def get_specs_after_cutoff(
    conn: aiosqlite.Connection, cutoff: datetime
) -> list[DBActivitySpec]:
    query = """
    SELECT a.id AS activity_id,
                   a.name,
                   a.description,
                   a.productivity_level,
                   a.source, -- Select source
                   a.last_manual_action_time AS activity_last_manual_action_time, -- Alias
                   e.id AS event_id,
                   e.event_time,
                   e.event_type,
                   e.aggregation_id,
                   e.last_manual_action_time AS event_last_manual_action_time -- Alias

            FROM activities a
            JOIN activity_events e ON a.id = e.activity_id
            WHERE datetime(e.event_time) >= datetime(?);
    """

    # WHERE datetime(e.event_time) >= datetime(?)
    async with conn.execute(query, (cutoff,)) as cursor:
        rows = await cursor.fetchall()
    grouped = defaultdict(list)
    for row in rows:
        activity_id = row["activity_id"]
        grouped[activity_id].append(row)
    return_list = []

    for activity_id, rows in grouped.items():
        db_activity = DBActivity(
            id=activity_id,
            name=rows[0]["name"],
            description=rows[0]["description"],
            productivity_level=rows[0]["productivity_level"],
            source=rows[0]["source"],  # Assign source here
            last_manual_action_time=rows[0][
                "activity_last_manual_action_time"
            ],  # Use aliased activity time
            # source=rows[0]["source"], # Removed source from here
        )

        events = []
        for row in rows:
            db_activity_event = DBActivityEvent(
                event_time=row["event_time"],
                event_type=row["event_type"],
                id=row["event_id"],
                activity_id=activity_id,
                aggregation_id=row["aggregation_id"],
                last_manual_action_time=row[
                    "event_last_manual_action_time"
                ],  # Use aliased event time
            )
            events.append(db_activity_event)

        db_activity_spec = DBActivitySpec(activity=db_activity, events=events)

        return_list.append(db_activity_spec)

    return return_list


async def select_tags(
    conn: aiosqlite.Connection, include_deleted: bool = False
) -> list[DBTag]:
    """Select tags.

    By default, excludes soft-deleted tags (deleted_at IS NULL).
    Set include_deleted=True to return all tags regardless of deleted_at.
    """
    query = (
        "SELECT id, name, description FROM tags"
        if include_deleted
        else "SELECT id, name, description FROM tags WHERE deleted_at IS NULL"
    )

    try:
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        tags = [
            DBTag(id=row["id"], name=row["name"], description=row["description"])
            for row in rows
        ]

        logger.trace(f"Selected {len(tags)} tags from database")
        for tag in tags:
            logger.trace(
                f"  - Tag {tag.id}: name='{tag.name}', description='{tag.description}'"
            )

        return tags
    except Exception as exc:
        logger.exception("Error selecting tags: {error}", error=exc)
        raise


async def insert_tags(conn: aiosqlite.Connection, tags: list[Tag]) -> list[int]:
    if not tags:
        return []

    try:
        sql = simple_insert_query("tags", ("name", "description"))

        insert_dicts = [
            {
                "name": tag.name or "",  # Ensure name is never None
                "description": tag.description
                or "",  # Ensure description is never None
            }
            for tag in tags
        ]

        for i, tag_dict in enumerate(insert_dicts):
            logger.debug(f"Inserting tag {i}: {tag_dict}")

        await conn.executemany(sql, insert_dicts)

        # Fetch the IDs of the newly inserted tags
        max_id_cursor = await conn.execute(
            f"SELECT id FROM tags ORDER BY id DESC LIMIT {len(tags)}"
        )
        max_id_rows = await max_id_cursor.fetchall()
        assert max_id_rows is not None, "No tags were inserted"
        ids = [row["id"] for row in max_id_rows]
        ids.reverse()  # Reverse to match the order of the input tags

        logger.info(f"Inserted {len(ids)} tags with IDs: {ids}")
        return ids

    except Exception as exc:
        logger.exception("Error inserting tags: {error}", error=exc)
        raise


async def update_tags(conn: aiosqlite.Connection, tags: list[DBTag]) -> None:
    if not tags:
        return

    try:
        # All DBTag instances have IDs, so no need to filter
        valid_tags = tags

        # Prepare statement and parameters for executemany
        update_params = [
            (
                tag.name,
                tag.description or "",
                tag.id,
            )  # Ensure description is never None
            for tag in valid_tags
        ]

        logger.debug(f"Updating {len(valid_tags)} tags")
        for tag in valid_tags:
            logger.debug(
                f"  - Updating tag {tag.id}: name='{tag.name}', description='{tag.description}'"
            )

        # Use named placeholders for clarity
        query = "UPDATE tags SET name = ?, description = ? WHERE id = ?"
        await conn.executemany(query, update_params)

        # Verify the updates took effect
        for tag in valid_tags:
            verify_query = "SELECT name, description FROM tags WHERE id = ?"
            async with conn.execute(verify_query, (tag.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    logger.debug(
                        f"  - Verified tag {tag.id}: name='{row['name']}', description='{row['description']}'"
                    )

    except Exception as exc:
        logger.exception("Error updating tags: {error}", error=exc)
        raise


async def delete_tags(conn: aiosqlite.Connection, tag_ids: list[int]) -> None:
    """Soft-delete multiple tags by their IDs by setting deleted_at.

    Note: existing UNIQUE constraint on tags.name remains; soft-deleted rows
    still occupy their names. Consider adjusting uniqueness in a follow-up
    migration if you need to re-create tags with the same name after delete.
    """
    if not tag_ids:
        return

    # Use IN clause with placeholders
    placeholders = ",".join("?" for _ in tag_ids)
    await conn.execute(
        f"UPDATE tags SET deleted_at = datetime('now') WHERE deleted_at IS NULL AND id IN ({placeholders})",
        tuple(tag_ids),
    )


async def bulk_upsert_tags(
    conn: aiosqlite.Connection,
    tags_to_update: list[DBTag],
    tags_to_insert: list[Tag],
    ids_to_delete: list[int],
) -> list[int]:
    """Perform bulk tag operations (update, insert, delete) in a single transaction

    Returns the IDs of the newly inserted tags.
    """
    try:
        logger.debug(
            f"Bulk upsert: updating {len(tags_to_update)} tags, "
            + f"inserting {len(tags_to_insert)} tags, "
            + f"deleting {len(ids_to_delete)} tags"
        )

        # Delete tags in bulk
        if ids_to_delete:
            await delete_tags(conn, ids_to_delete)

        # Update tags in bulk
        if tags_to_update:
            await update_tags(conn, tags_to_update)

        # Insert tags in bulk
        new_ids = []
        if tags_to_insert:
            new_ids = await insert_tags(conn, tags_to_insert)

        return new_ids

    except Exception as exc:
        logger.exception("Error in bulk_upsert_tags: {error}", error=exc)
        # Still do rollback on error
        await conn.rollback()
        raise


async def insert_tag_mappings(
    conn: aiosqlite.Connection, mappings: list[TagMapping]
) -> list[int]:
    if not mappings:
        return []

    try:
        sql = simple_insert_query("tag_mappings", ("tag_id", "activity_id"))

        insert_dicts = [
            {
                "tag_id": mapping.tag_id,
                "activity_id": mapping.activity_id,
            }
            for mapping in mappings
        ]

        logger.trace(f"Inserting {len(mappings)} tag mappings")
        for mapping in mappings:
            logger.trace(
                f"  - Mapping activity {mapping.activity_id} to tag {mapping.tag_id}"
            )

        await conn.executemany(sql, insert_dicts)

        # Get the IDs of newly inserted mappings
        max_id_cursor = await conn.execute(
            f"SELECT id FROM tag_mappings ORDER BY id DESC LIMIT {len(mappings)}"
        )
        max_id_rows = await max_id_cursor.fetchall()
        assert max_id_rows is not None, "No tag mappings were inserted"
        ids = [row["id"] for row in max_id_rows]
        ids.reverse()  # Reverse to match the order of the input mappings

        logger.trace(f"Inserted {len(ids)} tag mappings with IDs: {ids}")
        return ids

    except Exception as exc:
        logger.exception("Error inserting tag mappings: {error}", error=exc)
        raise


async def delete_tag_mappings(
    conn: aiosqlite.Connection, activity_id: int, tag_ids: list[int]
) -> None:
    if not tag_ids:
        return

    # Use IN clause with placeholders
    placeholders = ",".join("?" for _ in tag_ids)
    await conn.execute(
        f"DELETE FROM tag_mappings WHERE activity_id = ? AND tag_id IN ({placeholders})",
        (activity_id, *tag_ids),
    )


async def delete_activity(conn: aiosqlite.Connection, activity_id: int) -> None:
    # Deletes an activity by its ID. Assumes related events/tags are handled by CASCADE.
    # Note: Ensure foreign keys in activity_events and tag_mappings have ON DELETE CASCADE
    await conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    # No explicit commit needed if the caller manages the transaction


async def update_activity(
    conn: aiosqlite.Connection,
    activity_id: int,
    key_value_pairs: dict[str, Any],
):
    keys = tuple(key_value_pairs.keys())

    base_query = set_clause_query("activities", keys)

    query_dict = {**key_value_pairs, "id": activity_id}

    query = f"""
    {base_query}
    WHERE id = :id;
    """
    await conn.execute(query, query_dict)


async def delete_activity_events(
    conn: aiosqlite.Connection, activity_ids: list[int]
) -> None:
    await conn.execute(
        f"DELETE FROM activity_events WHERE activity_id IN ({','.join(['?'] * len(activity_ids))})",
        tuple(activity_ids),
    )


async def select_activity_spec_with_tags(
    conn: aiosqlite.Connection, activity_id: int
) -> DBActivitySpecWithTags:
    # Query to get the specific activity and its events
    activity_query = """
    SELECT a.id AS activity_id,
           a.name,
           a.description,
           a.productivity_level,
           a.source, -- Select source
           a.last_manual_action_time AS activity_last_manual_action_time, -- Alias
           e.id AS event_id,
           e.event_time,
           e.event_type,
           e.aggregation_id,
           e.last_manual_action_time AS event_last_manual_action_time -- Alias
    FROM activities a
    JOIN activity_events e ON a.id = e.activity_id
    WHERE a.id = ?;
    """

    async with conn.execute(activity_query, (activity_id,)) as cursor:
        rows = await cursor.fetchall()
        activity_rows = list(rows)

    if not activity_rows:
        raise ValueError(f"No activity found with ID {activity_id}")

    # Process the activity and its events
    activity_data = activity_rows[0]

    db_activity = DBActivity(
        id=activity_id,
        name=activity_data["name"],
        description=activity_data["description"],
        productivity_level=activity_data["productivity_level"],
        source=activity_data["source"],  # Assign source here
        last_manual_action_time=activity_data[
            "activity_last_manual_action_time"
        ],  # Use aliased activity time
        # source=activity_data["source"], # Removed source from here
    )

    events = []
    for row in activity_rows:
        db_activity_event = DBActivityEvent(
            event_time=row["event_time"],
            event_type=row["event_type"],
            id=row["event_id"],
            activity_id=activity_id,
            aggregation_id=row["aggregation_id"],
            last_manual_action_time=row[
                "event_last_manual_action_time"
            ],  # Use aliased event time
        )
        events.append(db_activity_event)

    # Query to get tags for this specific activity
    tags_query = """
    SELECT t.id AS tag_id, t.name, t.description
    FROM tags t
    JOIN tag_mappings tm ON t.id = tm.tag_id
    WHERE tm.activity_id = ? AND t.deleted_at IS NULL;
    """
    tags = []
    async with conn.execute(tags_query, (activity_id,)) as cursor:
        tag_rows = await cursor.fetchall()
        for row in tag_rows:
            assert row["tag_id"] is not None, "Tag ID cannot be None"
            tags.append(
                DBTag(
                    id=row["tag_id"], name=row["name"], description=row["description"]
                )
            )

    # Combine into the final spec object
    spec_with_tags = DBActivitySpecWithTags(
        activity=db_activity, events=events, tags=tags
    )

    return spec_with_tags


async def select_goals_with_latest_definition(
    conn: aiosqlite.Connection,
    last_successes_limit: int = 5,
) -> list[GoalWithLatestResult]:
    """Return all goals with their current definition, include/exclude tags,
    the latest result (if any), and last N success booleans using a single DB call.

    - Respects tag soft-deletes (only includes tags where t.deleted_at IS NULL).
    - Maps DB string fields to enums in entities, with lenient fallbacks.
    """
    query = """
    WITH latest_defs AS (
        SELECT gd.*
        FROM goal_definitions gd
        JOIN (
            SELECT goal_id, MAX(effective_from) AS max_eff
            FROM goal_definitions
            WHERE datetime(effective_from) <= datetime('now')
            GROUP BY goal_id
        ) m ON m.goal_id = gd.goal_id AND m.max_eff = gd.effective_from
    ),
    top_results AS (
        SELECT *
        FROM (
            SELECT r.*,
                   ROW_NUMBER() OVER (
                       PARTITION BY r.goal_definition_id
                       ORDER BY r.period_start DESC, r.id DESC
                   ) AS rn
            FROM goal_results r
        )
        WHERE rn <= :limit
    ),
    last_pe AS (
        SELECT goal_id, event_type, at,
               ROW_NUMBER() OVER (PARTITION BY goal_id ORDER BY datetime(at) DESC, id DESC) rn
        FROM goal_pause_events
    )
    SELECT
        -- Goal fields
    g.id                AS goal_id,
        CASE WHEN lpe.event_type = 'pause' THEN lpe.at ELSE NULL END AS goal_paused_since,
        g.created_at        AS goal_created_at,
        g.metric            AS metric,
        g.operator          AS operator,
        g.period            AS period,
        g.timezone          AS timezone,

        -- Definition fields
        ld.id                      AS def_id,
        ld.goal_id                 AS goal_id_for_def,
        ld.name                    AS def_name,
        ld.description             AS def_description,
        ld.metric_params_json      AS metric_params_json,
        ld.target_value            AS target_value,
        ld.include_mode            AS include_mode,
        ld.day_filter_json         AS day_filter_json,
        ld.time_filter_json        AS time_filter_json,
        ld.productivity_filter_json AS productivity_filter_json,
        ld.effective_from          AS effective_from,
        ld.created_at              AS def_created_at,

        -- Tag fields
        t.id                AS tag_id,
        t.name              AS tag_name,
        t.description       AS tag_description,
        gt.role             AS tag_role,

        -- Top results (last N), with rn=1 being latest
        tr.id               AS res_id,
        tr.period_start     AS res_period_start,
        tr.period_end       AS res_period_end,
        tr.metric_value     AS res_metric_value,
        tr.success          AS res_success,
        tr.eval_state       AS res_eval_state,
        tr.eval_state_reason AS res_eval_state_reason,
        tr.created_at       AS res_created_at,
        tr.rn               AS res_rn
    FROM goals g
    JOIN latest_defs ld ON ld.goal_id = g.id
    LEFT JOIN last_pe lpe ON lpe.goal_id = g.id AND lpe.rn = 1
    LEFT JOIN goal_tags gt ON gt.goal_definition_id = ld.id
    LEFT JOIN tags t ON t.id = gt.tag_id AND t.deleted_at IS NULL
    LEFT JOIN top_results tr ON tr.goal_definition_id = ld.id
    ORDER BY g.id, ld.id, t.id, res_rn
    """

    async with conn.execute(query, {"limit": last_successes_limit}) as cursor:
        rows = await cursor.fetchall()

    if not rows:
        return []

    # Aggregate per goal and definition
    results_by_goal: dict[int, dict[str, Any]] = {}
    seen_tag_include: dict[int, set[int]] = {}
    seen_tag_exclude: dict[int, set[int]] = {}
    seen_success_rn: dict[int, set[int]] = {}

    for r in rows:
        goal_id = r["goal_id"]
        def_id = r["def_id"]

        # Initialize structures for this goal if first time
        if goal_id not in results_by_goal:
            # Build goal object
            metric = GoalMetric(r["metric"])  # may raise if invalid
            op = (
                MetricOperator(r["operator"]) if r["operator"] else MetricOperator.EQUAL
            )
            period = GoalPeriod(r["period"]) if r["period"] else GoalPeriod.DAY

            def _coerce_operator(m: GoalMetric, opx: MetricOperator) -> MetricOperator:
                if m in (
                    GoalMetric.AVG_PRODUCTIVITY_LEVEL,
                    GoalMetric.TOTAL_ACTIVITY_DURATION,
                ):
                    return (
                        opx
                        if opx
                        in (MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN)
                        else MetricOperator.GREATER_THAN
                    )
                return opx

            op = _coerce_operator(metric, op)

            if metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
                goal_obj: DBGoal = DBAvgProductivityGoal(
                    id=goal_id,
                    created_at=r["goal_created_at"],
                    paused_since=r["goal_paused_since"],
                    timezone=r["timezone"],
                    period=period,
                    operator=cast(AvgProductivityOperators, op),
                )
            else:
                goal_obj = DBTotalActivityDurationGoal(
                    id=goal_id,
                    created_at=r["goal_created_at"],
                    paused_since=r["goal_paused_since"],
                    timezone=r["timezone"],
                    period=period,
                    operator=cast(TotalActivityDurationOperators, op),
                )

            # Build definition from row
            def_row = {
                "id": r["def_id"],
                "goal_id": r["goal_id_for_def"],
                "name": r["def_name"],
                "description": r["def_description"],
                "metric_params_json": r["metric_params_json"],
                "target_value": r["target_value"],
                "include_mode": r["include_mode"],
                "day_filter_json": r["day_filter_json"],
                "time_filter_json": r["time_filter_json"],
                "productivity_filter_json": r["productivity_filter_json"],
                "effective_from": r["effective_from"],
                "created_at": r["def_created_at"],
                # These are used by row_to_goal_definition()
                "metric": r["metric"],
                "operator": r["operator"],
                "period": r["period"],
                "timezone": r["timezone"],
            }
            definition = row_to_goal_definition(def_row)

            results_by_goal[goal_id] = {
                "goal": goal_obj,
                "definition": definition,
                "include_tags": [],
                "exclude_tags": [],
                "latest_result": None,
                "last_successes": [],
            }
            seen_tag_include[goal_id] = set()
            seen_tag_exclude[goal_id] = set()
            seen_success_rn[goal_id] = set()

        # Accumulate tags (dedupe)
        if r["tag_id"] is not None:
            tag = DBTag(
                id=r["tag_id"], name=r["tag_name"], description=r["tag_description"]
            )
            if r["tag_role"] == "include":
                if r["tag_id"] not in seen_tag_include[goal_id]:
                    results_by_goal[goal_id]["include_tags"].append(tag)
                    seen_tag_include[goal_id].add(r["tag_id"])
            else:
                if r["tag_id"] not in seen_tag_exclude[goal_id]:
                    results_by_goal[goal_id]["exclude_tags"].append(tag)
                    seen_tag_exclude[goal_id].add(r["tag_id"])

        # Accumulate latest_result and last_successes from top_results rows
        rn = r["res_rn"]
        if rn is not None:
            # Latest result (rn == 1)
            if rn == 1 and results_by_goal[goal_id]["latest_result"] is None:
                results_by_goal[goal_id]["latest_result"] = DBGoalResult(
                    id=r["res_id"],
                    goal_definition_id=def_id,
                    period_start=r["res_period_start"],
                    period_end=r["res_period_end"],
                    metric_value=r["res_metric_value"],
                    success=bool(r["res_success"])
                    if r["res_success"] is not None
                    else False,
                    eval_state=EvalState(r["res_eval_state"])
                    if r["res_eval_state"]
                    else EvalState.NA,
                    eval_state_reason=r["res_eval_state_reason"],
                    created_at=r["res_created_at"],
                )
            # Last successes list (dedupe by rn to avoid tag fan-out)
            if (
                last_successes_limit > 0
                and rn not in seen_success_rn[goal_id]
                and len(results_by_goal[goal_id]["last_successes"])
                < last_successes_limit
            ):
                results_by_goal[goal_id]["last_successes"].append(
                    bool(r["res_success"]) if r["res_success"] is not None else False
                )
                seen_success_rn[goal_id].add(rn)

    # Materialize final list in goal id order for stability
    ordered_goal_ids = sorted(results_by_goal.keys())
    final_results: list[GoalWithLatestResult] = []
    for gid in ordered_goal_ids:
        gdict = results_by_goal[gid]
        final_results.append(
            GoalWithLatestResult(
                goal=gdict["goal"],
                definition=gdict["definition"],
                include_tags=gdict["include_tags"],
                exclude_tags=gdict["exclude_tags"],
                latest_result=gdict["latest_result"],
                last_successes=gdict["last_successes"],
            )
        )

    return final_results


async def select_goal_progress_current(
    conn: aiosqlite.Connection, goal_definition_id: int
) -> Optional[GoalProgressCurrent]:
    """Fetch current progress row for a goal definition from goal_progress_current.

    Returns the row or None. Columns: goal_definition_id, period_start, period_end,
    metric_value, success, eval_state, eval_state_reason, updated_at.
    """
    query = """
    SELECT goal_definition_id, period_start, period_end, metric_value,
           success, eval_state, eval_state_reason, updated_at
    FROM goal_progress_current
    WHERE goal_definition_id = ?
    """
    async with conn.execute(query, (goal_definition_id,)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    # Decide variant using the goal's metric from the definition
    # For this query we need the goal metric; fetch from joined goal_definitions/goals
    metric_q = """
    SELECT g.metric AS metric
    FROM goal_definitions gd
    JOIN goals g ON g.id = gd.goal_id
    WHERE gd.id = ?
    """
    async with conn.execute(metric_q, (goal_definition_id,)) as cur:
        mrow = await cur.fetchone()
    metric = (
        GoalMetric(mrow["metric"])
        if mrow is not None
        else GoalMetric.AVG_PRODUCTIVITY_LEVEL
    )

    common = dict(
        goal_definition_id=row["goal_definition_id"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        success=row["success"],
        eval_state=EvalState(row["eval_state"])
        if row["eval_state"] is not None
        else EvalState.NA,
        eval_state_reason=row["eval_state_reason"],
        updated_at=row["updated_at"],
    )

    if metric == GoalMetric.TOTAL_ACTIVITY_DURATION:
        return TotalActivityDurationGoalProgressCurrent(
            metric_value=float(row["metric_value"]), **common
        )  # type: ignore[arg-type]
    else:
        return ProductivityGoalProgressCurrent(
            metric_value=float(row["metric_value"]), **common
        )  # type: ignore[arg-type]


async def upsert_goal_progress_current(
    conn: aiosqlite.Connection,
    *,
    goal_definition_id: int,
    period_start_utc: datetime,
    period_end_utc: datetime,
    metric_value: float,
    success: Optional[bool],
    eval_state: EvalState,
    eval_state_reason: Optional[str],
    updated_at_utc: datetime,
) -> None:
    sql = """
    INSERT INTO goal_progress_current (
        goal_definition_id, period_start, period_end, metric_value,
        success, eval_state, eval_state_reason, updated_at
    ) VALUES (:goal_definition_id, :period_start, :period_end, :metric_value,
              :success, :eval_state, :eval_state_reason, :updated_at)
    ON CONFLICT(goal_definition_id) DO UPDATE SET
        period_start = excluded.period_start,
        period_end = excluded.period_end,
        metric_value = excluded.metric_value,
        success = excluded.success,
        eval_state = excluded.eval_state,
        eval_state_reason = excluded.eval_state_reason,
        updated_at = excluded.updated_at
    """
    await conn.execute(
        sql,
        {
            "goal_definition_id": goal_definition_id,
            "period_start": period_start_utc,
            "period_end": period_end_utc,
            "metric_value": metric_value,
            "success": success,
            "eval_state": eval_state.value,
            "eval_state_reason": eval_state_reason,
            "updated_at": updated_at_utc,
        },
    )


async def select_last_goal_results_for_goal(
    conn: aiosqlite.Connection, *, goal_id: int, limit: int
) -> list[DBGoalResult]:
    """Return the last N goal_results across all definitions for a goal.

    Results are ordered newest first by period_start.
    """
    query = """
    SELECT r.id, r.goal_definition_id, r.period_start, r.period_end,
           r.metric_value, r.success, r.eval_state, r.eval_state_reason, r.created_at
    FROM goal_results r
    JOIN goal_definitions d ON d.id = r.goal_definition_id
    WHERE d.goal_id = ?
    ORDER BY r.period_start DESC
    LIMIT ?
    """
    async with conn.execute(query, (goal_id, limit)) as cursor:
        rows = await cursor.fetchall()
    results: list[DBGoalResult] = []
    for rr in rows:
        results.append(
            DBGoalResult(
                id=rr["id"],
                goal_definition_id=rr["goal_definition_id"],
                period_start=rr["period_start"],
                period_end=rr["period_end"],
                metric_value=rr["metric_value"],
                success=bool(rr["success"]) if rr["success"] is not None else None,
                eval_state=EvalState(rr["eval_state"])
                if rr["eval_state"]
                else EvalState.NA,
                eval_state_reason=rr["eval_state_reason"],
                created_at=rr["created_at"],
            )
        )
    return results


async def select_goal_with_latest_definition_by_definition_id(
    conn: aiosqlite.Connection, *, goal_definition_id: int
) -> Optional[GoalWithLatestResult]:
    # Fetch the definition row
    async with conn.execute(
        """
    SELECT gd.id, gd.goal_id, gd.name, gd.description, gd.metric_params_json,
           gd.target_value, gd.include_mode,
           gd.day_filter_json, gd.time_filter_json, gd.productivity_filter_json,
           gd.effective_from, gd.created_at,
                     g.metric AS metric, g.operator AS operator, g.period AS period, g.timezone AS timezone,
                     g.id AS goal_id_real,
                     (
                         SELECT at FROM goal_pause_events e
                         WHERE e.goal_id = g.id
                         ORDER BY datetime(at) DESC, id DESC
                         LIMIT 1
                     ) AS goal_last_pause_event_at,
                     (
                         SELECT event_type FROM goal_pause_events e
                         WHERE e.goal_id = g.id
                         ORDER BY datetime(at) DESC, id DESC
                         LIMIT 1
                     ) AS goal_last_pause_event_type,
                     g.created_at AS goal_created_at
        FROM goal_definitions gd
        JOIN goals g ON g.id = gd.goal_id
        WHERE gd.id = ?
        """,
        (goal_definition_id,),
    ) as cursor:
        dr = await cursor.fetchone()
    if not dr:
        return None

    # Build DBGoal from the joined row
    metric = GoalMetric(dr["metric"])  # raises on invalid
    operator = (
        MetricOperator(dr["operator"]) if dr["operator"] else MetricOperator.EQUAL
    )
    period = GoalPeriod(dr["period"]) if dr["period"] else GoalPeriod.DAY

    # Coerce operator into allowed set
    def _coerce_operator(m: GoalMetric, op: MetricOperator) -> MetricOperator:
        if m == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            return (
                op
                if op in (MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN)
                else MetricOperator.GREATER_THAN
            )
        if m == GoalMetric.TOTAL_ACTIVITY_DURATION:
            return (
                op
                if op in (MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN)
                else MetricOperator.GREATER_THAN
            )
        return op

    operator = _coerce_operator(metric, operator)
    paused_since_val = (
        dr["goal_last_pause_event_at"]
        if dr["goal_last_pause_event_type"] == "pause"
        else None
    )
    if metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        goal: DBGoal = DBAvgProductivityGoal(
            id=dr["goal_id_real"],
            created_at=dr["goal_created_at"],
            paused_since=paused_since_val,
            timezone=dr["timezone"],
            period=period,
            operator=cast(AvgProductivityOperators, operator),
        )
    else:
        goal = DBTotalActivityDurationGoal(
            id=dr["goal_id_real"],
            created_at=dr["goal_created_at"],
            paused_since=paused_since_val,
            timezone=dr["timezone"],
            period=period,
            operator=cast(TotalActivityDurationOperators, operator),
        )
    # Fetch tags for this def
    async with conn.execute(
        """
        SELECT gt.tag_id, gt.role, t.name, t.description
        FROM goal_tags gt
        JOIN tags t ON t.id = gt.tag_id
        WHERE gt.goal_definition_id = ?
        """,
        (goal_definition_id,),
    ) as cursor:
        tag_rows = await cursor.fetchall()
    include_tags: list[DBTag] = []
    exclude_tags: list[DBTag] = []
    for tr in tag_rows:
        tag = DBTag(id=tr["tag_id"], name=tr["name"], description=tr["description"])
        if tr["role"] == "INCLUDE":
            include_tags.append(tag)
        else:
            exclude_tags.append(tag)

    definition = row_to_goal_definition(dr)
    return GoalWithLatestResult(
        goal=goal,
        definition=definition,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        latest_result=None,
        last_successes=[],
    )


async def select_goal_with_definition_active_at(
    conn: aiosqlite.Connection, *, goal_id: int, active_at_utc: datetime
) -> Optional[GoalWithLatestResult]:
    """Return the goal and the definition in effect at the given UTC timestamp.

    Picks the goal_definition with the greatest effective_from <= active_at_utc.
    Includes include/exclude tags for the chosen definition.
    """
    # Choose the definition active at the provided timestamp
    async with conn.execute(
        """
        WITH chosen AS (
            SELECT gd.*
            FROM goal_definitions gd
            WHERE gd.goal_id = ? AND datetime(gd.effective_from) <= datetime(?)
            ORDER BY gd.effective_from DESC
            LIMIT 1
        )
        SELECT c.id, c.goal_id, c.name, c.description, c.metric_params_json,
               c.target_value, c.include_mode, c.day_filter_json, c.time_filter_json,
               c.productivity_filter_json, c.effective_from, c.created_at,
                             g.metric AS metric, g.operator AS operator, g.period AS period,
                             g.timezone AS timezone,
                             g.id AS goal_id_real,
                             (
                                 SELECT at FROM goal_pause_events e
                                 WHERE e.goal_id = g.id
                                 ORDER BY datetime(at) DESC, id DESC
                                 LIMIT 1
                             ) AS goal_last_pause_event_at,
                             (
                                 SELECT event_type FROM goal_pause_events e
                                 WHERE e.goal_id = g.id
                                 ORDER BY datetime(at) DESC, id DESC
                                 LIMIT 1
                             ) AS goal_last_pause_event_type,
                             g.created_at AS goal_created_at
        FROM chosen c
        JOIN goals g ON g.id = c.goal_id
        """,
        (goal_id, active_at_utc),
    ) as cursor:
        dr = await cursor.fetchone()
    if not dr:
        return None

    # Build DBGoal
    metric = GoalMetric(dr["metric"])  # raises on invalid
    operator = (
        MetricOperator(dr["operator"]) if dr["operator"] else MetricOperator.EQUAL
    )
    period = GoalPeriod(dr["period"]) if dr["period"] else GoalPeriod.DAY

    def _coerce_operator(m: GoalMetric, op: MetricOperator) -> MetricOperator:
        if m == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            return (
                op
                if op in (MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN)
                else MetricOperator.GREATER_THAN
            )
        if m == GoalMetric.TOTAL_ACTIVITY_DURATION:
            return (
                op
                if op in (MetricOperator.LESS_THAN, MetricOperator.GREATER_THAN)
                else MetricOperator.GREATER_THAN
            )
        return op

    operator = _coerce_operator(metric, operator)
    paused_since_val = (
        dr["goal_last_pause_event_at"]
        if dr["goal_last_pause_event_type"] == "pause"
        else None
    )
    if metric == GoalMetric.AVG_PRODUCTIVITY_LEVEL:
        goal: DBGoal = DBAvgProductivityGoal(
            id=dr["goal_id_real"],
            created_at=dr["goal_created_at"],
            paused_since=paused_since_val,
            timezone=dr["timezone"],
            period=period,
            operator=cast(AvgProductivityOperators, operator),
        )
    else:
        goal = DBTotalActivityDurationGoal(
            id=dr["goal_id_real"],
            created_at=dr["goal_created_at"],
            paused_since=paused_since_val,
            timezone=dr["timezone"],
            period=period,
            operator=cast(TotalActivityDurationOperators, operator),
        )

    # Tags for the chosen definition
    async with conn.execute(
        """
        SELECT gt.tag_id, gt.role, t.name, t.description
        FROM goal_tags gt
        JOIN tags t ON t.id = gt.tag_id
        WHERE gt.goal_definition_id = ?
        """,
        (dr["id"],),
    ) as cursor:
        tag_rows = await cursor.fetchall()
    include_tags: list[DBTag] = []
    exclude_tags: list[DBTag] = []
    for tr in tag_rows:
        tag = DBTag(id=tr["tag_id"], name=tr["name"], description=tr["description"])
        if tr["role"] == "INCLUDE":
            include_tags.append(tag)
        else:
            exclude_tags.append(tag)

    definition = row_to_goal_definition(dr)
    return GoalWithLatestResult(
        goal=goal,
        definition=definition,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        latest_result=None,
        last_successes=[],
    )


async def insert_goal_pause_event(
    conn: aiosqlite.Connection, *, goal_id: int, event_type: str, at: datetime
) -> int:
    """Insert a pause/resume event for a goal.

    event_type must be 'pause' or 'resume'. Returns inserted row id.
    """
    assert event_type in ("pause", "resume")
    cursor = await conn.execute(
        """
        INSERT INTO goal_pause_events (goal_id, event_type, at)
        VALUES (:goal_id, :event_type, :at)
        """,
        {"goal_id": goal_id, "event_type": event_type, "at": at},
    )
    rowid = cursor.lastrowid
    assert rowid is not None, "Failed to insert goal pause event"
    return int(rowid)


async def select_latest_goal_definition_id_for_goal(
    conn: aiosqlite.Connection, *, goal_id: int
) -> Optional[int]:
    async with conn.execute(
        """
        SELECT gd.id
        FROM goal_definitions gd
        WHERE gd.goal_id = ?
        ORDER BY gd.created_at DESC
        LIMIT 1
        """,
        (goal_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row["id"] if row else None


async def select_latest_progress_updated_at_for_goal(
    conn: aiosqlite.Connection, *, goal_id: int
) -> Optional[datetime]:
    async with conn.execute(
        """
        SELECT gpc.updated_at AS updated_at
        FROM goal_definitions gd
        LEFT JOIN goal_progress_current gpc ON gpc.goal_definition_id = gd.id
        WHERE gd.goal_id = ?
        ORDER BY gd.created_at DESC
        LIMIT 1
        """,
        (goal_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row["updated_at"] if row else None


async def insert_goal_result(
    conn: aiosqlite.Connection,
    *,
    goal_definition_id: int,
    period_start_utc: datetime,
    period_end_utc: datetime,
    metric_value: float,
    success: Optional[bool],
    eval_state: EvalState,
    eval_state_reason: Optional[str],
) -> int:
    """Insert or update a goal_results row for a definition and period.

    Uses ON CONFLICT(goal_definition_id, period_start) DO UPDATE to be idempotent.
    Returns the lastrowid (may be 0 for updates in SQLite).
    """
    async with conn.execute(
        """
        INSERT INTO goal_results (
            goal_definition_id, period_start, period_end, metric_value,
            success, eval_state, eval_state_reason
        ) VALUES (:goal_definition_id, :period_start, :period_end, :metric_value,
                  :success, :eval_state, :eval_state_reason)
        ON CONFLICT(goal_definition_id, period_start) DO UPDATE SET
            period_end = excluded.period_end,
            metric_value = excluded.metric_value,
            success = excluded.success,
            eval_state = excluded.eval_state,
            eval_state_reason = excluded.eval_state_reason
        """,
        {
            "goal_definition_id": goal_definition_id,
            "period_start": period_start_utc,
            "period_end": period_end_utc,
            "metric_value": float(metric_value),
            "success": (1 if success is True else 0 if success is False else None),
            "eval_state": eval_state.value
            if hasattr(eval_state, "value")
            else str(eval_state),
            "eval_state_reason": eval_state_reason,
        },
    ) as cursor:
        return cursor.lastrowid or 0


def row_to_goal_definition(r: Any) -> DBGoalDefinition:
    # Determine metric from joined row and map include mode and filters
    metric = GoalMetric(r["metric"])  # type: ignore[arg-type]
    include_mode = IncludeMode(r["include_mode"])  # type: ignore[arg-type]
    day_filter = json.loads(r["day_filter_json"]) if r["day_filter_json"] else None
    productivity_filter = None
    if r["productivity_filter_json"]:
        raw = json.loads(r["productivity_filter_json"])  # Expect list of strings
        productivity_filter = [ProductivityLevel(v) for v in raw]
    time_filter = json.loads(r["time_filter_json"]) if r["time_filter_json"] else None

    base_kwargs = {
        "id": r["id"],
        "goal_id": r["goal_id"],
        "name": r["name"],
        "description": r["description"],
        "include_mode": include_mode,
        "day_filter": day_filter,
        "productivity_filter": productivity_filter,
        "effective_from": r["effective_from"],
        "time_filter": time_filter,
    }

    match metric:
        case GoalMetric.AVG_PRODUCTIVITY_LEVEL:
            return DBAvgProductivityGoalDefinition(
                **base_kwargs,
                target_value=r["target_value"],
                metric_params=None,
            )
        case GoalMetric.TOTAL_ACTIVITY_DURATION:
            # Interpret target_value as seconds for duration
            seconds = float(r["target_value"]) if r["target_value"] is not None else 0.0
            return DBTotalActivityDurationGoalDefinition(
                **base_kwargs,
                target_value=timedelta(seconds=seconds),
                metric_params=None,
            )
        case _:
            raise ValueError(f"Unknown goal metric: {metric}")


# ---- Goal inserts ----
async def insert_goal(
    conn: aiosqlite.Connection,
    *,
    metric: GoalMetric,
    operator: MetricOperator,
    period: str,
    timezone: str,
) -> int:
    sql = simple_insert_query("goals", ("metric", "operator", "period", "timezone"))
    cursor = await conn.execute(
        sql,
        {
            "metric": metric.value,
            "operator": operator.value,
            "period": period,
            "timezone": timezone,
        },
    )
    last_row_id = cursor.lastrowid
    assert last_row_id is not None, "No goal row was inserted"
    return int(last_row_id)


async def insert_goal_definition(
    conn: aiosqlite.Connection,
    *,
    goal_id: int,
    name: str,
    description: str | None,
    target_value: float,
    include_mode: IncludeMode,
    day_filter_json: str | None,
    time_filter_json: str | None,
    productivity_filter_json: str | None,
    effective_from: datetime,
    metric_params_json: str | None = None,
) -> int:
    sql = simple_insert_query(
        "goal_definitions",
        (
            "goal_id",
            "name",
            "description",
            "metric_params_json",
            "target_value",
            "include_mode",
            "day_filter_json",
            "time_filter_json",
            "productivity_filter_json",
            "effective_from",
        ),
    )
    cursor = await conn.execute(
        sql,
        {
            "goal_id": goal_id,
            "name": name,
            "description": description,
            "metric_params_json": metric_params_json,
            "target_value": target_value,
            "include_mode": include_mode.value,
            "day_filter_json": day_filter_json,
            "time_filter_json": time_filter_json,
            "productivity_filter_json": productivity_filter_json,
            "effective_from": effective_from,
        },
    )
    last_row_id = cursor.lastrowid
    assert last_row_id is not None, "No goal_definition row was inserted"
    return int(last_row_id)


async def insert_goal_tags(
    conn: aiosqlite.Connection,
    *,
    goal_definition_id: int,
    include_tag_ids: list[int],
    exclude_tag_ids: list[int],
) -> None:
    if not include_tag_ids and not exclude_tag_ids:
        return
    rows: list[dict[str, Any]] = []
    for tid in include_tag_ids:
        rows.append(
            {
                "goal_definition_id": goal_definition_id,
                "tag_id": tid,
                "role": "include",
            }
        )
    for tid in exclude_tag_ids:
        rows.append(
            {
                "goal_definition_id": goal_definition_id,
                "tag_id": tid,
                "role": "exclude",
            }
        )
    sql = simple_insert_query("goal_tags", ("goal_definition_id", "tag_id", "role"))
    await conn.executemany(sql, rows)


async def delete_goal(conn: aiosqlite.Connection, goal_id: int) -> None:
    """Delete a goal by ID. Cascades will remove related definitions, tags, and results.

    Assumes PRAGMA foreign_keys=ON in the connection (set by the DB context manager).
    """
    await conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))


async def update_activity_event(
    conn: aiosqlite.Connection, db_activity_event: DBActivityEvent
) -> None:
    assert db_activity_event.id is not None, "Event ID cannot be None"
    query = """
    UPDATE activity_events
    SET event_time = :event_time,
        event_type = :event_type,
        aggregation_id = :aggregation_id,
        last_manual_action_time = :last_manual_action_time
    WHERE id = :id;
    """
    await conn.execute(
        query,
        {
            "event_time": db_activity_event.event_time,
            "event_type": db_activity_event.event_type,
            "aggregation_id": db_activity_event.aggregation_id,
            "id": db_activity_event.id,
            "last_manual_action_time": db_activity_event.last_manual_action_time,
        },
    )


async def select_specs_in_time_range(
    conn: aiosqlite.Connection, start: datetime, end: datetime
) -> list[DBActivitySpec]:
    activity_ids_query = """
        SELECT DISTINCT a.id
        FROM activities a
        WHERE (
            EXISTS (
                SELECT 1
                FROM activity_events ae
                WHERE ae.activity_id = a.id
                  AND ae.event_type = 'open'
                  AND datetime(ae.event_time) >= datetime(:start)
                  AND datetime(ae.event_time) <= datetime(:end)
            )
            OR (
                SELECT ae.event_type
                FROM activity_events ae
                WHERE ae.activity_id = a.id
                  AND datetime(ae.event_time) < datetime(:start)
                ORDER BY ae.event_time DESC, ae.id DESC
                LIMIT 1
            ) = 'open'
        )
    """

    async with conn.execute(activity_ids_query, {"start": start, "end": end}) as cursor:
        rows = await cursor.fetchall()
        activity_ids = [row["id"] for row in rows]

    if not activity_ids:
        return []

    placeholders = ",".join("?" for _ in activity_ids)
    specs_query = f"""
        SELECT
            a.id AS activity_id,
            a.name,
            a.description,
            a.productivity_level,
            a.source,
            a.last_manual_action_time AS activity_last_manual_action_time,
            e.id AS event_id,
            e.event_time,
            e.event_type,
            e.aggregation_id,
            e.last_manual_action_time AS event_last_manual_action_time
        FROM activities a
        JOIN activity_events e ON a.id = e.activity_id
        WHERE a.id IN ({placeholders})
        ORDER BY a.id, datetime(e.event_time), e.id
    """

    async with conn.execute(specs_query, activity_ids) as cursor:
        rows = await cursor.fetchall()

    grouped: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[row["activity_id"]].append(row)

    specs: list[DBActivitySpec] = []
    for activity_id, activity_rows in grouped.items():
        first_row = activity_rows[0]
        db_activity = DBActivity(
            id=activity_id,
            name=first_row["name"],
            description=first_row["description"],
            productivity_level=first_row["productivity_level"],
            source=first_row["source"],
            last_manual_action_time=first_row["activity_last_manual_action_time"],
        )

        events: list[DBActivityEvent] = []
        for row in activity_rows:
            events.append(
                DBActivityEvent(
                    event_time=row["event_time"],
                    event_type=row["event_type"],
                    id=row["event_id"],
                    activity_id=activity_id,
                    aggregation_id=row["aggregation_id"],
                    last_manual_action_time=row["event_last_manual_action_time"],
                )
            )

        specs.append(DBActivitySpec(activity=db_activity, events=events))

    return specs


async def select_specs_with_tags_in_time_range(
    conn: aiosqlite.Connection, start: datetime, end: datetime
) -> list[DBActivitySpecWithTags]:
    # First get regular activity specs
    activity_specs = await select_specs_in_time_range(conn, start, end)

    # Now fetch tags for each activity
    tags_by_activity = {}

    # Get all activity IDs to look up tags
    activity_ids = [
        spec.activity.id for spec in activity_specs if spec.activity.id is not None
    ]

    if not activity_ids:
        # Return early if there are no activities
        return [
            DBActivitySpecWithTags(**spec.model_dump(), tags=[])
            for spec in activity_specs
        ]

    # Create placeholders for SQL query
    placeholders = ",".join("?" for _ in activity_ids)

    # Query to get all tags for these activities
    query = f"""
    SELECT a.id AS activity_id, t.id AS tag_id, t.name, t.description
    FROM activities a
    LEFT JOIN tag_mappings tm ON a.id = tm.activity_id
    LEFT JOIN tags t ON tm.tag_id = t.id AND t.deleted_at IS NULL
    WHERE a.id IN ({placeholders})
    """

    async with conn.execute(query, activity_ids) as cursor:
        rows = await cursor.fetchall()

    # Group tags by activity
    for row in rows:
        activity_id = row["activity_id"]
        tag_id = row["tag_id"]

        if activity_id not in tags_by_activity:
            tags_by_activity[activity_id] = []
        if tag_id is not None:
            tag = DBTag(id=tag_id, name=row["name"], description=row["description"])
            tags_by_activity[activity_id].append(tag)

    # Combine activities with their tags
    result = []
    for spec in activity_specs:
        activity_id = spec.activity.id
        tags = tags_by_activity.get(activity_id, [])

        # Create enhanced spec with tags
        spec_with_tags = DBActivitySpecWithTags(**spec.model_dump(), tags=tags)
        result.append(spec_with_tags)

    return result


async def select_last_aggregation(conn: aiosqlite.Connection) -> DBAggregation | None:
    query = """
    SELECT id, start_time, end_time, first_timestamp, last_timestamp
    FROM aggregations
    ORDER BY end_time DESC
    LIMIT 1;
    """
    async with conn.execute(query) as cursor:
        row = await cursor.fetchone()
        if row:
            return DBAggregation(
                id=row["id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                first_timestamp=row["first_timestamp"],
                last_timestamp=row["last_timestamp"],
            )


async def select_latest_aggregation(
    conn: aiosqlite.Connection,
) -> DBAggregation | None:
    query = """
    SELECT id, start_time, end_time, first_timestamp, last_timestamp
    FROM aggregations
    ORDER BY end_time DESC
    LIMIT 1;
    """
    async with conn.execute(query) as cursor:
        row = await cursor.fetchone()
        if row:
            return DBAggregation(
                id=row["id"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                first_timestamp=row["first_timestamp"],
                last_timestamp=row["last_timestamp"],
            )
    return None


async def select_sources(conn: aiosqlite.Connection) -> list[DBDeviceSource]:
    query = """
    SELECT id, name, source_type, status, token_hash, last_seen, created_at
    FROM sources
    ORDER BY (last_seen IS NULL), datetime(last_seen) DESC, id DESC
    """
    async with conn.execute(query) as cursor:
        rows = await cursor.fetchall()
    result: list[DBDeviceSource] = []
    for row in rows:
        result.append(
            DBDeviceSource(
                id=row["id"],
                name=row["name"],
                source_type=SourceType(row["source_type"]),
                status=SourceStatus(row["status"]),
                token_hash=row["token_hash"],
                last_seen=row["last_seen"],
                created_at=row["created_at"],
            )
        )
    return result


async def toggle_source_status(
    conn: aiosqlite.Connection, source_id: int
) -> SourceStatus:
    status = await conn.execute(
        """
        UPDATE sources
        SET status = CASE
            WHEN status = :active THEN :revoked
            ELSE :active
        END
        WHERE id = :source_id
        RETURNING status
        """,
        {
            "source_id": source_id,
            "active": SourceStatus.ACTIVE.value,
            "revoked": SourceStatus.REVOKED.value,
        },
    )

    row = await status.fetchone()
    assert row is not None, "No source found with the given ID"

    return SourceStatus(row["status"])


async def delete_source(
    conn: aiosqlite.Connection, source_id: int
) -> DBDeviceSource | None:
    async with conn.execute(
        """
        DELETE FROM sources
        WHERE id = :source_id
        RETURNING id, name, source_type, status, token_hash, last_seen, created_at
        """,
        {"source_id": source_id},
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return DBDeviceSource(
            id=row["id"],
            name=row["name"],
            source_type=SourceType(row["source_type"]),
            status=SourceStatus(row["status"]),
            token_hash=row["token_hash"],
            last_seen=row["last_seen"],
            created_at=row["created_at"],
        )


async def insert_source(
    conn: aiosqlite.Connection,
    *,
    name: str,
    source_type: SourceType,
    token_hash: str,
    status: SourceStatus = SourceStatus.ACTIVE,
) -> DBDeviceSource:
    await conn.execute(
        """
        INSERT INTO sources (name, source_type, token_hash, status)
        VALUES (:name, :source_type, :token_hash, :status)
        """,
        {
            "name": name,
            "source_type": source_type.value,
            "token_hash": token_hash,
            "status": status.value,
        },
    )
    # Fetch the row we just inserted
    async with conn.execute(
        """
        SELECT id, name, source_type, status, token_hash, last_seen, created_at
        FROM sources WHERE name = :name
        """,
        {"name": name},
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None, "Failed to fetch inserted source"
        return DBDeviceSource(
            id=row["id"],
            name=row["name"],
            source_type=SourceType(row["source_type"]),
            status=SourceStatus(row["status"]),
            token_hash=row["token_hash"],
            last_seen=row["last_seen"],
            created_at=row["created_at"],
        )


async def insert_source_enrollment_code(
    conn: aiosqlite.Connection,
    *,
    code_hash: str,
    expires_at: datetime | None,
) -> int:
    cursor = await conn.execute(
        """
        INSERT INTO source_enrollment_codes (code_hash, expires_at, used)
        VALUES (:code_hash, :expires_at, 0)
        """,
        {"code_hash": code_hash, "expires_at": expires_at},
    )
    last_id = cursor.lastrowid
    return int(last_id) if last_id is not None else 0


async def deactivate_active_enrollment_codes(conn: aiosqlite.Connection) -> None:
    # Remove any existing enrollment codes so only one can exist at a time.
    await conn.execute("DELETE FROM source_enrollment_codes")


async def select_current_enrollment_code(
    conn: aiosqlite.Connection,
) -> Optional[Any]:
    async with conn.execute(
        "SELECT id, code_hash, expires_at FROM source_enrollment_codes LIMIT 1"
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return SourceEnrollmentCode(
        id=row["id"], code_hash=row["code_hash"], expires_at=row["expires_at"]
    )


async def delete_current_enrollment_code(conn: aiosqlite.Connection) -> None:
    await conn.execute("DELETE FROM source_enrollment_codes")


async def select_source_by_token_hash(
    conn: aiosqlite.Connection, token_hash: str
) -> Optional[DBDeviceSource]:
    async with conn.execute(
        """
        SELECT id, name, source_type, status, token_hash, last_seen, created_at
        FROM sources WHERE token_hash = :token_hash
        """,
        {"token_hash": token_hash},
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return DBDeviceSource(
            id=row["id"],
            name=row["name"],
            source_type=SourceType(row["source_type"]),
            status=SourceStatus(row["status"]),
            token_hash=row["token_hash"],
            last_seen=row["last_seen"],
            created_at=row["created_at"],
        )


async def update_source_last_seen(
    conn: aiosqlite.Connection, source_id: int, *, when: datetime
) -> None:
    await conn.execute(
        "UPDATE sources SET last_seen = :when WHERE id = :id",
        {"id": source_id, "when": when},
    )


async def select_auto_activities_closed_within_time_range_with_last_event(
    conn: aiosqlite.Connection, start: datetime, end: datetime
) -> list[DBActivityWithLatestEvent]:
    query = """
    SELECT
    a.id, a.name, a.description, a.productivity_level, a.source,
    a.last_manual_action_time AS activity_last_manual_action_time,
    le.event_type AS state,
    le.event_time,
    le.aggregation_id,
    le.id AS last_event_id,
    ag.start_time as aggregation_start_time,
    ag.end_time as aggregation_end_time,
    ag.first_timestamp as aggregation_first_timestamp,
    ag.last_timestamp as aggregation_last_timestamp,
    le.last_manual_action_time AS event_last_manual_action_time

    FROM activities a

    JOIN (
        SELECT *
        FROM activity_events ae
        WHERE ae.id = (
            SELECT ae2.id
            FROM activity_events ae2
            WHERE ae2.activity_id = ae.activity_id
            ORDER BY ae2.event_time DESC
            LIMIT 1
        )
    ) le ON le.activity_id = a.id
    LEFT JOIN aggregations ag ON le.aggregation_id = ag.id
    WHERE a.source = 'auto'
    AND le.event_type = 'close'
      AND datetime(le.event_time) >= datetime(?)
      AND datetime(le.event_time) <= datetime(?);
    """

    return_list = []
    async with conn.execute(query, (start, end)) as cursor:
        rows = await cursor.fetchall()
        for row in rows:
            db_activity = DBActivity(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                productivity_level=row["productivity_level"],
                source=row["source"],
                last_manual_action_time=row["activity_last_manual_action_time"],
            )

            db_activity_event = DBActivityEvent(
                event_time=row["event_time"],
                event_type=row["state"],
                id=row["last_event_id"],
                activity_id=row["id"],
                aggregation_id=row["aggregation_id"],
                last_manual_action_time=row["event_last_manual_action_time"],
            )
            latest_aggregation = DBAggregation(
                id=row["aggregation_id"],
                start_time=row["aggregation_start_time"],
                end_time=row["aggregation_end_time"],
                first_timestamp=row["aggregation_first_timestamp"],
                last_timestamp=row["aggregation_last_timestamp"],
            )
            return_list.append(
                DBActivityWithLatestEvent(
                    activity=db_activity,
                    latest_event=db_activity_event,
                    latest_aggregation=latest_aggregation,
                )
            )
    return return_list


async def select_manual_activity_specs_active_within_time_range(
    conn: aiosqlite.Connection, start: datetime, end: datetime
) -> list[DBActivitySpec]:
    """
    Fetches all manual activities specs that are active within a given time range.
    An activity is considered active if it's a manual activity and:
    1. It has an 'open' event within the specified time range (inclusive).
    2. Its last event before the start of the time range was 'open'.
    """
    activity_ids_query = """
        SELECT DISTINCT a.id
        FROM activities a
        WHERE a.source = 'manual'
        AND (
            -- Condition 1: Has an open event within the time range
            EXISTS (
                SELECT 1
                FROM activity_events ae
                WHERE ae.activity_id = a.id
                AND ae.event_time >= :start
                AND ae.event_time <= :end
                AND ae.event_type = 'open'
            )
            OR
            -- Condition 2: Last event before start is 'open'
            (
                SELECT ae.event_type
                FROM activity_events ae
                WHERE ae.activity_id = a.id AND ae.event_time < :start
                ORDER BY ae.event_time DESC
                LIMIT 1
            ) = 'open'
        )
    """
    async with conn.execute(activity_ids_query, {"start": start, "end": end}) as cursor:
        rows = await cursor.fetchall()
        activity_ids = [row["id"] for row in rows]

    if not activity_ids:
        return []

    # Now fetch the full specs for these activities.
    placeholders = ",".join("?" for _ in activity_ids)
    specs_query = f"""
        SELECT a.id AS activity_id,
               a.name,
               a.description,
               a.productivity_level,
               a.source,
               a.last_manual_action_time AS activity_last_manual_action_time,
               e.id AS event_id,
               e.event_time,
               e.event_type,
               e.aggregation_id,
               e.last_manual_action_time AS event_last_manual_action_time
        FROM activities a
        JOIN activity_events e ON a.id = e.activity_id
        WHERE a.id IN ({placeholders});
    """

    async with conn.execute(specs_query, activity_ids) as cursor:
        rows = await cursor.fetchall()

    grouped = defaultdict(list)
    for row in rows:
        activity_id = row["activity_id"]
        grouped[activity_id].append(row)

    activity_specs = []
    for activity_id, activity_rows in grouped.items():
        first_row = activity_rows[0]

        db_activity = DBActivity(
            id=activity_id,
            name=first_row["name"],
            description=first_row["description"],
            productivity_level=first_row["productivity_level"],
            source=first_row["source"],
            last_manual_action_time=first_row["activity_last_manual_action_time"],
        )

        events = []
        for row in activity_rows:
            db_activity_event = DBActivityEvent(
                event_time=row["event_time"],
                event_type=row["event_type"],
                id=row["event_id"],
                activity_id=activity_id,
                aggregation_id=row["aggregation_id"],
                last_manual_action_time=row["event_last_manual_action_time"],
            )
            events.append(db_activity_event)

        db_activity_spec = DBActivitySpec(activity=db_activity, events=events)
        activity_specs.append(db_activity_spec)

    return activity_specs


async def insert_candidate_sessions(
    conn: aiosqlite.Connection,
    *,
    sessionization_run_id: int,
    sessions: Sequence[CandidateSession],
) -> list[int]:
    if not sessions:
        return []

    placeholders = ", ".join("(?, ?, ?)" for _ in sessions)
    values: list[Any] = []
    for session in sessions:
        values.extend([session.name, session.llm_id, sessionization_run_id])

    sql = f"""
        INSERT INTO candidate_sessions (
            name,
            llm_id,
            sessionization_run_id
        )
        VALUES {placeholders}
        RETURNING
            id
    """

    async with conn.execute(sql, values) as cursor:
        rows = await cursor.fetchall()

    return [int(row["id"]) for row in rows]


async def insert_candidate_session_to_activity(
    conn: aiosqlite.Connection,
    *,
    mappings: Sequence[CandidateSessionToActivity],
) -> None:
    if not mappings:
        return

    await conn.executemany(
        """
        INSERT INTO candidate_session_to_activity (
            session_id,
            activity_id
        )
        VALUES (?, ?)
        """,
        [(mapping.candidate_session_id, mapping.activity_id) for mapping in mappings],
    )


async def delete_candidate_session_to_activity_by_activity_ids(
    conn: aiosqlite.Connection,
    *,
    activity_ids: Sequence[int],
) -> None:
    # Delete candidate session mappings for the given activity ids in a single query.
    if not activity_ids:
        return

    placeholders = ",".join("?" for _ in activity_ids)
    await conn.execute(
        f"""
        DELETE FROM candidate_session_to_activity
        WHERE activity_id IN ({placeholders})
        """,
        list(activity_ids),
    )


async def delete_candidate_sessions_by_ids(
    conn: aiosqlite.Connection,
    *,
    candidate_session_ids: Sequence[int],
) -> None:
    if not candidate_session_ids:
        return

    placeholders = ",".join("?" for _ in candidate_session_ids)
    await conn.execute(
        f"""
        DELETE FROM candidate_sessions
        WHERE id IN ({placeholders})
        """,
        list(candidate_session_ids),
    )


async def delete_candidate_sessions_without_activities(
    conn: aiosqlite.Connection,
) -> int:
    # Delete all candidate sessions that have no activity mappings. Returns the number of rows deleted.
    cursor = await conn.execute(
        """
        DELETE FROM candidate_sessions
        WHERE id NOT IN (
            SELECT DISTINCT session_id
            FROM candidate_session_to_activity
        )
        """
    )
    return cursor.rowcount or 0


async def select_candidate_session_specs(
    conn: aiosqlite.Connection,
    *,
    sessionization_run_id: int | None = None,
) -> list[DBCandidateSessionSpec]:
    where_clause = ""
    params: list[Any] = []
    if sessionization_run_id is not None:
        where_clause = "WHERE cs.sessionization_run_id = ?"
        params.append(sessionization_run_id)

    async with conn.execute(
        f"""
        SELECT
            cs.id,
            cs.name,
            cs.llm_id,
            cs.sessionization_run_id,
            cs.created_at,
            (
                SELECT GROUP_CONCAT(sub.activity_id, ',')
                FROM (
                    SELECT activity_id
                    FROM candidate_session_to_activity csta
                    WHERE csta.session_id = cs.id
                    ORDER BY datetime(csta.created_at) ASC, csta.activity_id ASC
                ) AS sub
            ) AS activity_ids_csv
        FROM candidate_sessions cs
        {where_clause}
        ORDER BY datetime(cs.created_at) ASC, cs.id ASC
        """,
        params,
    ) as cursor:
        rows = await cursor.fetchall()

    specs: list[DBCandidateSessionSpec] = []
    for row in rows:
        activity_ids_csv = row["activity_ids_csv"]
        activity_ids = (
            [int(value) for value in activity_ids_csv.split(",") if value]
            if activity_ids_csv
            else []
        )

        specs.append(
            DBCandidateSessionSpec(
                session=DBCandidateSession(
                    id=row["id"],
                    name=row["name"],
                    llm_id=row["llm_id"],
                    sessionization_run_id=row["sessionization_run_id"],
                    created_at=row["created_at"],
                ),
                activity_ids=activity_ids,
            )
        )

    return specs


async def insert_sessionization_run(
    conn: aiosqlite.Connection,
    *,
    sessionization_run: SessionizationRun,
) -> int:
    cursor = await conn.execute(
        """
        INSERT INTO sessionization_run (
            candidate_creation_start,
            candidate_creation_end,
            overlap_start,
            right_tail_end,
            finalized_horizon
        )
        VALUES (?, ?, ?, ?, ?)
        RETURNING
            id
        """,
        (
            sessionization_run.candidate_creation_start,
            sessionization_run.candidate_creation_end,
            sessionization_run.overlap_start,
            sessionization_run.right_tail_end,
            sessionization_run.finalized_horizon,
        ),
    )

    row = await cursor.fetchone()
    assert row is not None, "sessionization_run insert did not return a row"

    return row["id"]


async def select_latest_sessionization_run(
    conn: aiosqlite.Connection,
) -> DBSessionizationRun | None:
    async with conn.execute(
        """
        SELECT
            id,
            created_at,
            candidate_creation_start,
            candidate_creation_end,
            overlap_start,
            right_tail_end,
            finalized_horizon
        FROM sessionization_run
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    return DBSessionizationRun(
        id=row["id"],
        created_at=row["created_at"],
        candidate_creation_start=row["candidate_creation_start"],
        candidate_creation_end=row["candidate_creation_end"],
        overlap_start=row["overlap_start"],
        right_tail_end=row["right_tail_end"],
        finalized_horizon=row["finalized_horizon"],
    )


async def insert_sessions(
    conn: aiosqlite.Connection,
    *,
    sessionization_run_id: int,
    sessions: Sequence[Session],
) -> list[int]:
    if not sessions:
        return []

    insert_sql = """
        INSERT INTO sessions (
            name,
            llm_id,
            sessionization_run_id
        )
        VALUES (?, ?, ?)
    """

    inserted_ids: list[int] = []
    for session in sessions:
        cursor = await conn.execute(
            insert_sql,
            (
                session.name,
                session.llm_id,
                sessionization_run_id,
            ),
        )
        last_row_id = cursor.lastrowid
        assert last_row_id is not None, "sessions insert did not return an id"
        inserted_ids.append(last_row_id)

    return inserted_ids


async def insert_session_to_activity(
    conn: aiosqlite.Connection,
    mappings: Sequence[tuple[int, int]],
) -> None:
    if not mappings:
        return

    await conn.executemany(
        """
        INSERT INTO session_to_activity (session_id, activity_id)
        VALUES (?, ?)
        """,
        mappings,
    )


async def select_specs_with_tags_and_sessions_in_time_range(
    conn: aiosqlite.Connection, start: datetime, end: datetime
) -> list[DBActivitySpecWithTagsAndSessions]:
    """Get activity specs with tags, finalized sessions, and candidate sessions in the given time range.

    Uses the same activity filtering criteria as select_specs_with_tags_in_time_range.
    """
    # First get regular activity specs
    activity_specs = await select_specs_in_time_range(conn, start, end)

    if not activity_specs:
        return []

    # Get all activity IDs
    activity_ids = [
        spec.activity.id for spec in activity_specs if spec.activity.id is not None
    ]

    if not activity_ids:
        return []

    placeholders = ",".join("?" for _ in activity_ids)

    # Query to get all tags, sessions, and candidate sessions for these activities
    query = f"""
    SELECT
        a.id AS activity_id,
        -- Tags
        t.id AS tag_id,
        t.name AS tag_name,
        t.description AS tag_description,
        -- Finalized sessions (can only be one per activity due to UNIQUE constraint)
        s.id AS session_id,
        s.name AS session_name,
        s.llm_id AS session_llm_id,
        s.created_at AS session_created_at,
        s.sessionization_run_id AS session_run_id,
        -- Candidate sessions (can be multiple)
        cs.id AS candidate_session_id,
        cs.name AS candidate_session_name,
        cs.llm_id AS candidate_session_llm_id,
        cs.created_at AS candidate_session_created_at,
        cs.sessionization_run_id AS candidate_session_run_id
    FROM activities a
    LEFT JOIN tag_mappings tm ON a.id = tm.activity_id
    LEFT JOIN tags t ON tm.tag_id = t.id AND t.deleted_at IS NULL
    LEFT JOIN session_to_activity sta ON a.id = sta.activity_id
    LEFT JOIN sessions s ON sta.session_id = s.id
    LEFT JOIN candidate_session_to_activity csta ON a.id = csta.activity_id
    LEFT JOIN candidate_sessions cs ON csta.session_id = cs.id
    WHERE a.id IN ({placeholders})
    """

    async with conn.execute(query, activity_ids) as cursor:
        rows = await cursor.fetchall()

    # Group data by activity
    tags_by_activity: dict[int, list[DBTag]] = defaultdict(list)
    session_by_activity: dict[int, DBSession] = {}
    candidate_sessions_by_activity: dict[int, list[DBCandidateSession]] = defaultdict(
        list
    )

    for row in rows:
        activity_id = row["activity_id"]

        # Collect tags
        tag_id = row["tag_id"]
        if tag_id is not None:
            tag = DBTag(
                id=tag_id, name=row["tag_name"], description=row["tag_description"]
            )
            # Avoid duplicates
            if tag not in tags_by_activity[activity_id]:
                tags_by_activity[activity_id].append(tag)

        # Collect finalized session (only one per activity)
        session_id = row["session_id"]
        if session_id is not None and activity_id not in session_by_activity:
            session_by_activity[activity_id] = DBSession(
                id=session_id,
                name=row["session_name"],
                llm_id=row["session_llm_id"],
                created_at=row["session_created_at"],
                sessionization_run_id=row["session_run_id"],
            )

        # Collect candidate sessions (can be multiple)
        candidate_session_id = row["candidate_session_id"]
        if candidate_session_id is not None:
            candidate_session = DBCandidateSession(
                id=candidate_session_id,
                name=row["candidate_session_name"],
                llm_id=row["candidate_session_llm_id"],
                created_at=row["candidate_session_created_at"],
                sessionization_run_id=row["candidate_session_run_id"],
            )
            # Avoid duplicates
            if candidate_session not in candidate_sessions_by_activity[activity_id]:
                candidate_sessions_by_activity[activity_id].append(candidate_session)

    # Combine activities with their relationships
    result = []
    for spec in activity_specs:
        activity_id = spec.activity.id
        tags = tags_by_activity.get(activity_id, [])
        session = session_by_activity.get(activity_id, None)
        candidate_sessions = candidate_sessions_by_activity.get(activity_id, [])

        # Create enhanced spec with tags and sessions
        spec_with_relationships = DBActivitySpecWithTagsAndSessions(
            **spec.model_dump(),
            tags=tags,
            session=session,
            candidate_sessions=candidate_sessions,
        )
        result.append(spec_with_relationships)

    return result
