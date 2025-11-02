from fastapi import Request

from clepsy.entities import UserSettings


async def get_user_settings(request: Request) -> UserSettings:
    assert isinstance(
        request.state.user_settings, UserSettings
    ), "User settings not found in request state"
    return request.state.user_settings


async def get_user_settings_optional(request: Request) -> UserSettings | None:
    us = getattr(request.state, "user_settings", None)
    return us if isinstance(us, UserSettings) else None
