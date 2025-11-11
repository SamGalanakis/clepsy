"""JSON serializers for different activity spec types."""

from clepsy import utils
from clepsy.entities import (
    DBActivitySpec,
    DBActivitySpecWithTags,
    DBActivitySpecWithTagsAndSessions,
)


def db_activity_spec_to_json_serializable(
    spec: DBActivitySpec,
) -> dict:
    """
    Converts a DBActivitySpec object to a JSON-serializable dictionary.

    Args:
        spec: The DBActivitySpec object to convert.

    Returns:
        A dictionary that can be directly serialized to JSON using json.dumps().
    """
    activity_data = {
        "name": spec.activity.name,
        "description": spec.activity.description,
        "productivity_level": spec.activity.productivity_level.value,
        "is_manual": spec.activity.is_manual,
        "id": spec.activity.id,
    }

    events_data = []
    for event in spec.events:
        event_data = {
            "event_type": event.event_type.value,
            "event_time": utils.datetime_to_iso_8601(event.event_time),
            "id": event.id,
            "aggregation_id": event.aggregation_id,
            "activity_id": event.activity_id,
        }
        events_data.append(event_data)

    result = {
        "activity": activity_data,
        "events": events_data,
    }

    return result


def db_activity_spec_with_tags_to_json_serializable(
    spec: DBActivitySpecWithTags,
) -> dict:
    """
    Converts a DBActivitySpecWithTags object to a JSON-serializable dictionary.

    Args:
        spec: The DBActivitySpecWithTags object to convert.

    Returns:
        A dictionary that can be directly serialized to JSON using json.dumps().
    """
    activity_data = {
        "name": spec.activity.name,
        "description": spec.activity.description,
        "productivity_level": spec.activity.productivity_level.value,
        "is_manual": spec.activity.is_manual,
        "id": spec.activity.id,
        "tags": [
            {"id": tag.id, "name": tag.name, "description": tag.description}
            for tag in spec.tags
        ],
    }

    events_data = []
    for event in spec.events:
        event_data = {
            "event_type": event.event_type.value,
            "event_time": utils.datetime_to_iso_8601(event.event_time),
            "id": event.id,
            "aggregation_id": event.aggregation_id,
            "activity_id": event.activity_id,
        }
        events_data.append(event_data)

    result = {
        "activity": activity_data,
        "events": events_data,
    }

    return result


def db_activity_spec_with_tags_and_sessions_to_json_serializable(
    spec: DBActivitySpecWithTagsAndSessions,
) -> dict:
    """
    Converts a DBActivitySpecWithTagsAndSessions object to a JSON-serializable dictionary,
    keeping all activity-related information under the 'activity' key.

    Args:
        spec: The DBActivitySpecWithTagsAndSessions object to convert.

    Returns:
        A dictionary that can be directly serialized to JSON using json.dumps().
    """
    activity_data = {
        "name": spec.activity.name,
        "description": spec.activity.description,
        "productivity_level": spec.activity.productivity_level.value,
        "is_manual": spec.activity.is_manual,
        "id": spec.activity.id,
        "tags": [
            {"id": tag.id, "name": tag.name, "description": tag.description}
            for tag in spec.tags
        ],
    }

    events_data = []
    for event in spec.events:
        event_data = {
            "event_type": event.event_type.value,
            "event_time": utils.datetime_to_iso_8601(event.event_time),
            "id": event.id,
            "aggregation_id": event.aggregation_id,
            "activity_id": event.activity_id,
        }
        events_data.append(event_data)

    # Serialize finalized session (if exists)
    session_data = None
    if spec.session:
        session_data = {
            "id": spec.session.id,
            "name": spec.session.name,
            "llm_id": spec.session.llm_id,
            "created_at": utils.datetime_to_iso_8601(spec.session.created_at),
            "sessionization_run_id": spec.session.sessionization_run_id,
        }

    # Serialize candidate sessions
    candidate_sessions_data = [
        {
            "id": cs.id,
            "name": cs.name,
            "llm_id": cs.llm_id,
            "created_at": utils.datetime_to_iso_8601(cs.created_at),
            "sessionization_run_id": cs.sessionization_run_id,
        }
        for cs in spec.candidate_sessions
    ]

    result = {
        "activity": activity_data,
        "events": events_data,
        "session": session_data,
        "candidate_sessions": candidate_sessions_data,
    }

    return result
