from __future__ import annotations

# app/domains/document_jobs/workflow.py: 收口 document_jobs 状态组和动作前置规则。

from app.domains.document_jobs.models import DocumentJobStatus


ACTIVE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"pending", "queued", "running"}
TERMINAL_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = {"succeeded", "failed", "canceled"}
ARCHIVABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = set(TERMINAL_DOCUMENT_JOB_STATUSES)
CANCELABLE_DOCUMENT_JOB_STATUSES: set[DocumentJobStatus] = set(ACTIVE_DOCUMENT_JOB_STATUSES)
DOCUMENT_JOB_STATUS_GROUPS: dict[str, set[DocumentJobStatus]] = {
    "active": set(ACTIVE_DOCUMENT_JOB_STATUSES),
}


def is_active_document_job_status(status: str) -> bool:
    return status in ACTIVE_DOCUMENT_JOB_STATUSES


def is_terminal_document_job_status(status: str) -> bool:
    return status in TERMINAL_DOCUMENT_JOB_STATUSES

