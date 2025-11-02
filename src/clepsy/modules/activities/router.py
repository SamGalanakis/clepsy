from fastapi import APIRouter

from .add_router import router as activity_add_router
from .edit_router import router as activity_edit_router


router = APIRouter(prefix="/activities")
router.include_router(activity_edit_router)
router.include_router(activity_add_router)
