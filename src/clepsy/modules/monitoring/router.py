from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from clepsy.entities import WorkerName
from clepsy.frontend.components.base_page import create_base_page
from clepsy.modules.monitoring.page import (
    create_worker_logs_modal_content,
    create_workers_page,
    create_workers_table_card,
)


router = APIRouter(prefix="/monitoring")


@router.get("/")
async def monitoring_home(request: Request) -> HTMLResponse:
    content = create_workers_page()
    if request.state.is_htmx:
        return HTMLResponse(content)
    return HTMLResponse(
        create_base_page(
            page_title="Monitoring",
            content=content,
            user_settings=None,
        )
    )


@router.get("/workers")
async def monitoring_workers(request: Request) -> HTMLResponse:
    content = create_workers_page()
    if request.state.is_htmx:
        return HTMLResponse(content)
    return HTMLResponse(
        create_base_page(
            page_title="Monitoring — Workers",
            content=content,
            user_settings=None,
        )
    )


@router.get("/workers/table")
async def monitoring_workers_table(_: Request) -> HTMLResponse:
    """Return just the workers table card for HTMX polling swaps."""
    return HTMLResponse(create_workers_table_card())


@router.get("/workers/logs")
async def monitoring_worker_logs(name: WorkerName = Query(...)) -> HTMLResponse:
    """Return the logs modal panel content for a specific worker.

    This endpoint is designed to be requested via HTMX and swapped into the
    modal content container.
    """
    panel = create_worker_logs_modal_content(worker_name=name)
    return HTMLResponse(panel)
