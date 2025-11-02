import json
from json import JSONDecodeError, loads
from uuid import uuid4

import aiosqlite
from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from loguru import logger

from clepsy.auth.auth import encrypt_secret
from clepsy.auth.auth_middleware import create_jwt_token
from clepsy.config import config
from clepsy.db.db import get_db_connection
from clepsy.db.queries import (
    finalize_user_settings_from_draft,
    get_user_settings_draft,
    select_user_settings,
    update_user_settings_draft_llm_configs,
    update_user_settings_draft_productivity,
    update_user_settings_draft_tags,
    upsert_user_settings_draft_basics,
)
from clepsy.entities import AADS, ImageProcessingApproach, ModelProvider
from clepsy.frontend.components import common_timezones_list
from clepsy.frontend.components.base_page import create_base_page
from clepsy.modules.account_creation.page import (
    create_basics_page,
    create_connect_page,
    create_models_page,
    create_productivity_page,
    create_tags_page,
)
from clepsy.modules.user_settings.llm_models.router import validate_llm_models_form


# future steps will use encryption and finalize

router = APIRouter()
# Wizard step registry
STEPS: list[dict[str, str]] = [
    {"slug": "basics", "title": "Basics"},
    {"slug": "productivity", "title": "Productivity"},
    {"slug": "tags", "title": "Tags (Optional)"},
    {"slug": "models", "title": "Models"},
    {"slug": "connect", "title": "Connect Source (optional)"},
]


def slug_index(slug: str) -> int:
    for i, s in enumerate(STEPS):
        if s["slug"] == slug:
            return i
    return -1


def next_slug(slug: str) -> str | None:
    i = slug_index(slug)
    if i == -1:
        return None
    if i + 1 < len(STEPS):
        return STEPS[i + 1]["slug"]
    return None


def resume_slug_from_draft(draft: dict | None) -> str:
    if not draft or not (draft.get("username") and draft.get("timezone")):
        return "basics"
    if not draft.get("productivity_prompt"):
        return "productivity"
    # Step 3 (tags) is optional; skip to models
    return "models"


def get_step_title(slug: str) -> str:
    for s in STEPS:
        if s["slug"] == slug:
            return s["title"]
    return slug.capitalize()


# Helper to get or set wizard_id cookie
def ensure_wizard_id(request: Request, response: Response) -> str:
    wizard_id = request.cookies.get("wizard_id")
    if not wizard_id:
        wizard_id = uuid4().hex
        response.set_cookie("wizard_id", wizard_id, httponly=True)
    return wizard_id


@router.get("/create-account")
async def create_account_wizard_entry(request: Request) -> Response:
    async with get_db_connection(include_uuid_func=False) as conn:
        existing = await select_user_settings(conn)
        if existing is not None:
            return RedirectResponse(
                "/s/user-settings", status_code=status.HTTP_303_SEE_OTHER
            )
        # Try to resume existing draft if cookie present
        wizard_id_cookie = request.cookies.get("wizard_id")
        next_url = "/s/create-account/basics"
        if wizard_id_cookie:
            try:
                draft = await get_user_settings_draft(conn, wizard_id=wizard_id_cookie)
                if draft:
                    slug = resume_slug_from_draft(draft)
                    next_url = f"/s/create-account/{slug}"
            except aiosqlite.Error:
                pass

    # Start or resume
    resp = RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
    ensure_wizard_id(request, resp)
    return resp


@router.get("/create-account/basics")
async def create_account_basics_get(request: Request) -> Response:
    # Render the basics form (username, timezone)
    page = create_basics_page()
    if request.state.is_htmx:
        return HTMLResponse(page)
    return HTMLResponse(
        create_base_page(
            content=page,
            user_settings=None,
            page_title="Create Account — Basics",
            include_sidebar=False,
        )
    )


@router.post("/create-account/basics")
async def create_account_basics_post(
    request: Request,
    username: str = Form(""),
    timezone: str = Form("UTC"),
) -> Response:
    # Validate basics
    username_error = None
    timezone_error = None

    if not username.strip():
        username_error = "Username is required"
    # Password handled by user_auth; nothing to validate here
    if timezone not in common_timezones_list:
        timezone_error = "Invalid timezone"

    if username_error or timezone_error:
        page = create_basics_page(
            username_error=username_error,
            timezone_error=timezone_error,
            username_value=username,
            timezone_value=timezone,
        )
        return HTMLResponse(page)

    # Persist basics to draft
    try:
        async with get_db_connection() as conn:
            existing = await select_user_settings(conn)
            if existing is not None:
                return RedirectResponse(
                    "/s/user-settings", status_code=status.HTTP_303_SEE_OTHER
                )

            # ensure wizard id cookie exists
            response = JSONResponse({"ok": True})
            wizard_id = ensure_wizard_id(request, response)
            await upsert_user_settings_draft_basics(
                conn,
                wizard_id=wizard_id,
                username=username.strip(),
                timezone=timezone,
                description=None,
            )
            await conn.commit()

            # Go to next step
            response.headers["HX-Redirect"] = "/s/create-account/productivity"
            return response
    except (aiosqlite.Error, RuntimeError, ValueError) as exc:
        logger.exception(
            "Failed to persist account-creation step 1: {error}", error=exc
        )
        page = create_basics_page(
            username_error=str(exc),
            username_value=username,
            timezone_value=timezone,
        )
        return HTMLResponse(page)


