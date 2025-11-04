from __future__ import annotations

# ruff: noqa: I001
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import NamedTuple

import aiosqlite
from baml_py import Collector

from baml_client import b
from baml_client.type_builder import TypeBuilder
import baml_client.types as baml_types
from loguru import logger
from clepsy import utils
from clepsy.config import config
from clepsy.db.db import get_db_connection
from clepsy.db.queries import (
    insert_activities,
    insert_activity_events,
    insert_aggregation,
    insert_tag_mappings,
    select_auto_activities_closed_within_time_range_with_last_event,
    select_latest_aggregation,
    select_manual_activity_specs_active_within_time_range,
    select_open_activities_with_last_event,
    select_open_auto_activities_with_last_event,
    select_tags,
    select_user_settings,
    update_activity,
)
import clepsy.entities as E
from clepsy.llm import create_client_registry
from clepsy.modules.aggregator.programmatic_timeline_validation import (
    validate_timeline_programmatically,
)
from clepsy.modules.aggregator.stitching import stitch_timeline


async def llm_productivity_level_activity(
    activity_name: str, activity_description: str, user_settings: E.UserSettings
) -> E.ProductivityLevel:
    productivity_guidelines = (
        """Please classify the productivity level of the activity based on the following guidelines:\n
    {guidelines}"""
    ).format(guidelines=user_settings.productivity_prompt)

    client = create_client_registry(
        llm_config=user_settings.text_model_config, name="TextClient", set_primary=True
    )

    productivity_level = await b.ClassifyActivityProductivity(
        activity_name=activity_name,
        activity_description=activity_description,
        productivity_guidelines=productivity_guidelines,
        baml_options={"client_registry": client},
    )

    return E.ProductivityLevel(productivity_level)


async def llm_tag_activity(
    activity_name: str,
    activity_description: str,
    tags: list[E.DBTag],
    user_settings: E.UserSettings,
) -> list[E.DBTag]:
    description = activity_description
    if not tags:
        return []
    tb = TypeBuilder()

    for tag in tags:
        tb.TagNames.add_value(tag.name)

    client = create_client_registry(
        llm_config=user_settings.text_model_config, name="TextClient", set_primary=True
    )

    tag_catalog = [
        baml_types.Tag(name=tag.name, description=tag.description) for tag in tags
    ]

    matching_tag_names = await b.TagActivity(
        activity_name=activity_name,
        activity_description=description,
        tag_catalog=tag_catalog,
        baml_options={"client_registry": client, "tb": tb},
    )
    matching_tags = [tag for tag in tags if tag.name in matching_tag_names]

    return matching_tags


async def llm_tag_extras(
    activity_name: str,
    activity_description: str,
    tags: list[E.DBTag],
    user_settings: E.UserSettings,
) -> E.ActivityExtras:
    productivity_task = llm_productivity_level_activity(
        activity_name=activity_name,
        activity_description=activity_description,
        user_settings=user_settings,
    )
    assigned_tags_task = llm_tag_activity(
        activity_name=activity_name,
        activity_description=activity_description,
        tags=tags,
        user_settings=user_settings,
    )

    productivity_level, matched_tags = await asyncio.gather(
        productivity_task,
        assigned_tags_task,
    )

    return E.ActivityExtras(
        productivity_level=productivity_level,
        tags=matched_tags,
    )


class TimelineAggregatorInputs(NamedTuple):
    logs: list[baml_types.TimelineLog]


