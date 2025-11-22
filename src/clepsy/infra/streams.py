# ruff: noqa: I001

"""Utilities for interacting with the Valkey source events stream."""

from datetime import datetime, timezone
from typing import Iterable

from loguru import logger
from valkey.exceptions import (
    LockNotOwnedError,
    ResponseError as StreamResponseError,
)  # type: ignore

from clepsy.infra.valkey_client import get_connection


SOURCE_EVENTS_STREAM = "source:events"
DEV_STREAM_FLUSH_LOCK_KEY = "dev:source_stream:flush_lock"


def flush_valkey() -> None:
    try:
        conn = get_connection(decode_responses=True)
        lock = conn.lock(DEV_STREAM_FLUSH_LOCK_KEY, timeout=10, blocking_timeout=0)  # type: ignore[attr-defined]
    except Exception:
        logger.debug("[dev] Failed to acquire dev flush lock")
        return

    acquired = False
    try:
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.debug(
                "[dev] Source events stream flush already handled by other worker",
            )
            return

        conn.flushall()
        logger.info(
            "[dev] Flushed Valkey completely!",
        )
    except Exception:
        logger.exception("[dev] Failed to flush Valkey")
    finally:
        if acquired:
            try:
                lock.release()
            except LockNotOwnedError:
                logger.debug(
                    "[dev] Flush lock key already cleared; skipping release",
                )
            except Exception:
                logger.exception("[dev] Failed to release dev flush lock")


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


def get_oldest_source_event_timestamp() -> datetime | None:
    """Get the timestamp of the oldest event in the source events stream.

    Returns None if the stream is empty.
    """
    conn = get_connection(decode_responses=True)
    # Get the first entry in the stream (oldest)
    entries: Iterable = conn.xrange(SOURCE_EVENTS_STREAM, min="-", max="+", count=1)  # type: ignore[attr-defined]
    entries_list = list(entries)
    if not entries_list:
        return None

    # Extract timestamp from message ID (format: "{timestamp_ms}-{sequence}")
    msg_id, _ = entries_list[0]
    timestamp_ms = int(str(msg_id).split("-")[0])
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)


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
