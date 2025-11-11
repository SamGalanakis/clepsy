import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import NamedTuple

from baml_py import ClientRegistry
from loguru import logger
from rapidfuzz.distance import Levenshtein

from baml_client import b
import baml_client.types as baml_types
from clepsy import utils
from clepsy.entities import (
    ActivityEventType,
    ActivityStitchingInput,
    DBActivityWithLatestEvent,
    NewActivityEventExistingActivity,
    TimeSpan,
)


class StitchResult(NamedTuple):
    id: int
    stitched_activity: baml_types.ActivityStitchOutput
    delete_first_generated_event: bool


class StitchTimelineOutput(NamedTuple):
    stitchable_activity_to_llm_id: dict[int, str]
    stitched_activities_events: list[NewActivityEventExistingActivity]
    unstitched_activities_close_events: list[NewActivityEventExistingActivity]
    activities_to_update: list[tuple[int, dict[str, str]]]


STITCH_TRANS_TABLE = str.maketrans("-_.,()[]{}\\/|:;'\"`\t\n\r", " " * 21)


def stitch_norm(s: str) -> str:
    return " ".join(s.lower().translate(STITCH_TRANS_TABLE).split())


def to_stitch(
    a: ActivityStitchingInput, b_activity: ActivityStitchingInput, max_dist: int = 2
) -> bool:
    normalized_name_a, normalized_name_b = (
        stitch_norm(a.name),
        stitch_norm(b_activity.name),
    )

    if normalized_name_a == normalized_name_b:
        logger.debug(
            f"Activities {a.name} and {b_activity.name} have the same normalized name: {normalized_name_a}. Stitching them."
        )
        return True

    if (
        Levenshtein.distance(
            normalized_name_a.replace(" ", ""), normalized_name_b.replace(" ", "")
        )
        <= max_dist
    ):
        return True

    normalised_desc_a, normalized_desc_b = (
        stitch_norm(a.description),
        stitch_norm(b_activity.description),
    )

    if normalised_desc_a == normalized_desc_b:
        logger.debug(
            f"Activities {a.name} and {b_activity.name} have the same normalized description: {normalised_desc_a}. Stitching them."
        )
        return True

    return False


def _find_potential_matches(
    stitchable_activities: list[DBActivityWithLatestEvent],
    generated_timeline_activites: dict[str, baml_types.ActivityMetadata],
    llm_id_to_sorted_events: dict[str, list[baml_types.Event]],
    aggregation_time_span: TimeSpan,
    max_activity_pause_time: timedelta,
) -> defaultdict[int, list[str]]:
    stitchable_activity_id_to_potential_matches = defaultdict(list)

    for stitchable_activity in stitchable_activities:
        preexisting_activity_is_ongoing = (
            stitchable_activity.latest_event.event_type == ActivityEventType.OPEN
        )

        for new_activity_llm_id, _ in generated_timeline_activites.items():
            first_activity_event_t = llm_id_to_sorted_events[new_activity_llm_id][0].t
            first_activity_event_timestamp = utils.mm_ss_string_to_datetime(
                start=aggregation_time_span.start_time, mm_ss=first_activity_event_t
            )

            if preexisting_activity_is_ongoing:
                last_confirmed_active = stitchable_activity.latest_aggregation.end_time
                pause_time = first_activity_event_timestamp - last_confirmed_active
            else:
                last_seen_active = stitchable_activity.latest_event.event_time
                pause_time = first_activity_event_timestamp - last_seen_active

            if pause_time <= max_activity_pause_time:
                stitchable_activity_id_to_potential_matches[
                    stitchable_activity.activity.id
                ].append(new_activity_llm_id)

    return stitchable_activity_id_to_potential_matches