@router.get("/create-account/productivity")
async def create_account_productivity_get(request: Request) -> Response:
    page = create_productivity_page()
    if request.state.is_htmx:
        return HTMLResponse(page)
    return HTMLResponse(
        create_base_page(
            content=page,
            user_settings=None,
            page_title="Create Account — Productivity",
            include_sidebar=False,
        )
    )


@router.post("/create-account/productivity")
async def create_account_productivity_post(
    request: Request,
    productivity_prompt: str = Form(""),
) -> Response:
    async with get_db_connection() as conn:
        existing = await select_user_settings(conn)
        if existing is not None:
            return RedirectResponse(
                "/s/user-settings", status_code=status.HTTP_303_SEE_OTHER
            )

        response = JSONResponse({"ok": True})
        wizard_id = ensure_wizard_id(request, response)
        await update_user_settings_draft_productivity(
            conn, wizard_id=wizard_id, productivity_prompt=productivity_prompt or ""
        )
    response.headers["HX-Redirect"] = "/s/create-account/tags"
    return response


@router.get("/create-account/tags")
async def create_account_tags_get(request: Request) -> Response:
    # Preload tags from existing draft if any
    initial_tags: list[dict] | None = None
    wizard_id_cookie = request.cookies.get("wizard_id")
    if wizard_id_cookie:
        async with get_db_connection() as conn:
            try:
                draft = await get_user_settings_draft(conn, wizard_id=wizard_id_cookie)
                if draft and draft.get("tags_json"):
                    try:
                        loaded = loads(draft["tags_json"]) or []
                    except JSONDecodeError:
                        loaded = []
                    if isinstance(loaded, list):
                        # Normalize
                        initial_tags = [
                            {
                                "id": str(t.get("id") or f"new-{i}"),
                                "name": t.get("name", ""),
                                "description": t.get("description", ""),
                            }
                            for i, t in enumerate(loaded)
                            if isinstance(t, dict)
                        ]
            except aiosqlite.Error:
                pass
    page = create_tags_page(initial_tags=initial_tags or [])
    if request.state.is_htmx:
        return HTMLResponse(page)
    return HTMLResponse(
        create_base_page(
            content=page,
            user_settings=None,
            page_title="Create Account — Tags",
            include_sidebar=False,
        )
    )


@router.post("/create-account/tags")
async def create_account_tags_post(
    request: Request, action: str = Form(None), tags_data: str = Form("")
) -> Response:
    # Validate JSON shape if provided unless skipping
    parsed_tags = None
    if action != "skip" and tags_data.strip():
        try:
            parsed_tags = json.loads(tags_data)
            if not (
                isinstance(parsed_tags, list)
                and all(isinstance(x, dict) for x in parsed_tags)
            ):
                raise ValueError("Tags must be a list of objects")
        except (json.JSONDecodeError, TypeError, ValueError):
            page = create_tags_page(initial_tags=parsed_tags or [])
            return HTMLResponse(page)

    async with get_db_connection() as conn:
        existing = await select_user_settings(conn)
        if existing is not None:
            return RedirectResponse(
                "/s/user-settings", status_code=status.HTTP_303_SEE_OTHER
            )

        response = JSONResponse({"ok": True})
        wizard_id = ensure_wizard_id(request, response)
        await update_user_settings_draft_tags(
            conn,
            wizard_id=wizard_id,
            tags_json=(None if action == "skip" else (tags_data or None)),
        )
    response.headers["HX-Redirect"] = "/s/create-account/models"
    return response


@router.get("/create-account/models")
async def create_account_models_get(request: Request) -> Response:
    page = create_models_page()
    if request.state.is_htmx:
        return HTMLResponse(page)
    return HTMLResponse(
        create_base_page(
            content=page,
            user_settings=None,
            page_title="Create Account — Models",
            include_sidebar=False,
        )
    )


