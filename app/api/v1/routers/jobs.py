from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers.jobs_ingest import router as jobs_ingest_router
from app.api.v1.routers.jobs_ops import router as jobs_ops_router
from app.api.v1.routers.jobs_query import router as jobs_query_router

router = APIRouter(tags=["jobs"])
router.include_router(jobs_ingest_router, prefix="/jobs")
router.include_router(jobs_query_router, prefix="/jobs")
router.include_router(jobs_ops_router, prefix="/jobs")
