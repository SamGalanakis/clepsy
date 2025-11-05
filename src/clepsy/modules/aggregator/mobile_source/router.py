from fastapi import APIRouter, HTTPException

from clepsy.entities import MobileAppUsageEvent
from clepsy.jobs.mobile import persist_mobile_app_usage_job


router = APIRouter(prefix="/mobile")


@router.post("/app-usage")
async def receive_mobile_app_usage(event: MobileAppUsageEvent) -> dict | None:
    try:
        # Validate schema, then dispatch actor (job performs anonymization)
        MobileAppUsageEvent.model_validate(event.model_dump())
        persist_mobile_app_usage_job.send(event.model_dump())
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
