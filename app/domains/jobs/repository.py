from __future__ import annotations

# app/domains/jobs/repository.py: 保留历史任务审计事件的读写端口。

from typing import Protocol

from app.domains.jobs.models import JobEvent


class JobEventRepositoryProtocol(Protocol):
    """Job 审计事件读写合同。"""

    def append_event(self, job_id: str, event: JobEvent) -> None: ...
    def list_events(self, job_id: str) -> list[JobEvent]: ...