def prepare_timeline_aggregator_inputs(
    input_logs: list[E.AggregationInputEvent],
    aggregation_time_span: E.TimeSpan,
) -> TimelineAggregatorInputs:
    input_logs.sort(key=lambda x: x.timestamp)

    def prep_input_logs_baml(
        x: E.AggregationInputEvent,
    ) -> baml_types.TimelineLog:
        match x:
            case E.ProcessedDesktopCheckScreenshotEventVLM():
                return baml_types.DesktopCheckScreenshotVLM(
                    kind="desktop_screenshot_vlm",
                    timestamp=utils.datetime_to_mm_ss(
                        aggregation_time_span.start_time, x.timestamp
                    ),
                    llm_description=x.llm_description,
                    active_window=baml_types.WindowInfo(
                        title=x.active_window.title,
                        app_name=x.active_window.app_name,
                        is_active=x.active_window.is_active,
                    ),
                )
            case E.ProcessedDesktopCheckScreenshotEventOCR():
                return baml_types.DesktopCheckScreenshotOCR(
                    kind="desktop_screenshot_ocr",
                    timestamp=utils.datetime_to_mm_ss(
                        aggregation_time_span.start_time, x.timestamp
                    ),
                    image_text=x.image_text,
                    active_window=baml_types.WindowInfo(
                        title=x.active_window.title,
                        app_name=x.active_window.app_name,
                        is_active=x.active_window.is_active,
                    ),
                    image_text_post_processed_by_llm=x.image_text_post_processed_by_llm,
                )

            case E.MobileAppUsageEvent():
                media_summary = None
                if x.media_metadata:
                    media_summary = ", ".join(
                        f"{key}: {value}"
                        for key, value in x.media_metadata.items()
                        if value
                    )

                return baml_types.MobileAppUsageEvent(
                    kind="mobile_app_usage",
                    timestamp=utils.datetime_to_mm_ss(
                        aggregation_time_span.start_time, x.timestamp
                    ),
                    app_label=x.app_label,
                    package_name=x.package_name,
                    activity_name=x.activity_name,
                    media_summary=media_summary,
                    notification_text=x.notification_text,
                )

            case _:
                raise ValueError(f"Unsupported event type: {type(x)}")

    logs_baml = list(map(prep_input_logs_baml, input_logs))

    return TimelineAggregatorInputs(
        logs=logs_baml,
    )


async def manual_activity_reconciliation(
    manual_activities: list[E.DBActivitySpec],
    generated_timeline_activities: dict[str, baml_types.ActivityMetadata],
    generated_timeline_events: list[baml_types.Event],
    aggregation_time_span: E.TimeSpan,
    text_model_config: E.LLMConfig,
) -> tuple[dict[str, baml_types.ActivityMetadata], list[baml_types.Event]]:
    if not manual_activities:
        return generated_timeline_activities, generated_timeline_events

    generated_timeline_events.sort(key=lambda x: utils.mm_ss_to_timedelta(x.t))

    activity_id_to_sorted_events = defaultdict(list)
    for event in generated_timeline_events:
        activity_id_to_sorted_events[event.activity_id].append(event)

    manual_activity_id_to_overlapping_ids = defaultdict(list)

    for manual_activity in manual_activities:
        sorted_events = manual_activity.sorted_events

        sorted_time_floats = [x.event_time.timestamp() for x in sorted_events]

        event_bools = [x.event_type == E.ActivityEventType.OPEN for x in sorted_events]

        overlap_tuples = list(zip(sorted_time_floats, event_bools))

        for (
            generated_activity_id,
            generated_activity,
        ) in generated_timeline_activities.items():
            sorted_generated_events = activity_id_to_sorted_events[
                generated_activity_id
            ]
            sorted_generated_time_floats = [
                utils.mm_ss_string_to_datetime(
                    aggregation_time_span.start_time, x.t
                ).timestamp()
                for x in sorted_generated_events
            ]

            generated_event_bools = [
                x.event_type == "open" for x in sorted_generated_events
            ]
            generated_overlap_tuples = list(
                zip(sorted_generated_time_floats, generated_event_bools)
            )

            overlap = utils.overlap_in_span(
                overlap_tuples,
                generated_overlap_tuples,
                (
                    aggregation_time_span.start_time.timestamp(),
                    aggregation_time_span.end_time.timestamp(),
                ),
            )

            if overlap:
                manual_activity_id_to_overlapping_ids[
                    manual_activity.activity_id
                ].append(generated_activity_id)

    generated_activity_ids_to_remove = set()

    for manual_activity in manual_activities:
        manual_activity_id = manual_activity.activity_id

        overlapping_ids = manual_activity_id_to_overlapping_ids[manual_activity_id]

        for overlapping_activity_id in overlapping_ids:
            if overlapping_activity_id in generated_activity_ids_to_remove:
                continue

            generated_activity = generated_timeline_activities[overlapping_activity_id]

            # Delegate to LLM to decide if overlapping auto should be removed
            reconciliation_result = await b.ManualActivityReconciliation(
                manual_activity=baml_types.ActivityReconciliationActivity(
                    name=manual_activity.activity.name,
                    description=manual_activity.activity.description,
                ),
                auto_activity=baml_types.ActivityReconciliationActivity(
                    name=generated_activity.name,
                    description=generated_activity.description,
                ),
                baml_options={
                    "client_registry": create_client_registry(
                        llm_config=text_model_config,
                        name="TextClient",
                        set_primary=True,
                    )
                },
            )

            if reconciliation_result.remove:
                logger.info(
                    "Removing auto activity {} due to manual activity reconciliation",
                    overlapping_activity_id,
                )
                generated_activity_ids_to_remove.add(overlapping_activity_id)

    final_activities = {
        activity_id: activity_metadata
        for activity_id, activity_metadata in generated_timeline_activities.items()
        if activity_id not in generated_activity_ids_to_remove
    }

    final_events = [
        event
        for event in generated_timeline_events
        if event.activity_id not in generated_activity_ids_to_remove
    ]

    return final_activities, final_events


