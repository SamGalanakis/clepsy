import base64
from datetime import datetime, timezone as dt_timezone
import hashlib
import os

from fastapi import APIRouter, HTTPException, Request

from clepsy.auth.auth import verify_password
from clepsy.db.db import get_db_connection
import clepsy.db.queries as queries
from clepsy.db.queries import (
    delete_current_enrollment_code,
    insert_source,
    select_current_enrollment_code,
)
from clepsy.entities import (
    DBDeviceSource,
    SourcePairRequest,
    SourcePairResponse,
    SourceStatus,
)


router = APIRouter(prefix="/sources")


@router.put("/source-heartbeats")
async def receive_heartbeat(
    request: Request,
) -> None:
    try:
        source: DBDeviceSource = getattr(request.state, "device_source")  # type: ignore[attr-defined]
        assert (
            source is not None
        ), "Device source must be set in request.state by middleware"

        async with get_db_connection(
            include_uuid_func=False, commit_on_exit=True
        ) as conn:
            await queries.update_source_last_seen(
                conn, source_id=source.id, when=datetime.now(dt_timezone.utc)
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/pair", response_model=SourcePairResponse)
async def redeem_enrollment_code(body: SourcePairRequest) -> SourcePairResponse:
    try:
        now = datetime.now(dt_timezone.utc)
        async with get_db_connection() as conn:
            # Fetch current enrollment code via DB helper
            enrollment = await select_current_enrollment_code(conn)

            if enrollment is None:
                raise HTTPException(status_code=404, detail="No active enrollment code")

            code_hash: str = enrollment.code_hash
            expires_at = enrollment.expires_at

            if expires_at:
                if now > expires_at:
                    # Expired; clear code to be safe
                    await delete_current_enrollment_code(conn)
                    await conn.commit()
                    raise HTTPException(
                        status_code=400, detail="Enrollment code expired"
                    )

            if not verify_password(code_hash, body.code):
                raise HTTPException(status_code=401, detail="Invalid enrollment code")

            # Generate device token: 32 random bytes -> urlsafe base64 string (no padding)
            raw = os.urandom(32)
            device_token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
            # Store SHA-256 hash (hex) of raw bytes in DB
            token_hash = hashlib.sha256(raw).hexdigest()

            # Create the source row
            name = body.device_name.strip()
            created = await insert_source(
                conn,
                name=name,
                source_type=body.source_type,
                token_hash=token_hash,
                status=SourceStatus.ACTIVE,
            )

            # One-time use: remove the code
            await delete_current_enrollment_code(conn)
            await conn.commit()

        return SourcePairResponse(source_id=created.id, device_token=device_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
