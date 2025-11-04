from fastapi import APIRouter, HTTPException
from rq import Queue

from clepsy.entities import MobileAppUsageEvent
from clepsy.infra.rq_setup import get_connection
from clepsy.jobs.mobile import persist_mobile_app_usage_job


router = APIRouter(prefix="/mobile")


@router.post("/app-usage")
async def receive_mobile_app_usage(event: MobileAppUsageEvent) -> dict | None:
    try:
        # Validate schema, then enqueue persistence job (job performs anonymization)
        MobileAppUsageEvent.model_validate(event.model_dump())
        q = Queue("default", connection=get_connection())  # type: ignore[arg-type]
        q.enqueue(
            persist_mobile_app_usage_job,
            event.model_dump(),
            job_timeout=60,
            result_ttl=0,
            failure_ttl=24 * 3600,
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
