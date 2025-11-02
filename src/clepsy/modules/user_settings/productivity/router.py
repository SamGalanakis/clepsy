import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from clepsy.central_cache import central_cache, user_settings_ttl
from clepsy.db.db import get_db_connection
from clepsy.db.queries import update_user_settings as update_user_settings_query
from clepsy.modules.user_settings.productivity.page import create_productivity_page


router = APIRouter()


@router.post("/user-settings/productivity")
async def update_productivity_settings(
    request: Request,
    productivity_prompt: str = Form(...),
) -> HTMLResponse:
    settings_to_update = {"productivity_prompt": productivity_prompt}
    async with get_db_connection() as conn:
        user_settings = await update_user_settings_query(
            conn, settings=settings_to_update
        )
    await central_cache.set(
        key="user_settings", value=user_settings, ttl=user_settings_ttl
    )  # type: ignore
    page = await create_productivity_page(user_settings=user_settings)
    response = HTMLResponse(content=page)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Settings Saved",
                    "description": "Your productivity settings have been updated.",
                }
            }
        }
    )
    return response
