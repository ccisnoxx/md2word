# File: app/api/v1/router.py
# Purpose: Aggregate v1 API subrouters.

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routers.auth import router as auth_router
from app.domains.acceptance.router import router as acceptance_router
from app.domains.audit.router import router as audit_router
from app.domains.config_workbench.router import router as config_workbench_router
from app.domains.document_jobs.router import router as document_jobs_router
from app.domains.document_jobs.incidents_router import router as document_job_incidents_router
from app.domains.files.router import router as files_router
from app.api.v1.routers.health import router as health_router
from app.domains.jobs.mineru_callbacks_router import router as mineru_callbacks_router
from app.domains.ops.router import router as ops_router
from app.domains.saved_views.router import router as saved_views_router
from app.domains.term_rules.categories_router import router as term_rule_categories_router
from app.domains.term_rules.proposals_router import router as term_rule_proposals_router
from app.domains.term_rules.review_router import router as term_rule_reviews_router
from app.domains.term_rules.sets_router import router as term_rule_sets_router
from app.domains.term_rules.router import router as term_rules_router
from app.domains.terminology.router import router as terminology_releases_router
from app.domains.templates.router import router as templates_router
from app.domains.translation.proposals_router import router as translation_term_proposals_router
from app.domains.translation.sets_router import router as translation_term_sets_router
from app.domains.translation.router import router as translation_profiles_router
from app.domains.users.router import router as users_router


router = APIRouter(prefix="/api/v1")
router.include_router(acceptance_router)
router.include_router(auth_router)
router.include_router(audit_router)
router.include_router(config_workbench_router)
router.include_router(document_job_incidents_router)
router.include_router(document_jobs_router)
router.include_router(files_router)
router.include_router(health_router)
router.include_router(mineru_callbacks_router)
router.include_router(ops_router)
router.include_router(saved_views_router)
router.include_router(templates_router)
router.include_router(term_rule_categories_router)
router.include_router(term_rule_proposals_router)
router.include_router(term_rule_reviews_router)
router.include_router(term_rule_sets_router)
router.include_router(term_rules_router)
router.include_router(terminology_releases_router)
router.include_router(translation_term_proposals_router)
router.include_router(translation_term_sets_router)
router.include_router(translation_profiles_router)
router.include_router(users_router)