@router.post("/create-account/models")
async def create_account_models_post(
    request: Request,
    image_model_provider: ModelProvider = Form(...),
    image_model_base_url: str | None = Form(None),
    image_model: str = Form(...),
    image_model_api_key: str | None = Form(None),
    text_model_provider: ModelProvider = Form(...),
    text_model_base_url: str | None = Form(None),
    text_model: str = Form(...),
    text_model_api_key: str | None = Form(None),
    image_processing_approach: ImageProcessingApproach = Form(...),
) -> Response:
    logger.debug("Handling POST /create-account/models submission")

    (
        image_provider_error,
        image_base_url_error,
        image_model_error,
        image_api_key_error,
        text_provider_error,
        text_base_url_error,
        text_model_error,
        text_api_key_error,
    ) = validate_llm_models_form(
        image_model_provider=image_model_provider,
        image_model_base_url=image_model_base_url,
        image_model=image_model,
        text_model_provider=text_model_provider,
        text_model_base_url=text_model_base_url,
        text_model=text_model,
        image_processing_approach=image_processing_approach,
    )
    if any(
        [
            image_provider_error,
            image_base_url_error,
            image_model_error,
            image_api_key_error,
            text_provider_error,
            text_base_url_error,
            text_model_error,
            text_api_key_error,
        ]
    ):
        page = create_models_page(
            image_model_provider_value=(
                image_model_provider.value if image_model_provider else None
            ),
            image_model_base_url_value=image_model_base_url,
            image_model_value=image_model,
            text_model_provider_value=(
                text_model_provider.value if text_model_provider else None
            ),
            text_model_base_url_value=text_model_base_url,
            text_model_value=text_model,
            image_provider_error=image_provider_error,
            image_base_url_error=image_base_url_error,
            image_model_error=image_model_error,
            image_api_key_error=image_api_key_error,
            text_provider_error=text_provider_error,
            text_base_url_error=text_base_url_error,
            text_model_error=text_model_error,
            text_api_key_error=text_api_key_error,
            image_processing_approach_value=image_processing_approach.value,
        )
        return HTMLResponse(page)

    text_model_api_key_enc = (
        encrypt_secret(
            text_model_api_key,
            config.master_key.get_secret_value(),
            aad=AADS.LLM_API_KEY,
        )
        if text_model_api_key
        else None
    )
    image_model_api_key_enc = (
        encrypt_secret(
            image_model_api_key,
            config.master_key.get_secret_value(),
            aad=AADS.LLM_API_KEY,
        )
        if image_model_api_key
        else None
    )

    wizard_id = request.cookies.get("wizard_id")
    assert wizard_id

    async with get_db_connection(start_transaction=True) as conn:
        await update_user_settings_draft_llm_configs(
            conn,
            wizard_id=wizard_id,
            image_model_provider=image_model_provider or None,
            image_model_base_url=image_model_base_url or None,
            image_model=image_model or None,
            image_model_api_key_enc=image_model_api_key_enc,
            text_model_provider=text_model_provider or None,
            text_model_base_url=text_model_base_url or None,
            text_model=text_model or None,
            text_model_api_key_enc=text_model_api_key_enc,
            image_processing_approach=image_processing_approach.value,
        )

        # Finalize
        await finalize_user_settings_from_draft(conn, wizard_id=wizard_id)

    jwt_token = create_jwt_token()
    if request.state.is_htmx:
        # HTMX expects a 200 with HX-Redirect
        resp = JSONResponse({})
        resp.headers["HX-Redirect"] = "/s"
    else:
        # For non-HTMX, force GET via 303 See Other
        resp = RedirectResponse(url="/s", status_code=status.HTTP_303_SEE_OTHER)

    resp.set_cookie(key="Authorization", value=f"Bearer {jwt_token}", httponly=True)
    # clear wizard cookie
    resp.delete_cookie("wizard_id")
    # After models, go to optional connect step
    if request.state.is_htmx:
        resp.headers["HX-Redirect"] = "/s/create-account/connect"
        return resp
    return RedirectResponse(
        "/s/create-account/connect", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/create-account/connect")
async def create_account_connect_get(request: Request) -> Response:
    page = create_connect_page()
    if request.state.is_htmx:
        return HTMLResponse(page)
    return HTMLResponse(
        create_base_page(
            content=page,
            user_settings=None,
            page_title="Create Account — Connect Source",
            include_sidebar=False,
        )
    )


@router.post("/create-account/connect/finish")
async def create_account_connect_finish(request: Request) -> Response:
    # Finish onboarding and go to dashboard
    if request.state.is_htmx:
        resp = JSONResponse({})
        resp.headers["HX-Redirect"] = "/s"
        return resp
    return RedirectResponse("/s", status_code=status.HTTP_303_SEE_OTHER)