def _perform_programmatic_stitching(
    stitchable_activities: list[DBActivityWithLatestEvent],
    new_activity_llm_id_to_activity: dict[str, baml_types.ActivityMetadata],
    stitchable_activity_id_to_potential_matches: defaultdict[int, list[str]],
) -> dict[int, str]:
    id_to_stitched_llm_id: dict[int, str] = {}
    stitched_llm_ids: set[str] = set()

    for stitchable_activity in stitchable_activities:
        assert stitchable_activity.activity.id is not None
        potential_matches = stitchable_activity_id_to_potential_matches[
            stitchable_activity.activity.id
        ]

        stitching_input = ActivityStitchingInput(
            name=stitchable_activity.activity.name,
            description=stitchable_activity.activity.description,
        )

        for new_activity_llm_id in potential_matches:
            if new_activity_llm_id in stitched_llm_ids:
                continue

            new_activity = new_activity_llm_id_to_activity[new_activity_llm_id]
            new_stitching_input = ActivityStitchingInput(
                name=new_activity.name,
                description=new_activity.description,
            )

            if to_stitch(stitching_input, new_stitching_input):
                logger.debug(
                    f"Stitching open activity {stitchable_activity.activity.name} with new activity {new_activity.name} due to programmatic match."
                )
                id_to_stitched_llm_id[stitchable_activity.activity.id] = (
                    new_activity_llm_id
                )
                stitched_llm_ids.add(new_activity_llm_id)
                break
    return id_to_stitched_llm_id


async def _perform_llm_stitching(
    stitchable_activities: list[DBActivityWithLatestEvent],
    new_activity_llm_id_to_activity: dict[str, baml_types.ActivityMetadata],
    id_to_stitched_llm_id: dict[int, str],
    llm_id_to_merged_activity: dict[str, baml_types.ActivityStitchOutput],
    baml_client_registry: ClientRegistry,
) -> tuple[dict[int, str], dict[str, baml_types.ActivityStitchOutput]]:
    """
    Perform LLM-based stitching for activities that didn't match programmatically.
    Makes all StitchOrSkip calls in parallel for better performance.
    Returns both the stitch mapping and the merged activity outputs.
    """
    stitched_llm_ids = set(id_to_stitched_llm_id.values())

    unmatched_stitchable_activities = [
        sa
        for sa in stitchable_activities
        if sa.activity.id not in id_to_stitched_llm_id
    ]

    unmatched_new_activities = {
        llm_id: activity
        for llm_id, activity in new_activity_llm_id_to_activity.items()
        if llm_id not in stitched_llm_ids
    }

    # Collect all potential stitch pairs to check
    stitch_checks = []
    for stitchable_activity in unmatched_stitchable_activities:
        assert stitchable_activity.activity.id is not None

        for new_activity_llm_id, new_activity in unmatched_new_activities.items():
            if new_activity_llm_id in stitched_llm_ids:
                continue

            input_a = baml_types.ActivityStitchingInput(
                name=stitchable_activity.activity.name,
                description=stitchable_activity.activity.description,
            )
            input_b = baml_types.ActivityStitchingInput(
                name=new_activity.name,
                description=new_activity.description,
            )

            stitch_checks.append(
                {
                    "stitchable_activity": stitchable_activity,
                    "new_activity_llm_id": new_activity_llm_id,
                    "new_activity": new_activity,
                    "input_a": input_a,
                    "input_b": input_b,
                }
            )

    # Make all LLM calls in parallel
    if stitch_checks:
        tasks = [
            b.StitchOrSkip(
                check["input_a"],
                check["input_b"],
                baml_options={"client_registry": baml_client_registry},
            )
            for check in stitch_checks
        ]

        results = await asyncio.gather(*tasks)

        # Process results: match each stitchable activity with first positive result
        for check, merged_activity in zip(stitch_checks, results):
            if merged_activity is not None:
                stitchable_activity_id = check["stitchable_activity"].activity.id
                new_activity_llm_id = check["new_activity_llm_id"]

                # Skip if this stitchable activity already matched
                if stitchable_activity_id in id_to_stitched_llm_id:
                    continue

                # Skip if this new activity already matched
                if new_activity_llm_id in stitched_llm_ids:
                    continue

                logger.debug(
                    f"Stitching open activity {check['stitchable_activity'].activity.name} "
                    f"with new activity {check['new_activity'].name} due to LLM match."
                )

                id_to_stitched_llm_id[stitchable_activity_id] = new_activity_llm_id
                llm_id_to_merged_activity[new_activity_llm_id] = merged_activity
                stitched_llm_ids.add(new_activity_llm_id)

    return id_to_stitched_llm_id, llm_id_to_merged_activity


