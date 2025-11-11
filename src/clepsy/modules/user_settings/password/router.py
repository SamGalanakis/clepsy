import json

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import HTMLResponse

from clepsy.auth.auth import hash_password, verify_password
from clepsy.central_cache import invalidate_user_settings_cache
from clepsy.db.db import get_db_connection
from clepsy.db.queries import (
    select_user_auth,
    select_user_settings,
    update_user_password,
)
from clepsy.modules.user_settings.password.page import create_password_page


router = APIRouter()


def validate_password_form(
    current_password: str,
    new_password: str,
    confirm_password: str,
    user_current_password_hash: str,
):
    current_password_error = None
    new_password_error = None
    confirm_password_error = None
    if not current_password.strip():
        current_password_error = "Current password is required"
    else:
        if not verify_password(
            stored_hash=user_current_password_hash, password=current_password
        ):
            current_password_error = "Current password is incorrect"
    if not new_password.strip():
        new_password_error = "New password is required"
    elif len(new_password) < 8:
        new_password_error = "Password must be at least 8 characters long"
    if not confirm_password.strip():
        confirm_password_error = "Please confirm your new password"
    elif new_password != confirm_password:
        confirm_password_error = "Passwords do not match"
    return current_password_error, new_password_error, confirm_password_error


@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> HTMLResponse:
    try:
        async with get_db_connection() as conn:
            user_settings = await select_user_settings(conn)
            if user_settings is None:
                raise HTTPException(status_code=500, detail="User settings not found")

            auth_row = await select_user_auth(conn)
            if auth_row is None:
                raise HTTPException(
                    status_code=500, detail="Authentication not initialized"
                )

            current_password_error, new_password_error, confirm_password_error = (
                validate_password_form(
                    current_password,
                    new_password,
                    confirm_password,
                    auth_row["password_hash"],
                )
            )
            if any(
                [current_password_error, new_password_error, confirm_password_error]
            ):
                settings_page_content = await create_password_page(
                    user_settings=user_settings,
                    current_password_error=current_password_error,
                    new_password_error=new_password_error,
                    confirm_password_error=confirm_password_error,
                    new_password_value=new_password,
                    confirm_password_value=confirm_password,
                )
                return HTMLResponse(
                    content=settings_page_content, status_code=status.HTTP_200_OK
                )
            new_password_hash = hash_password(new_password)
            await update_user_password(conn, password_hash=new_password_hash)
        await invalidate_user_settings_cache()
        settings_page_content = await create_password_page(user_settings=user_settings)
        response = HTMLResponse(content=settings_page_content)
        response.headers["HX-Trigger"] = json.dumps(
            {
                "basecoat:toast": {
                    "config": {
                        "category": "success",
                        "title": "Password Changed",
                        "description": "Your password has been successfully updated.",
                    }
                }
            }
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error") from e
