from __future__ import annotations

# app/api/v1/router.py: 汇总 v1 API 子路由。

from fastapi import APIRouter

from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.document_jobs import router as document_jobs_router
from app.api.v1.routers.files import router as files_router
from app.api.v1.routers.health import router as health_router
from app.api.v1.routers.jobs import router as jobs_router
from app.api.v1.routers.mineru_callbacks import router as mineru_callbacks_router
from app.api.v1.routers.term_rule_categories import router as term_rule_categories_router
from app.api.v1.routers.term_rule_sets import router as term_rule_sets_router
from app.api.v1.routers.term_rules import router as term_rules_router
from app.api.v1.routers.templates import router as templates_router
from app.api.v1.routers.translation_profiles import router as translation_profiles_router


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(document_jobs_router)
router.include_router(files_router)
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(mineru_callbacks_router)
router.include_router(templates_router)
router.include_router(term_rule_categories_router)
router.include_router(term_rule_sets_router)
router.include_router(term_rules_router)
router.include_router(translation_profiles_router)
