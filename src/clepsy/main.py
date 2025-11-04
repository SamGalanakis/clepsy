from contextlib import asynccontextmanager
import mimetypes

from fastapi import APIRouter, FastAPI, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from clepsy import bootstrap
from clepsy.auth.auth_middleware import DeviceTokenMiddleware, JWTMiddleware
from clepsy.modules.account_creation.router import router as account_creation_router
from clepsy.modules.activities.router import router as activity_router
from clepsy.modules.aggregator.router import router as aggregator_router
from clepsy.modules.goals.router import router as goals_router
from clepsy.modules.home.router import router as home_router
from clepsy.modules.insights.router import router as insights_router
from clepsy.modules.login.router import router as login_router
from clepsy.modules.sources.router import router as sources_router
from clepsy.modules.tags.router import router as tags_router
from clepsy.modules.user_settings.router import router as user_settings_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # ---- startup -------------------------------------------------
    logger.info("Starting Clepsy backend...")
    logger.info("Initializing bootstrap...")
    await bootstrap.init()
    # In RQ mode, we don't start in-process workers or the in-memory event bus.
    # APScheduler fully removed; RQ Cron handles scheduling
    yield

    # No in-process workers to stop when using RQ


app = FastAPI(title="Clepsy backend", lifespan=lifespan)

mimetypes.add_type("application/javascript", ".js")

app.mount("/static", StaticFiles(directory="static"), name="static")

jwt_middleware = JWTMiddleware(
    path_prefixes=["/s/"],
    path_prefixes_to_exclude=[
        "/s/login",
        "/sources/",
    ],
)

app.add_middleware(BaseHTTPMiddleware, dispatch=jwt_middleware)


device_token_middleware = DeviceTokenMiddleware(
    path_prefixes=["/sources"],
    path_prefixes_to_exclude=["/sources/pair"],
)

app.add_middleware(BaseHTTPMiddleware, dispatch=device_token_middleware)

website_router = APIRouter(prefix="/s")


website_router.include_router(home_router)
website_router.include_router(login_router)
website_router.include_router(user_settings_router)
website_router.include_router(activity_router)
website_router.include_router(goals_router)
website_router.include_router(account_creation_router)
website_router.include_router(insights_router)
website_router.include_router(tags_router)


sources_router.include_router(aggregator_router)


app.include_router(website_router)
app.include_router(sources_router)


@app.get("/")
async def redirect_to_website():
    """Redirect root URL to the website interface"""
    return RedirectResponse(url="/s/")


@app.get("/healthz")
async def healthz():
    """
    A tiny, dedicated endpoint that just returns 200 OK and nothing else.
    """
    return Response(status_code=200)


if __name__ == "__main__":
    uvicorn.run(
        "clepsy.main:app",
        host="0.0.0.0",
        port=8000,
        log_config=None,
        log_level=None,
        reload=False,
    )
