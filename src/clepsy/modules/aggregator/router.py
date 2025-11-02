from fastapi import APIRouter

from .desktop_source.router import router as desktop_router
from .mobile_source.router import router as mobile_router


router = APIRouter(prefix="/aggregator")

router.include_router(desktop_router)
router.include_router(mobile_router)