async def _process_stitch_results(
    id_to_stitched_llm_id: dict[int, str],
    stitchable_activities: list[DBActivityWithLatestEvent],
    llm_id_to_sorted_events: dict[str, list[baml_types.Event]],
    aggregation_time_span: TimeSpan,
    previous_aggregation_end_time: datetime,
    time_for_uninterrupted_ongoing_stitch: timedelta,
    llm_id_to_merged_activity: dict[str, baml_types.ActivityStitchOutput],
) -> StitchTimelineOutput:
    """
    Process stitch results and create events.
    For programmatic matches, uses original activity name/description.
    For LLM matches, uses the merged activity from llm_id_to_merged_activity.
    """
    stitched_activities_events: list[NewActivityEventExistingActivity] = []
    unstitched_activities_close_events: list[NewActivityEventExistingActivity] = []
    activities_to_update: list[tuple[int, dict[str, str]]] = []
    llm_id_to_stitch_result: dict[str, StitchResult] = {}

    for stitchable_activity in stitchable_activities:
        stitchable_activity_id = stitchable_activity.activity.id
        assert (
            stitchable_activity_id is not None
        ), "Stitchable activity ID must not be None"

        matched_llm_id = id_to_stitched_llm_id.get(stitchable_activity_id)
        is_open = stitchable_activity.latest_event.event_type == ActivityEventType.OPEN

        if matched_llm_id is None:
            if is_open:
                logger.debug(
                    f"Open activity {stitchable_activity.activity.name} has no match. Closing it!"
                )
                unstitched_activities_close_events.append(
                    NewActivityEventExistingActivity(
                        event_time=previous_aggregation_end_time,
                        event_type=ActivityEventType.CLOSE,
                        activity_id=stitchable_activity_id,
                    )
                )
        else:
            # This activity was stitched
            if matched_llm_id in llm_id_to_stitch_result:
                # Already processed this llm_id (can happen if multiple stitchable activities match the same new activity)
                continue

            # For programmatic matches: use existing name/description (they're nearly identical)
            # For LLM matches: use the merged activity
            if matched_llm_id in llm_id_to_merged_activity:
                # LLM-stitched: use merged result
                joint_activity = llm_id_to_merged_activity[matched_llm_id]
            else:
                # Programmatically stitched: keep original (names are already nearly identical)
                joint_activity = baml_types.ActivityStitchOutput(
                    name=stitchable_activity.activity.name,
                    description=stitchable_activity.activity.description,
                )

            delete_first_generated_event = False
            if is_open:
                first_activity_event = llm_id_to_sorted_events[matched_llm_id][0]
                first_activity_event_timestamp = utils.mm_ss_string_to_datetime(
                    start=aggregation_time_span.start_time,
                    mm_ss=first_activity_event.t,
                )

                last_confirmed_active = stitchable_activity.latest_aggregation.end_time
                pause_duration = first_activity_event_timestamp - last_confirmed_active

                if pause_duration > time_for_uninterrupted_ongoing_stitch:
                    stitched_activities_events.append(
                        NewActivityEventExistingActivity(
                            event_time=first_activity_event_timestamp,
                            event_type=ActivityEventType.OPEN,
                            activity_id=stitchable_activity_id,
                        )
                    )
                else:
                    delete_first_generated_event = True

            llm_id_to_stitch_result[matched_llm_id] = StitchResult(
                id=stitchable_activity_id,
                stitched_activity=joint_activity,
                delete_first_generated_event=delete_first_generated_event,
            )

    for new_activity_llm_id, stitched_result in llm_id_to_stitch_result.items():
        new_activity_events = llm_id_to_sorted_events[new_activity_llm_id]
        if stitched_result.delete_first_generated_event:
            if new_activity_events:
                del new_activity_events[0]

        activities_to_update.append(
            (
                stitched_result.id,
                {
                    "name": stitched_result.stitched_activity.name,
                    "description": stitched_result.stitched_activity.description,
                },
            )
        )

        for event in new_activity_events:
            event_time = utils.mm_ss_string_to_datetime(
                start=aggregation_time_span.start_time, mm_ss=event.t
            )
            stitched_activities_events.append(
                NewActivityEventExistingActivity(
                    event_time=event_time,
                    event_type=ActivityEventType(event.event_type),
                    activity_id=stitched_result.id,
                )
            )

    return StitchTimelineOutput(
        stitchable_activity_to_llm_id=id_to_stitched_llm_id,
        stitched_activities_events=stitched_activities_events,
        unstitched_activities_close_events=unstitched_activities_close_events,
        activities_to_update=activities_to_update,
    )


