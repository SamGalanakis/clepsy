from datetime import datetime, timezone as dt_timezone
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from htpy import Element, div, h2, input as htpy_input, p, span

from clepsy.auth.auth import hash_password
from clepsy.central_cache import invalidate_device_source_cache
from clepsy.config import config
from clepsy.db.db import get_db_connection
from clepsy.db.deps import get_user_settings
from clepsy.db.queries import (
    deactivate_active_enrollment_codes,
    delete_source,
    insert_source_enrollment_code,
    select_sources,
    toggle_source_status,
)
from clepsy.entities import SourceStatus, UserSettings
from clepsy.frontend.components import create_button
from clepsy.modules.user_settings.sources.page import (
    create_sources_table,
    create_status_toggle,
)


router = APIRouter()


@router.get("/user-settings/sources/table")
async def sources_table_partial(
    user_settings: UserSettings = Depends(get_user_settings),
) -> HTMLResponse:
    async with get_db_connection(include_uuid_func=False) as conn:
        sources = await select_sources(conn)
    table_html = create_sources_table(sources, user_timezone=user_settings.timezone)
    return HTMLResponse(content=table_html)


@router.post("/toggle-source-status/{source_id}")
async def toggle_source_status_endpoint(source_id: int) -> HTMLResponse:
    async with get_db_connection() as conn:
        new_status = await toggle_source_status(conn, source_id=source_id)
    is_active = new_status == SourceStatus.ACTIVE
    toggle = create_status_toggle(is_active=is_active, source_id=source_id)
    response = HTMLResponse(content=toggle)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "basecoat:toast": {
                "config": {
                    "category": "success",
                    "title": (
                        "Source has been activated."
                        if is_active
                        else "Source has been deactivated."
                    ),
                    "description": None,
                }
            }
        }
    )
    return response


async def render_add_source_modal_content(*, code: str, minutes_valid: int) -> Element:
    header = div(class_="flex justify-between items-center p-4 border-b")[
        h2(class_="text-lg font-semibold text-on-surface")["Add Source",],
        create_button(
            text=None,
            variant="secondary",
            icon="x",
            attrs={
                "type": "button",
                "onclick": "document.getElementById('add-source-modal').close();",
            },
        ),
    ]
    body = div(
        class_="flex flex-col gap-4 p-4",
        x_data=(
            "{ copied: false, async copy(){ const inp=$refs.code; inp.select(); "
            "try{ await navigator.clipboard.writeText(inp.value); }"
            "catch(e){ document.execCommand('copy'); }"
            "this.copied=true; setTimeout(()=>this.copied=false, 1200); } }"
        ),
    )[
        p(class_="text-sm text-muted-foreground")[
            f"Enter this code in the desktop app to link it. Code is valid for {minutes_valid} minutes."
        ],
        div(class_="w-full flex flex-col items-center gap-2")[
            div(class_="relative w-full max-w-xs md:max-w-sm")[
                htpy_input(
                    id="enrollment-code",
                    type="text",
                    value=code,
                    readonly=True,
                    x_ref="code",
                    # Clicking anywhere on the input copies the code
                    **{"@click": "copy()"},
                    class_=(
                        "input cursor-pointer text-center font-mono tracking-widest "
                        "text-2xl md:text-3xl py-3 pl-4 pr-16 w-full"
                    ),
                ),
                create_button(
                    text=None,
                    icon="copy",
                    variant="secondary",
                    size="sm",
                    extra_classes="absolute right-2 top-1/2 -translate-y-1/2",
                    attrs={
                        "type": "button",
                        "@click": "copy()",
                        "tabindex": "-1",
                        "aria-label": "Copy code",
                    },
                ),
            ],
            span(
                class_="text-green-600 dark:text-green-400 text-sm",
                x_show="copied",
                x_cloak=True,
            )["Copied!"],
        ],
    ]

    return div(class_="bg-surface rounded-lg shadow-lg")[header, body]


@router.get("/add-source-modal")
async def get_add_source_modal() -> HTMLResponse:
    try:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        code_hash = hash_password(code)
        expires_at = datetime.now(dt_timezone.utc) + config.source_enrollment_code_ttl
        async with get_db_connection() as conn:
            await deactivate_active_enrollment_codes(conn)
            await insert_source_enrollment_code(
                conn, code_hash=code_hash, expires_at=expires_at
            )
        minutes_valid = int(config.source_enrollment_code_ttl.total_seconds() // 60)
        content = await render_add_source_modal_content(
            code=code, minutes_valid=minutes_valid
        )
        return HTMLResponse(content=content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/sources/{source_id}")
async def delete_source_endpoint(
    source_id: int, user_settings: UserSettings = Depends(get_user_settings)
) -> HTMLResponse:
    try:
        async with get_db_connection() as conn:
            deleted_source = await delete_source(conn, source_id)

            # Invalidate cache for this source
            if deleted_source:
                await invalidate_device_source_cache(deleted_source.token_hash)

            sources = await select_sources(conn)
        tz = user_settings.timezone if user_settings else "UTC"
        table_html = create_sources_table(sources, user_timezone=tz)
        category = "success" if deleted_source else "warning"
        title = "Source Deleted" if deleted_source else "Nothing Deleted"
        desc = (
            "The source was removed."
            if deleted_source
            else "No source found with that ID."
        )
        response = HTMLResponse(content=table_html)
        response.headers["HX-Trigger"] = json.dumps(
            {
                "basecoat:toast": {
                    "config": {
                        "category": category,
                        "title": title,
                        "description": desc,
                    }
                }
            }
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
