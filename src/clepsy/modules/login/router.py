from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger

from clepsy.auth.auth import hash_password, maybe_rehash, verify_password
from clepsy.auth.auth_middleware import create_jwt_token
from clepsy.db.db import get_db_connection
from clepsy.db.queries import select_user_auth, update_user_password
from clepsy.frontend.components import create_base_page
from clepsy.modules.login.page import (
    create_login_page,
)


router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    is_authenticated = request.state.authenticated

    if is_authenticated:
        logger.info("User is already authenticated - redirecting to settings page")
        response = RedirectResponse(url="/s/user-settings", status_code=303)
        return response

    is_htmx = request.state.is_htmx
    content = create_login_page()

    if is_htmx:
        return HTMLResponse(content)

    return HTMLResponse(
        create_base_page(
            content=content,
            user_settings=None,
            page_title="Login - Auto Time Tracker",
            include_sidebar=False,  # No sidebar for login page
        )
    )


@router.post("/login")
async def login_user(password: str = Form(...)) -> Response:  # Use base Response type
    try:
        logger.info("Login attempt")

        async with get_db_connection(include_uuid_func=False) as conn:
            # Always verify against user_auth
            auth_row = await select_user_auth(conn)
            if not auth_row:
                logger.error("Auth not initialized (user_auth empty)")
                raise RuntimeError("Authentication not initialized")
            password_to_check_hash = auth_row["password_hash"]

            # Validate password
            if not verify_password(
                stored_hash=password_to_check_hash, password=password
            ):
                logger.warning("Invalid login attempt")
                # Return login form with error message
                error_form = create_login_page(error_message="Invalid password")
                return HTMLResponse(content=error_form)  # Removed headers

            # Login successful
            logger.info("Successful login!")

        if maybe_rehash(password_to_check_hash):
            logger.info("Rehashing password with updated parameters")
            new_hash = hash_password(password)
            async with get_db_connection(include_uuid_func=False) as conn:
                await update_user_password(conn=conn, password_hash=new_hash)

        # Create JWT token
        token = create_jwt_token()

        # Create success response with redirect via HX-Redirect
        response = HTMLResponse(
            content="<div class='text-green-500 p-4'>Login successful! Redirecting...</div>"
        )
        # Set the auth cookie
        response.set_cookie(
            key="Authorization",
            value=f"Bearer {token}",
            httponly=True,
            samesite="lax",
            secure=False,
        )  # Adjust secure=True for HTTPS
        # Trigger redirect
        response.headers["HX-Redirect"] = "/s/"

        return response
    except HTTPException:
        raise
    except Exception:
        logger.error("Login error", exc_info=True)
        error_form = create_login_page(
            error_message="An unexpected error occurred. Please try again."
        )
        return HTMLResponse(content=error_form)


@router.get("/logout")
async def logout_user(_: Request):
    logger.info("User is logging out.")
    response = RedirectResponse(url="/s/login", status_code=303)
    response.delete_cookie(key="Authorization", samesite="lax")
    return response
