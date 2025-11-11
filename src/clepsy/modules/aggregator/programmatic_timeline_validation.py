from collections import defaultdict
from datetime import timedelta
from typing import List

from loguru import logger

import baml_client.types as baml_types
from clepsy import utils
from clepsy.config import config
import clepsy.entities as E


def validate_aggregator_core_output(
    output: E.AggregatorCoreOutput,
    aggregation_time_span: E.TimeSpan,
    stitchable_activities: List[E.DBActivityWithLatestEvent],
) -> list[str]:
    """Validate the AggregatorCoreOutput for correctness."""
    errors = []
    new_activity_llm_ids = set(output.new_activities.keys())
    old_activity_ids = set([x.activity.id for x in stitchable_activities])

    new_activity_llm_id_to_events = defaultdict(list)
    for event in output.new_activity_events:
        if event.activity_id not in new_activity_llm_ids:
            errors.append(
                f"Event activity_id '{event.activity_id}' not found in new_activities"
            )
        new_activity_llm_id_to_events[event.activity_id].append(event)

        event_timedelta = utils.mm_ss_to_timedelta(event.t)
        if not (
            timedelta(seconds=0) <= event_timedelta <= aggregation_time_span.duration
        ):
            errors.append(
                f"Event time '{event.t}' is outside the aggregation time span"
            )

    for new_activity_id, events in new_activity_llm_id_to_events.items():
        sorted_events = sorted(events, key=lambda e: utils.mm_ss_to_timedelta(e.t))
        if not sorted_events:
            continue
        previous_event_type = sorted_events[0].event_type

        if previous_event_type != "open":
            errors.append(
                f"First event for new activity '{new_activity_id}' must be 'open', found '{previous_event_type}'"
            )
        for event in sorted_events[1:]:
            if event.event_type == previous_event_type:
                errors.append(
                    f"Events for activity '{new_activity_id}' must alternate between 'open' and 'close', found two consecutive '{event.event_type}' events"
                )
            if previous_event_type == "close":
                time_to_previous_event = utils.mm_ss_to_timedelta(
                    event.t
                ) - utils.mm_ss_to_timedelta(sorted_events[0].t)
                if (
                    time_to_previous_event.total_seconds()
                    > config.max_pause_time_seconds
                ):
                    errors.append(
                        f"Time between 'open' and 'close' events for activity '{new_activity_id}' exceeds maximum allowed pause time of {config.max_pause_time_seconds} seconds"
                    )
            previous_event_type = event.event_type

    for event in (
        output.stitched_activities_events + output.unstitched_activities_close_events
    ):
        if not (
            aggregation_time_span.start_time
            <= event.event_time
            <= aggregation_time_span.end_time
        ):
            errors.append(
                f"Event time '{event.event_time}' is outside the aggregation time span"
            )
        if event.activity_id not in old_activity_ids:
            errors.append(f"Event {event} not found in old activities")

    return errors


def validate_timeline_programmatically(
    timeline: baml_types.Timeline,
    aggregation_time_span: E.TimeSpan,
) -> List[str]:
    """
    Validates that the generated timeline follows the correct format and rules.
    - All events are within the aggregation time span.
    - All activity_ids in events are either in the activities map or from open_auto_activities.
    - All activity_ids in the activities map are present in at least one event.
    - The first event for a new activity is always 'open'.
    - Events for each activity alternate between 'open' and 'close'.
    - Timestamps for events are sorted.
    """
    errors: List[str] = []
    # 1. Check if timeline events are sorted by timestamp
    if len(timeline.events) > 1:
        last_event_time = utils.mm_ss_string_to_datetime(
            aggregation_time_span.start_time, timeline.events[0].t
        )
        for event in timeline.events[1:]:
            current_event_time = utils.mm_ss_string_to_datetime(
                aggregation_time_span.start_time, event.t
            )
            if current_event_time < last_event_time:
                logger.warning(
                    f"Events are not sorted by timestamp. Previous: {last_event_time}, Current: {current_event_time}"
                )
            last_event_time = current_event_time

    # 2. All events must be within the aggregation time span

    sorted_timeline_events = sorted(
        timeline.events, key=lambda e: utils.mm_ss_to_timedelta(e.t)
    )

    for event in sorted_timeline_events:
        event_time = utils.mm_ss_string_to_datetime(
            aggregation_time_span.start_time, event.t
        )
        if not (aggregation_time_span.start_time <= event_time):
            errors.append(
                f"Event {event.activity_id} at {event.t} is before the aggregation span starts {aggregation_time_span.start_time}"
            )
        if not (event_time <= aggregation_time_span.end_time):
            errors.append(
                f"Event {event.activity_id} at {event.t} is after the aggregation span ends {aggregation_time_span.end_time}"
            )

    # 3. Activity ID consistency checks
    event_activity_ids = set(event.activity_id for event in timeline.events)
    defined_activity_ids = set(timeline.activities.keys())

    # 3a. All event activity_ids must be in defined activities or open activities
    allowed_activity_ids = defined_activity_ids
    unexplained_event_ids = event_activity_ids - allowed_activity_ids
    if unexplained_event_ids:
        errors.append(
            f"Found events for activity IDs not present in the activities map or open activities: {unexplained_event_ids}"
        )

    # 3b. All defined activity_ids must have at least one event
    unused_activity_ids = defined_activity_ids - event_activity_ids
    if unused_activity_ids:
        errors.append(
            f"Activity IDs defined in the activities map but have no corresponding events: {unused_activity_ids}"
        )

    # 4. Per-activity validation
    events_by_activity = defaultdict(list)
    for event in sorted_timeline_events:
        events_by_activity[event.activity_id].append(event)

    for activity_id, events in events_by_activity.items():
        # events are sorted by time because the whole list is sorted.

        last_event_type = None

        for event in events:
            current_event_type = event.event_type
            if last_event_type:
                if current_event_type == last_event_type:
                    errors.append(
                        f"Activity '{activity_id}' has non-alternating event types: {last_event_type} -> {current_event_type} for event at {event.t}"
                    )
            else:
                # This is a new activity, first event must be 'open'
                if current_event_type != "open":
                    errors.append(
                        f"First event for new activity '{activity_id}' must be 'open', but got '{current_event_type}' for event at {event.t}"
                    )
            last_event_type = current_event_type
    return errors