async def generate_isolated_timeline(
    input_logs: list[E.AggregationInputEvent],
    aggregation_time_span: E.TimeSpan,
    text_model_config: E.LLMConfig,
    collector: Collector,
    qc_policy: E.IsolatedTimelineQCPolicy,
    max_desktop_screenshot_log_interval_seconds: int,
    max_pause_time_seconds: int,
    aggregation_interval_seconds: int,
) -> tuple[dict[str, baml_types.ActivityMetadata], list[baml_types.Event]]:
    inputs = prepare_timeline_aggregator_inputs(
        input_logs=input_logs,
        aggregation_time_span=aggregation_time_span,
    )

    client = create_client_registry(
        llm_config=text_model_config,
        name="TextClient",
        set_primary=True,
        request_timeout_seconds=60 * 5,
    )

    if not inputs.logs:
        logger.warning(
            "No logs provided for timeline aggregation, returning empty timeline"
        )
        return {}, []

    schema_with_reasoning = await b.GenerateTimeline(
        logs=inputs.logs,
        duration_seconds=aggregation_interval_seconds,
        max_pause_time_seconds=max_pause_time_seconds,
        max_desktop_screenshot_log_interval_seconds=max_desktop_screenshot_log_interval_seconds,
        baml_options={"client_registry": client, "collector": collector},
    )

    reasoning = schema_with_reasoning.reasoning

    logger.trace("Aggregation LLM Reasoning: {}", reasoning)

    timeline = schema_with_reasoning.filled_schema
    timeline.events = sorted(
        timeline.events, key=lambda x: utils.mm_ss_to_timedelta(x.t)
    )
    error_strings = validate_timeline_programmatically(
        timeline=timeline,
        aggregation_time_span=aggregation_time_span,
    )

    if error_strings:
        logger.warning(
            "Programmatic validation found errors in the generated timeline: {} for {}",
            error_strings,
            timeline,
        )

    if qc_policy == E.IsolatedTimelineQCPolicy.ALWAYS or (
        qc_policy == E.IsolatedTimelineQCPolicy.WHEN_PROGRAMMATIC_ERRRORS
        and error_strings
    ):
        qc_result = await b.QualityControlTimeline(
            generated_timeline=timeline,
            duration_seconds=aggregation_interval_seconds,
            max_pause_time_seconds=config.max_pause_time_seconds,
            baml_options={"client_registry": client, "collector": collector},
            logs=inputs.logs,
            errors=error_strings,
        )

        if isinstance(qc_result.timeline, baml_types.Timeline):
            logger.info("Timeline changed in qc,reasoning: {}", qc_result.reasoning)
            timeline = qc_result.timeline
            timeline.events = sorted(
                timeline.events, key=lambda x: utils.mm_ss_to_timedelta(x.t)
            )
            error_strings_post_qc = validate_timeline_programmatically(
                timeline=timeline,
                aggregation_time_span=aggregation_time_span,
            )
            assert not error_strings_post_qc, f"Programmatic validation found errors in the QC-ed timeline: {error_strings_post_qc} for {timeline}"

    new_events = timeline.events
    new_activities = timeline.activities

    return new_activities, new_events


