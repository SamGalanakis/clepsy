from datetime import timezone

from fastapi import APIRouter, HTTPException

from clepsy.entities import MobileAppUsageEvent
from clepsy.jobs.mobile import persist_mobile_app_usage_job


router = APIRouter(prefix="/mobile")


@router.post("/app-usage")
async def receive_mobile_app_usage(event: MobileAppUsageEvent) -> dict | None:
    try:
        # Validate schema, then dispatch actor (job performs anonymization)
        MobileAppUsageEvent.model_validate(event.model_dump())

        # Serialize timestamp as ISO8601 naive in UTC for message safety
        ts = event.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_utc = ts.astimezone(timezone.utc)
        payload = event.model_dump()
        payload["timestamp"] = ts_utc.replace(tzinfo=None).isoformat()

        persist_mobile_app_usage_job.send(payload)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
