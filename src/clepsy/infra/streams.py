from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from valkey.exceptions import ResponseError as StreamResponseError  # type: ignore

from clepsy.infra.valkey_client import get_connection


SOURCE_EVENTS_STREAM = "source:events"


def to_ms(ts: datetime) -> int:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp() * 1000)


def xadd_source_event(
    *, event_type: str, timestamp: datetime, payload_json: str
) -> str:
    """Append a source event to the Valkey stream using the event timestamp as the ID base.

    Returns the message ID assigned by Valkey.
    """
    conn = get_connection(decode_responses=True)
    entry = {  # bytes-safe; valkey will handle encoding
        "type": event_type,
        "ts": str(to_ms(timestamp)),
        "payload": payload_json,
    }
    # Use event-time based ID to enable XRANGE by window using ms bounds.
    # Let Valkey pick a monotonically increasing sequence for the same ms to avoid collisions.
    msg_id_base = f"{to_ms(timestamp)}-*"
    try:
        return conn.xadd(SOURCE_EVENTS_STREAM, entry, id=msg_id_base)  # type: ignore[attr-defined]
    except StreamResponseError as e:
        # This happens if the specified ID would be <= the top item (e.g., backfill older timestamps).
        # Fallback to server-assigned ID to avoid dropping the event; the payload still carries the true event ts.
        logger.warning(
            "XADD with event-time ID {} failed ({}); falling back to server-assigned ID (*)",
            msg_id_base,
            e,
        )
        return conn.xadd(SOURCE_EVENTS_STREAM, entry)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Failed to XADD source event to stream")
        raise


def xrange_source_events(*, start: datetime, end: datetime) -> list[dict]:
    """Read events from the source stream within [start, end] by stream ID range.

    Returns a list of {"id": str, "event_type": str, "payload_json": str} dicts.
    """
    conn = get_connection(decode_responses=True)
    start_id = f"{to_ms(start)}-0"
    end_id = f"{to_ms(end)}-999999"
    try:
        entries: Iterable = conn.xrange(SOURCE_EVENTS_STREAM, min=start_id, max=end_id)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Failed to XRANGE source events stream")
        raise
    out: list[dict] = []
    for msg_id, fields in entries:
        etype = fields.get("type")
        payload = fields.get("payload")
        if etype is None or payload is None:
            continue
        out.append(
            {
                "id": str(msg_id),
                "event_type": str(etype),
                "payload_json": str(payload),
            }
        )
    return out
