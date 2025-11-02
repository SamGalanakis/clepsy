import asyncio

from fastapi import APIRouter, HTTPException

from clepsy.config import config
from clepsy.entities import MobileAppUsageEvent
from clepsy.modules.pii.pii import (
    DEFAULT_PII_ENTITY_TYPES,
    anonymize_text,
)
from clepsy.queues import event_bus


router = APIRouter(prefix="/mobile")


async def anonymize_mobile_app_usage_event(
    event: MobileAppUsageEvent,
) -> MobileAppUsageEvent:
    if event.notification_text:
        event.notification_text = await asyncio.to_thread(
            anonymize_text,
            text=event.notification_text,
            entity_types=DEFAULT_PII_ENTITY_TYPES,
            threshold=config.gliner_pii_threshold,
        )

    return event


@router.post("/app-usage")
async def receive_mobile_app_usage(event: MobileAppUsageEvent) -> dict | None:
    try:
        event = await anonymize_mobile_app_usage_event(event)
        await event_bus.publish(event)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