async def persist_new_activities(
    new_activities: dict[str, baml_types.ActivityMetadata],
    new_events: list[baml_types.Event],
    aggregation_time_span: E.TimeSpan,
    conn: aiosqlite.Connection,
    activity_extras: list[E.ActivityExtras],
    events_to_insert: list[E.ActivityEventInsert],
    aggregation_id: int,
):
    for event in events_to_insert:
        event.aggregation_id = aggregation_id

    tag_mappings_to_insert: list[E.TagMapping] = []
    activities_to_insert: list[E.Activity] = []
    original_llm_activity_ids_ordered: list[str] = []
    for activity_extra, (llm_activity_id, activity_metadata) in zip(
        activity_extras, new_activities.items()
    ):
        actual_activity = E.Activity(
            name=activity_metadata.name,  # Use activity_data
            description=activity_metadata.description,  # Use activity_data
            productivity_level=activity_extra.productivity_level,
            source=E.Source.AUTO,
            last_manual_action_time=None,
        )
        activities_to_insert.append(actual_activity)

        original_llm_activity_ids_ordered.append(llm_activity_id)

    if activities_to_insert:
        inserted_activity_ids = await insert_activities(conn, activities_to_insert)

        for activity_extra, activity_db_id, activity_llm_id in zip(
            activity_extras, inserted_activity_ids, original_llm_activity_ids_ordered
        ):
            for tag_item in activity_extra.tags:
                assert tag_item.id is not None, "Tag must have an ID to be mapped"
                tag_mappings_to_insert.append(
                    E.TagMapping(activity_id=activity_db_id, tag_id=tag_item.id)
                )

            generated_events = [
                event for event in new_events if event.activity_id == activity_llm_id
            ]

            for llm_event in generated_events:
                events_to_insert.append(
                    E.ActivityEventInsert(
                        event_type=E.ActivityEventType(llm_event.event_type),
                        event_time=utils.mm_ss_string_to_datetime(
                            aggregation_time_span.start_time, llm_event.t
                        ),
                        activity_id=activity_db_id,
                        aggregation_id=aggregation_id,
                        last_manual_action_time=None,
                    )
                )

    tasks = []
    if events_to_insert:
        tasks.append(insert_activity_events(conn, events_to_insert))

    if tag_mappings_to_insert:
        tasks.append(insert_tag_mappings(conn, tag_mappings_to_insert))

    await asyncio.gather(*tasks)


