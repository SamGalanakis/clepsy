from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger

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
    conn = get_connection()
    entry = {  # bytes-safe; valkey will handle encoding
        "type": event_type,
        "ts": str(to_ms(timestamp)),
        "payload": payload_json,
    }
    # Use event-time based ID to enable XRANGE by window using ms bounds
    msg_id_base = f"{to_ms(timestamp)}-0"
    try:
        return conn.xadd(SOURCE_EVENTS_STREAM, entry, id=msg_id_base)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Failed to XADD source event to stream")
        raise


def xrange_source_events(*, start: datetime, end: datetime) -> list[dict]:
    """Read events from the source stream within [start, end] by stream ID range.

    Returns a list of {"id": str, "event_type": str, "payload_json": str} dicts.
    """
    conn = get_connection()
    start_id = f"{to_ms(start)}-0"
    end_id = f"{to_ms(end)}-999999"
    try:
        entries: Iterable = conn.xrange(SOURCE_EVENTS_STREAM, min=start_id, max=end_id)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("Failed to XRANGE source events stream")
        raise
    out: list[dict] = []
    for msg_id, fields in entries:
        # fields is a dict-like of bytes->bytes (decode_responses=False)
        etype = fields.get(b"type")
        payload = fields.get(b"payload")
        if etype is None or payload is None:
            continue
        out.append(
            {
                "id": msg_id.decode()
                if isinstance(msg_id, (bytes, bytearray))
                else str(msg_id),
                "event_type": etype.decode()
                if isinstance(etype, (bytes, bytearray))
                else str(etype),
                "payload_json": payload.decode()
                if isinstance(payload, (bytes, bytearray))
                else str(payload),
            }
        )
    return out
