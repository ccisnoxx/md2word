from __future__ import annotations

# app/api/v1/router.py: 汇总 v1 API 子路由。

from fastapi import APIRouter

from app.api.v1.routers.auth import router as auth_router
from app.domains.document_jobs.router import router as document_jobs_router
from app.domains.files.router import router as files_router
from app.api.v1.routers.health import router as health_router
from app.domains.jobs.router import router as jobs_router
from app.domains.jobs.mineru_callbacks_router import router as mineru_callbacks_router
from app.domains.term_rules.categories_router import router as term_rule_categories_router
from app.domains.term_rules.proposals_router import router as term_rule_proposals_router
from app.domains.term_rules.sets_router import router as term_rule_sets_router
from app.domains.term_rules.router import router as term_rules_router
from app.domains.templates.router import router as templates_router
from app.domains.translation.proposals_router import router as translation_term_proposals_router
from app.domains.translation.sets_router import router as translation_term_sets_router
from app.domains.translation.router import router as translation_profiles_router


router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(document_jobs_router)
router.include_router(files_router)
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(mineru_callbacks_router)
router.include_router(templates_router)
router.include_router(term_rule_categories_router)
router.include_router(term_rule_proposals_router)
router.include_router(term_rule_sets_router)
router.include_router(term_rules_router)
router.include_router(translation_term_proposals_router)
router.include_router(translation_term_sets_router)
router.include_router(translation_profiles_router)