async def aggregator_core(
    input_logs: list[E.AggregationInputEvent],
    manual_activities: list[E.DBActivitySpec],
    stitchable_closed_activities: list[E.DBActivityWithLatestEvent],
    open_auto_activities: list[E.DBActivityWithLatestEvent],
    previous_aggregation_end_time: datetime | None,
    aggregation_time_span: E.TimeSpan,
    text_model_config: E.LLMConfig,
    collector: Collector,
) -> E.AggregatorCoreOutput:
    (
        generated_timeline_activities,
        generated_timeline_events,
    ) = await generate_isolated_timeline(
        collector=collector,
        input_logs=input_logs,
        text_model_config=text_model_config,
        aggregation_time_span=aggregation_time_span,
        qc_policy=E.IsolatedTimelineQCPolicy.ALWAYS,
        max_desktop_screenshot_log_interval_seconds=config.max_desktop_screenshot_log_interval_seconds,
        max_pause_time_seconds=config.max_pause_time_seconds,
        aggregation_interval_seconds=config.aggregation_interval_minutes * 60,
    )

    (
        generated_timeline_activities,
        generated_timeline_events,
    ) = await manual_activity_reconciliation(
        manual_activities=manual_activities,
        generated_timeline_activities=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        aggregation_time_span=aggregation_time_span,
        text_model_config=text_model_config,
    )

    stitch_output = await stitch_timeline(
        generated_timeline_activites=generated_timeline_activities,
        generated_timeline_events=generated_timeline_events,
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=previous_aggregation_end_time,
        stitchable_activities=stitchable_closed_activities + open_auto_activities,
        max_activity_pause_time=config.max_activity_pause_time,
        baml_client_registry=create_client_registry(
            llm_config=text_model_config,
            name="TextClient",
            set_primary=True,
        ),
    )

    logger.debug(
        "Stitching output: {}",
        stitch_output,
    )

    stitched_activities_events = stitch_output.stitched_activities_events
    unstitched_activities_close_events = (
        stitch_output.unstitched_activities_close_events
    )
    activities_to_update = stitch_output.activities_to_update

    stitched_llm_ids = set(stitch_output.stitchable_activity_to_llm_id.values())
    new_events = [
        event
        for event in generated_timeline_events
        if event.activity_id not in stitched_llm_ids
    ]

    new_activities = {
        activity_llm_id: activity
        for activity_llm_id, activity in generated_timeline_activities.items()
        if activity_llm_id not in stitched_llm_ids
    }

    return E.AggregatorCoreOutput(
        new_activities=new_activities,
        new_activity_events=new_events,
        stitched_activities_events=stitched_activities_events,
        unstitched_activities_close_events=unstitched_activities_close_events,
        activities_to_update=activities_to_update,
    )


async def get_interrupted_activity_close_events(
    conn: aiosqlite.Connection, previous_aggregation: E.DBAggregation | None
) -> list[E.ActivityEventInsert] | None:
    if not previous_aggregation:
        logger.info(
            "No previous aggregation found, skipping interrupted open activities check"
        )
        return

    open_activities = await select_open_activities_with_last_event(
        conn=conn,
    )

    open_auto_activities = [a for a in open_activities if not a.activity.is_manual]

    if not open_auto_activities:
        logger.info("No open auto activities found, nothing to close")
        return

    last_observed_time = previous_aggregation.end_time

    close_events = []
    for open_activity in open_auto_activities:
        assert open_activity.activity.id is not None, "Open activity must have an ID"
        close_events.append(
            E.ActivityEventInsert(
                event_type=E.ActivityEventType.CLOSE,
                event_time=last_observed_time,
                activity_id=open_activity.activity.id,
                aggregation_id=None,
                last_manual_action_time=None,
            )
        )

    return close_events


async def aggregator(
    input_logs: list[E.AggregationInputEvent],
    aggregation_time_span: E.TimeSpan,
    conn: aiosqlite.Connection,
    user_settings: E.UserSettings,
    collector: Collector,
    previous_aggregation: E.DBAggregation | None = None,
) -> E.AggregatorCoreOutput:
    manual_activities = await select_manual_activity_specs_active_within_time_range(
        conn=conn,
        start=aggregation_time_span.start_time,
        end=aggregation_time_span.end_time,
    )

    open_auto_activities = await select_open_auto_activities_with_last_event(
        conn=conn,
    )

    potentially_stitchable_start_time = (
        aggregation_time_span.start_time - config.max_activity_pause_time
    )
    potentially_stitchable_close_time = aggregation_time_span.start_time

    stitchable_closed_activities = (
        await select_auto_activities_closed_within_time_range_with_last_event(
            conn=conn,
            start=potentially_stitchable_start_time,
            end=potentially_stitchable_close_time,
        )
    )

    core_output = await aggregator_core(
        collector=collector,
        text_model_config=user_settings.text_model_config,
        input_logs=input_logs,
        manual_activities=manual_activities,
        open_auto_activities=open_auto_activities,
        stitchable_closed_activities=stitchable_closed_activities,
        previous_aggregation_end_time=previous_aggregation.end_time
        if previous_aggregation
        else None,
        aggregation_time_span=aggregation_time_span,
    )

    return core_output


