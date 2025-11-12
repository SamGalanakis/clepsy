import base64
import datetime
import hashlib
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
import jwt
from loguru import logger

from clepsy.central_cache import (
    get_device_source_by_token_cached,
    get_user_settings_cached,
)
from clepsy.config import config
from clepsy.entities import SourceStatus


def create_jwt_token(user_id: str | None = None) -> str:
    expiry_seconds = time.time() + datetime.timedelta(days=1).total_seconds()
    payload = {"user_id": user_id, "expires": expiry_seconds}
    token = jwt.encode(
        payload, config.jwt_secret.get_secret_value(), algorithm=config.jwt_algorithm
    )

    return token


def decode_jwt_token(token: str) -> dict:
    try:
        decoded_token = jwt.decode(
            token,
            config.jwt_secret.get_secret_value(),
            algorithms=[config.jwt_algorithm],
        )
    except Exception as e:
        raise e
    expired = decoded_token["expires"] < time.time()

    if expired:
        raise HTTPException(status_code=401, detail="Token expired")
    else:
        return decoded_token


class JWTMiddleware:
    def __init__(self, path_prefixes: list[str], path_prefixes_to_exclude: list[str]):
        self.path_prefixes = path_prefixes
        self.path_prefixes_to_exclude = path_prefixes_to_exclude
        # Allow these while authenticated but before user settings exist (onboarding)
        self.allowed_when_uninitialized_prefixes: list[str] = [
            "/s/create-account",
            "/s/user-settings/test-model/",
        ]

    def to_authenticate(self, path: str) -> bool:
        in_path_prefixes = any(
            [path.startswith(prefix) for prefix in self.path_prefixes]
        )
        if not in_path_prefixes:
            return False
        in_path_prefixes_to_exclude = any(
            [path.startswith(prefix) for prefix in self.path_prefixes_to_exclude]
        )

        if in_path_prefixes_to_exclude:
            return False

        return True

    async def redirect_to_registration(self, is_htmx: bool):
        if is_htmx:
            # HTMX expects a 200 with HX-Redirect header
            return JSONResponse(
                content="",
                status_code=200,
                headers={"HX-Redirect": "/s/create-account"},
            )
        else:
            return RedirectResponse(url="/s/create-account")

    async def redirect_to_login(self, is_htmx: bool):
        if is_htmx:
            # HTMX expects a 200 with HX-Redirect header
            return JSONResponse(
                content="", status_code=200, headers={"HX-Redirect": "/s/login"}
            )
        else:
            return RedirectResponse(url="/s/login")

    async def check_authentication(self, request: Request, to_authenticate: bool):
        """Validate the Authorization cookie if present.

        Returns a tuple of (authenticated, decoded_token | None, reason | None)
        where reason is one of: "no_token", "invalid_token".
        """
        auth_token = request.cookies.get("Authorization")
        if auth_token is None:
            if to_authenticate:
                logger.debug("No auth token cookie present")
            return False, None, "no_token"

        try:
            jwt_token = auth_token.split(" ")[1]
            decoded_token = decode_jwt_token(jwt_token)
            request.state.jwt_payload = decoded_token
            request.state.authenticated = True

            return True, decoded_token, None
        except Exception:
            if to_authenticate:
                logger.exception("Invalid jwt token")
            return False, None, "invalid_token"

    async def __call__(self, request: Request, call_next):
        # do something with the request object
        is_htmx = "HX-Request" in request.headers
        to_authenticate = self.to_authenticate(request.url.path)
        path = request.url.path
        authenticated, decoded_token, auth_reason = await self.check_authentication(
            request, to_authenticate
        )

        request.state.authenticated = authenticated
        request.state.is_htmx = is_htmx
        if not to_authenticate:
            return await call_next(request)

        # Fetch user settings via TTL cache to avoid hitting DB on every request
        user_settings = await get_user_settings_cached()

        request.state.user_settings = user_settings
        if authenticated and user_settings:
            request.state.decoded_token = decoded_token
            response = await call_next(request)
        elif authenticated and not user_settings:
            logger.warning("User is authenticated but no user settings found")
            logger.info(
                "Authenticated user missing settings; path={}. Routing based on onboarding allowances.",
                path,
            )
            # Allow specific paths while onboarding
            allowed = any(
                path.startswith(prefix)
                for prefix in self.allowed_when_uninitialized_prefixes
            )
            if allowed:
                logger.info(
                    "Allowing access during initialization to path={} (allowed prefix)",
                    path,
                )
                response = await call_next(request)
            else:
                # Redirect authenticated user without settings to the wizard
                logger.info(
                    "Redirecting authenticated-but-uninitialized user to /s/create-account from path={}",
                    path,
                )
                response = await self.redirect_to_registration(is_htmx)

        else:
            if to_authenticate:
                # Only log for paths we protect to avoid noise on assets etc.
                logger.info(
                    "Unauthenticated request to protected path={} (reason={}); redirecting to /s/login",
                    path,
                    auth_reason,
                )
            response = await self.redirect_to_login(is_htmx)

        return response


class DeviceTokenMiddleware:
    def __init__(
        self,
        path_prefixes: list[str],
        path_prefixes_to_exclude: list[str],
    ):
        self.path_prefixes = path_prefixes
        self.path_prefixes_to_exclude = path_prefixes_to_exclude

    def to_authenticate(self, path: str) -> bool:
        in_path_prefixes = any(path.startswith(prefix) for prefix in self.path_prefixes)
        if not in_path_prefixes:
            return False
        in_exclude = any(
            path.startswith(prefix) for prefix in self.path_prefixes_to_exclude
        )
        return not in_exclude

    @staticmethod
    def _b64_to_bytes(token_b64: str) -> bytes:
        # urlsafe base64 without padding; add padding back if needed
        padding = "=" * (-len(token_b64) % 4)
        return base64.urlsafe_b64decode(token_b64 + padding)

    async def __call__(self, request: Request, call_next):
        if not self.to_authenticate(request.url.path):
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=403, detail="Bearer token required")

        token = auth.split(" ", 1)[1].strip()
        try:
            token_bytes = self._b64_to_bytes(token)
        except Exception as e:
            logger.warning(
                f"Source sent malformed bearer token to {request.url.path}: {e}"
            )
            raise HTTPException(
                status_code=403, detail="Invalid bearer token format"
            ) from e

        token_hash = hashlib.sha256(token_bytes).hexdigest()

        # Look up source by token hash and ensure it's active (cached to reduce DB load)

        source = await get_device_source_by_token_cached(token_hash)

        if source is None:
            logger.warning(
                f"Source attempted to connect with invalid token to {request.url.path}. "
                "This usually means the source needs to be re-paired."
            )
            raise HTTPException(status_code=403, detail="Invalid token")
        if getattr(source, "status", None) != SourceStatus.ACTIVE:
            logger.warning(f"Source {source.id} attempted to connect but is disabled")
            raise HTTPException(status_code=403, detail="Source disabled")

        # Attach to request for handlers to use
        request.state.device_source = source

        return await call_next(request)
