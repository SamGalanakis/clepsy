from fastapi import APIRouter, HTTPException
from loguru import logger

from clepsy.entities import MobileAppUsageEvent
from clepsy.jobs.mobile import persist_mobile_app_usage_job


router = APIRouter(prefix="/mobile")


@router.post("/app-usage")
async def receive_mobile_app_usage(event: MobileAppUsageEvent) -> dict | None:
    try:
        payload = event.model_dump(mode="json")
        logger.debug("Received mobile app usage event {}", payload)
        persist_mobile_app_usage_job.send(payload)
        return None
    except HTTPException:
        logger.error("HTTPException receiving mobile app usage event")
        raise
    except Exception as e:
        logger.error(f"Error receiving mobile app usage event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