async def do_aggregation(
    input_logs: list[E.AggregationInputEvent],
    aggregation_time_span: E.TimeSpan,
):
    collector = Collector(name="Aggregation")

    assert input_logs, "do_aggregation must be called with non-empty input_logs"
    input_logs.sort(key=lambda x: x.timestamp)
    first_event_timestamp = input_logs[0].timestamp
    last_event_timestamp = input_logs[-1].timestamp
    aggregation_events_time_span = E.TimeSpan(
        start_time=first_event_timestamp, end_time=last_event_timestamp
    )

    async with get_db_connection() as conn:
        previous_aggregation = await select_latest_aggregation(conn)
        user_settings = await select_user_settings(conn)
        if not user_settings:
            raise E.MissingUserSettingsError()

        tags = await select_tags(conn)
        core_output = await aggregator(
            input_logs=input_logs,
            aggregation_time_span=aggregation_time_span,
            conn=conn,
            user_settings=user_settings,
            previous_aggregation=previous_aggregation,
            collector=collector,
        )

    activity_extras = []
    if core_output.new_activities:
        activity_extras = await asyncio.gather(
            *(
                llm_tag_extras(
                    activity_name=activity_metadata.name,
                    activity_description=activity_metadata.description,
                    tags=tags,
                    user_settings=user_settings,
                )
                for activity_metadata in core_output.new_activities.values()
            )
        )

    async with get_db_connection(start_transaction=True, commit_on_exit=True) as conn:
        aggregation_id = await insert_aggregation(
            aggregation=E.Aggregation(
                start_time=aggregation_time_span.start_time,
                end_time=aggregation_time_span.end_time,
                first_timestamp=aggregation_events_time_span.start_time,
                last_timestamp=aggregation_events_time_span.end_time,
            ),
            conn=conn,
        )

        events_to_insert: list[E.ActivityEventInsert] = []
        for ev in (
            core_output.stitched_activities_events
            + core_output.unstitched_activities_close_events
        ):
            events_to_insert.append(
                E.ActivityEventInsert(
                    activity_id=ev.activity_id,
                    event_time=ev.event_time,
                    event_type=ev.event_type,
                    aggregation_id=aggregation_id,
                    last_manual_action_time=None,
                )
            )

        if core_output.new_activities:
            await persist_new_activities(
                new_activities=core_output.new_activities,
                new_events=core_output.new_activity_events,
                conn=conn,
                activity_extras=activity_extras,
                events_to_insert=events_to_insert,
                aggregation_time_span=aggregation_time_span,
                aggregation_id=aggregation_id,
            )
        elif events_to_insert:
            await insert_activity_events(conn, events_to_insert)

        if core_output.activities_to_update:
            await asyncio.gather(
                *(
                    update_activity(conn, activity_id, kv_pairs)
                    for activity_id, kv_pairs in core_output.activities_to_update
                )
            )

    formatted_function_logs = "\n".join(
        [utils.format_function_log(x) for x in collector.logs]
    )

    logger.debug(
        "Aggregation completed. Function logs:\n{}",
        formatted_function_logs,
    )


async def do_empty_aggregation():
    # Open a connection and perform both read and optional write within the same context
    async with get_db_connection(start_transaction=False, commit_on_exit=True) as conn:
        previous_aggregation = await select_latest_aggregation(conn)
        close_events = await get_interrupted_activity_close_events(
            conn, previous_aggregation=previous_aggregation
        )
        if close_events:
            await insert_activity_events(conn, close_events)
