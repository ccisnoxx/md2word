from __future__ import annotations

# app/domains/jobs/router.py: 聚合 jobs domain 的 v1 子路由。

from fastapi import APIRouter

from app.domains.jobs.ingest_router import router as jobs_ingest_router
from app.domains.jobs.ops_router import router as jobs_ops_router
from app.domains.jobs.query_router import router as jobs_query_router

router = APIRouter(tags=["jobs"])
router.include_router(jobs_ingest_router, prefix="/jobs")
router.include_router(jobs_query_router, prefix="/jobs")
router.include_router(jobs_ops_router, prefix="/jobs")