async def stitch_timeline(
    generated_timeline_activites: dict[str, baml_types.ActivityMetadata],
    generated_timeline_events: list[baml_types.Event],
    aggregation_time_span: TimeSpan,
    previous_aggregation_end_time: datetime | None,
    stitchable_activities: list[DBActivityWithLatestEvent],
    max_activity_pause_time: timedelta,
    baml_client_registry: ClientRegistry,
    time_for_uninterrupted_ongoing_stitch: timedelta = timedelta(seconds=30),
) -> StitchTimelineOutput:
    if previous_aggregation_end_time is None:
        logger.warning(
            "No previous aggregation end time, cannot stitch. Returning empty output."
        )
        return StitchTimelineOutput(
            stitchable_activity_to_llm_id={},
            stitched_activities_events=[],
            unstitched_activities_close_events=[],
            activities_to_update=[],
        )

    # Prepare data structures
    new_activity_llm_id_to_activity: dict[str, baml_types.ActivityMetadata] = (
        generated_timeline_activites
    )
    llm_id_to_sorted_events: dict[str, list[baml_types.Event]] = defaultdict(list)
    for event in generated_timeline_events:
        llm_id_to_sorted_events[event.activity_id].append(event)
    for llm_id in llm_id_to_sorted_events:
        llm_id_to_sorted_events[llm_id].sort(
            key=lambda x: utils.mm_ss_to_timedelta(x.t)
        )

    # 1. Find potential matches
    stitchable_activity_id_to_potential_matches = _find_potential_matches(
        stitchable_activities=stitchable_activities,
        generated_timeline_activites=generated_timeline_activites,
        llm_id_to_sorted_events=llm_id_to_sorted_events,
        aggregation_time_span=aggregation_time_span,
        max_activity_pause_time=max_activity_pause_time,
    )

    # 2. Programmatic stitching (for nearly identical names)
    id_to_stitched_llm_id = _perform_programmatic_stitching(
        stitchable_activities=stitchable_activities,
        new_activity_llm_id_to_activity=new_activity_llm_id_to_activity,
        stitchable_activity_id_to_potential_matches=stitchable_activity_id_to_potential_matches,
    )

    # 3. LLM stitching for remaining activities (single call: decide + merge)
    llm_id_to_merged_activity: dict[str, baml_types.ActivityStitchOutput] = {}
    id_to_stitched_llm_id, llm_id_to_merged_activity = await _perform_llm_stitching(
        stitchable_activities=stitchable_activities,
        new_activity_llm_id_to_activity=new_activity_llm_id_to_activity,
        id_to_stitched_llm_id=id_to_stitched_llm_id,
        llm_id_to_merged_activity=llm_id_to_merged_activity,
        baml_client_registry=baml_client_registry,
    )

    # 4. Process results and create events
    stitch_output = await _process_stitch_results(
        id_to_stitched_llm_id=id_to_stitched_llm_id,
        stitchable_activities=stitchable_activities,
        llm_id_to_sorted_events=llm_id_to_sorted_events,
        aggregation_time_span=aggregation_time_span,
        previous_aggregation_end_time=previous_aggregation_end_time,
        time_for_uninterrupted_ongoing_stitch=time_for_uninterrupted_ongoing_stitch,
        llm_id_to_merged_activity=llm_id_to_merged_activity,
    )

    return stitch_output
