"""Role-derived permissions shared by auth responses and backend guards."""

from __future__ import annotations

# File: app/services/auth/permissions.py
# Purpose: Keep role permission lists in one place for UI claims and API guards.

from app.services.auth.models import InternalUserRole


OPERATOR_PERMISSIONS: tuple[str, ...] = (
    "document_jobs:read",
    "document_jobs:create",
    "document_jobs:download",
    "document_jobs:retry",
    "document_jobs:cancel",
    "document_jobs:archive",
    "document_jobs:clone",
    "translation_qa:read",
    "translation_qa:write",
    "term_proposals:read",
    "term_proposals:create",
)

ADMIN_EXTRA_PERMISSIONS: tuple[str, ...] = (
    "settings:read",
    "settings:write",
    "system:read",
    "ops:read",
    "ops:write",
    "audit:read",
    "users:manage",
    "files:retention",
    "term_proposals:review",
)


def permissions_for_role(role: InternalUserRole) -> list[str]:
    """Return the stable permission claims for one internal user role."""

    permissions = list(OPERATOR_PERMISSIONS)
    if role == "admin":
        permissions.extend(ADMIN_EXTRA_PERMISSIONS)
    return permissions
