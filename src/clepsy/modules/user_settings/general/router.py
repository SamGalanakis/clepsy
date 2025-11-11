import json

from fastapi import APIRouter, Depends, Form, status
from fastapi.responses import HTMLResponse

from clepsy.central_cache import central_cache, user_settings_ttl
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import update_user_settings as update_user_settings_query
from clepsy.entities import UserSettings
from clepsy.frontend.components import common_timezones_list
from clepsy.modules.user_settings.general.page import create_general_settings_page


router = APIRouter()


@router.post("/user-settings/general")
async def update_general_settings(
    username: str = Form(...),
    timezone: str = Form(...),
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    username_error = None
    timezone_error = None

    if not username.strip():
        username_error = "Username is required"
    if timezone not in common_timezones_list:
        timezone_error = "Invalid timezone"

    if any([username_error, timezone_error]):
        page = await create_general_settings_page(
            user_settings=user_settings,
            username_error=username_error,
            timezone_error=timezone_error,
            username_value=username,
            timezone_value=timezone,
        )
        return HTMLResponse(content=page, status_code=status.HTTP_200_OK)

    settings_to_update = {
        "username": username,
        "timezone": timezone,
    }

    async with get_db_connection() as conn:
        updated_user_settings = await update_user_settings_query(
            conn, settings=settings_to_update
        )
        assert updated_user_settings, "User settings not found after update"
    await central_cache.set(
        "user_settings", updated_user_settings, ttl=user_settings_ttl
    )  # type: ignore
    response_content = await create_general_settings_page(
        user_settings=updated_user_settings,
        username_value=username,
        timezone_value=timezone,
    )

    response = HTMLResponse(content=response_content, status_code=status.HTTP_200_OK)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": "Settings Saved",
                    "description": "Your general settings have been updated.",
                }
            }
        }
    )
    return response
