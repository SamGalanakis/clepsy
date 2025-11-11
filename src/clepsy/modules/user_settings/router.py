"""Central user settings router that delegates to sub-routers.

This router registers sub-routers for each settings domain and exposes a single
GET endpoint to load any settings page (HTMX-friendly). POST/test endpoints are
defined in their respective feature routers.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.entities import UserSettings
from clepsy.frontend.components import create_base_page
from clepsy.modules.user_settings.page import (
    create_tags_page,
)  # existing tags page builder
from clepsy.modules.user_settings.sources.router import router as sources_router

# Page builders
from .general.page import create_general_settings_page

# Sub-routers
from .general.router import router as general_router
from .llm_models.page import create_llm_models_page
from .llm_models.router import router as llm_models_router
from .password.page import create_password_page
from .password.router import router as password_router
from .productivity.page import create_productivity_page
from .productivity.router import router as productivity_router
from .sources.page import create_sources_page


router = APIRouter()
router.include_router(general_router)
router.include_router(password_router)
router.include_router(llm_models_router)
router.include_router(productivity_router)
router.include_router(sources_router)

SettingsPageName = Literal[
    "general",
    "password",
    "llm_models",
    "tags",
    "productivity",
    "sources",
]


@router.get("/user-settings/{page_name}")
async def user_settings_page(
    request: Request,
    page_name: SettingsPageName,
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    is_htmx = getattr(request.state, "is_htmx", False)
    async with get_db_connection(include_uuid_func=False) as conn:
        if page_name == "general":
            content = await create_general_settings_page(
                user_settings=user_settings,
                username_value=user_settings.username,
                timezone_value=user_settings.timezone,
            )
        elif page_name == "password":
            content = await create_password_page(user_settings=user_settings)
        elif page_name == "llm_models":
            content = await create_llm_models_page(user_settings=user_settings)
        elif page_name == "tags":
            content = await create_tags_page(conn=conn)
        elif page_name == "productivity":
            content = await create_productivity_page(user_settings=user_settings)
        elif page_name == "sources":
            content = await create_sources_page(conn=conn)
        else:
            raise HTTPException(status_code=404, detail="Page not found")

    if is_htmx:
        return HTMLResponse(content=content)
    return HTMLResponse(
        create_base_page(
            page_title="User Settings",
            content=content,
            user_settings=user_settings,
        )
    )
