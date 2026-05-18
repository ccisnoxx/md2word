from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.jobs import router as jobs_router
from app.api.v1.routers.mineru_callbacks import router as mineru_callbacks_router
from app.api.v1.routers.templates import router as templates_router


router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(mineru_callbacks_router)
router.include_router(templates_router)
