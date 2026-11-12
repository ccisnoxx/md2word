"""翻译批次执行：对外只暴露门面 TranslationBatchExecution 与批次队列协议。

组件依赖方向（无环）：
planning ← integrity_binding ← artifacts ← generation ← installation；
failure → generation；provider_call → failure、artifacts、generation。
"""

from __future__ import annotations

from typing import Any, Callable

from app.core.config import Settings
from app.domains.document_jobs.execution_support import DocumentJobLifecycle
from app.domains.document_jobs.models import DocumentJobRecord, DocumentJobTranslationBatchRecord
from app.domains.document_jobs.repository import (
    DocumentJobRepositoryProtocol,
    DocumentJobTranslationBatchRepositoryProtocol,
)
from app.domains.document_jobs.translation_execution.artifacts import TranslationArtifactStore
from app.domains.document_jobs.translation_execution.deps import (
    DocumentTranslationBatchTaskQueueProtocol,
    TranslationExecutionDeps,
)
from app.domains.document_jobs.translation_execution.failure import TranslationFailureHandler
from app.domains.document_jobs.translation_execution.generation import TranslationGenerationCoordinator
from app.domains.document_jobs.translation_execution.installation import TranslationBatchInstaller
from app.domains.document_jobs.translation_execution.integrity_binding import TranslationIntegrityBinder
from app.domains.document_jobs.translation_execution.planning import TranslationPlanner
from app.domains.document_jobs.translation_execution.provider_call import TranslationBatchRunner
from app.domains.document_jobs.workflow import TranslationGenerationSummary
from app.domains.files import FileUploadService
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.resource_snapshots import JobResourceSnapshotService
from app.domains.translation.audit import TranslationAuditService
from app.domains.translation.document_ir_translator import DocumentIRTranslationService
from app.services.document_ir.models import DocumentIR

__all__ = ["DocumentTranslationBatchTaskQueueProtocol", "TranslationBatchExecution"]


class TranslationBatchExecution:
    """翻译批次执行门面：由 DocumentJobExecutionService 构造并持有。

    任务级状态推进与事件记录经注入的 DocumentJobLifecycle 完成；翻译收口后的续跑经注入的
    resume_job 回到宿主执行骨架。宿主、Worker 与用例只调用本类公开方法；组件属性
    （planner、runner、generation 等）仅供测试精确驱动单个环节。
    """

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: DocumentJobRepositoryProtocol,
        file_repository: DocumentFileRepositoryProtocol,
        file_service: FileUploadService,
        job_resource_snapshot_service: JobResourceSnapshotService | None,
        lifecycle: DocumentJobLifecycle,
        resume_job: Callable[..., DocumentJobRecord | None],
        translation_batch_repository: DocumentJobTranslationBatchRepositoryProtocol,
        document_ir_translation_service: DocumentIRTranslationService | None,
        translation_audit_service: TranslationAuditService | None,
        term_version_service: Any | None,
        translation_batch_task_queue: DocumentTranslationBatchTaskQueueProtocol | None,
    ) -> None:
        self.deps = TranslationExecutionDeps(
            settings=settings,
            job_repository=job_repository,
            file_repository=file_repository,
            file_service=file_service,
            job_resource_snapshot_service=job_resource_snapshot_service,
            lifecycle=lifecycle,
            resume_job=resume_job,
            translation_batch_repository=translation_batch_repository,
            document_ir_translation_service=document_ir_translation_service,
            translation_audit_service=translation_audit_service,
            term_version_service=term_version_service,
            translation_batch_task_queue=translation_batch_task_queue,
        )
        self.planner = TranslationPlanner(self.deps)
        self.binder = TranslationIntegrityBinder(self.deps, planner=self.planner)
        self.artifacts = TranslationArtifactStore(self.deps, planner=self.planner, binder=self.binder)
        self.generation = TranslationGenerationCoordinator(self.deps, planner=self.planner, artifacts=self.artifacts)
        self.installer = TranslationBatchInstaller(self.deps, planner=self.planner, generation=self.generation)
        self.failures = TranslationFailureHandler(self.deps, planner=self.planner, generation=self.generation)
        self.runner = TranslationBatchRunner(
            self.deps,
            planner=self.planner,
            binder=self.binder,
            artifacts=self.artifacts,
            generation=self.generation,
            failures=self.failures,
        )

    def set_translation_batch_task_queue(
        self,
        task_queue: DocumentTranslationBatchTaskQueueProtocol | None,
    ) -> None:
        """在 runtime 组装后注入 translation batch queue，避免循环构造依赖。"""

        self.deps.translation_batch_task_queue = task_queue

    def start_generation(
        self,
        job: DocumentJobRecord,
        source_document_ir: DocumentIR | None = None,
        *,
        trace_id: str | None,
    ) -> DocumentJobRecord:
        """安装本代根批次并投递可运行批次；未给出 source 时按任务权威指针读取并校验。"""

        if source_document_ir is None:
            _source_file, source_document_ir = self.planner.read_source(job, job.source_document_ir_file_id)
        return self.installer.install_and_enqueue(job, source_document_ir, trace_id=trace_id)

    def finalize_generation(
        self,
        job_id: str,
        *,
        generation: int,
        trace_id: str | None,
    ) -> DocumentJobRecord | None:
        """幂等收口指定代次；可重复调用，非当前代或已终态时原样返回。"""

        return self.generation.finalize(job_id, generation=generation, trace_id=trace_id)

    def summarize_generation(
        self,
        job: DocumentJobRecord,
        batches: list[DocumentJobTranslationBatchRecord] | None = None,
    ) -> TranslationGenerationSummary | None:
        """按当前 source/config 重算权威代次结论；API 投影与执行入口共用。"""

        return self.generation.summarize(job, batches)

    def execute_translation_batch(
        self, batch_id: str, *, trace_id: str | None = None,
    ) -> DocumentJobTranslationBatchRecord | None:
        """Worker 入口：执行单个 provider batch task。"""

        return self.runner.run(batch_id, trace_id=trace_id)
