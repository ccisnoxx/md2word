"""翻译批次执行组件共享的依赖集合。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.core.config import Settings
from app.domains.document_jobs.execution_support import DocumentJobLifecycle
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.repository import (
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.files import FileUploadService
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService


class DocumentTranslationBatchTaskQueueProtocol(Protocol):
    """translation provider batch task 投递端口；批次记录负责幂等和 fan-in。"""

    def enqueue(self, batch_id: str, *, trace_id: str | None, run_inline: bool = True) -> str | None:
        """投递一个按 batch_id 执行的后台任务，返回底层队列任务 ID。"""


@dataclass
class TranslationExecutionDeps:
    """七个翻译执行组件共用的唯一依赖持有者。

    组件只经 ``self.deps`` 读取依赖，因此运行时注入队列或测试替换某个依赖时，
    只需改这一处即可对全部组件生效；不要在组件上另存依赖副本。
    """

    settings: Settings
    job_repository: DocumentJobRepositoryProtocol
    file_repository: DocumentFileRepositoryProtocol
    file_service: FileUploadService
    job_resource_snapshot_service: JobResourceSnapshotService | None
    lifecycle: DocumentJobLifecycle
    resume_job: Callable[..., DocumentJobRecord | None]
    translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol
    document_ir_translation_service: DocumentIRTranslationService | None
    translation_audit_service: TranslationAuditService | None
    term_version_service: Any | None
    translation_batch_task_queue: DocumentTranslationBatchTaskQueueProtocol | None
