from __future__ import annotations

# app/core/job_workflow.py: 集中定义 jobs workflow 规则、结构化迁移结果和领域级拒绝原因。

from dataclasses import dataclass, field
from typing import Any

from app.core.job_models import (
    ConversionOptions,
    JobExecutionStatus,
    JobLifecycleStatus,
    JobRecord,
    build_source_pdf_context_patch,
    project_job_status,
)


class JobWorkflowViolation(ValueError):
    """表示 job 当前状态或 variant 不允许执行某个 workflow 动作。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class WorkflowEventIntent:
    """描述一次领域语义事件，由应用层映射成持久化 JobEvent。"""

    kind: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowTransition:
    """描述一次合法 workflow 动作应产生的 job patch 和事件意图。"""

    next_lifecycle_status: JobLifecycleStatus | None = None
    next_execution_status: JobExecutionStatus | None = None
    context_updates: dict[str, Any] = field(default_factory=dict)
    event_intents: tuple[WorkflowEventIntent, ...] = ()

    def resolved_lifecycle_status(self, job: JobRecord) -> JobLifecycleStatus:
        """返回迁移后的生命周期状态。"""

        return self.next_lifecycle_status or job.resolved_lifecycle_status()

    def resolved_execution_status(self, job: JobRecord) -> JobExecutionStatus:
        """返回迁移后的执行状态。"""

        return self.next_execution_status or job.resolved_execution_status()

    def resolved_status(self, job: JobRecord) -> str:
        """返回迁移后的对外兼容 status。"""

        return project_job_status(
            self.resolved_lifecycle_status(job),
            self.resolved_execution_status(job),
        )

    def as_job_update_patch(self, job: JobRecord) -> dict[str, Any]:
        """返回可直接传给 repository.update_job() 的 patch。"""

        patch = dict(self.context_updates)
        patch["lifecycle_status"] = self.resolved_lifecycle_status(job)
        patch["execution_status"] = self.resolved_execution_status(job)
        patch["status"] = self.resolved_status(job)
        return patch


def build_job_created_intent(
    *,
    source_kind: str,
    source_filename: str,
    options: ConversionOptions,
) -> WorkflowEventIntent:
    """返回 job 创建成功后的统一领域事件意图。"""

    details = {
        "source_filename": source_filename,
        "translation_mode": options.translation_mode,
        "document_language": options.document_language,
    }
    if source_kind == "source_pdf":
        details["source_kind"] = "source_pdf"
    return WorkflowEventIntent(kind="job_created", details=details)


def build_mineru_callback_received_intent(payload: dict[str, Any]) -> WorkflowEventIntent:
    """返回收到可信 callback 后的统一领域事件意图。"""

    return WorkflowEventIntent(
        kind="mineru_callback_received",
        details={
            "batch_id": payload.get("batch_id"),
            "data_id": payload.get("data_id"),
            "state": payload.get("state"),
        },
    )


def build_translation_started_intent(*, translation_model: str) -> WorkflowEventIntent:
    """返回翻译开始时的统一领域事件意图。"""

    return WorkflowEventIntent(
        kind="translation_started",
        details={"translation_model": translation_model},
    )


def build_translation_completed_intent(
    *,
    translation_model: str,
    translation_request_recorded: bool,
) -> WorkflowEventIntent:
    """返回翻译完成时的统一领域事件意图。"""

    return WorkflowEventIntent(
        kind="translation_completed",
        details={
            "translation_model": translation_model,
            "translation_request_recorded": translation_request_recorded,
        },
    )


def build_parsed_result_conversion_started_intent() -> WorkflowEventIntent:
    """返回 parsed 结果后处理开始时的统一领域事件意图。"""

    return WorkflowEventIntent(kind="parsed_result_conversion_started")


def build_parsed_result_package_recovered_intent(*, source_url: str) -> WorkflowEventIntent:
    """返回 parsed 结果 zip 已恢复为本地 artifact 的事件意图。"""

    return WorkflowEventIntent(
        kind="parsed_result_package_recovered",
        details={"source_url": source_url},
    )


def build_retry_transition(job: JobRecord) -> WorkflowTransition:
    """返回 retry 动作的 job patch，保持当前 API 与持久化兼容。"""

    current_status = job.projected_status()
    if current_status not in {"failed", "canceled"}:
        raise JobWorkflowViolation(f"当前状态 `{current_status}` 不允许 retry。")

    context_updates: dict[str, Any] = {
        "progress": 0,
        "error_code": None,
        "error_message": None,
        "result_ready": False,
        "started_at": None,
        "completed_at": None,
    }
    if job.source_kind == "source_pdf":
        context_updates.update(
            build_source_pdf_context_patch(
                job,
                batch_id=None,
                data_id=None,
                callback_seed=None,
                upstream_status=None,
            )
        )

    return WorkflowTransition(
        next_lifecycle_status="uploaded",
        next_execution_status="idle",
        context_updates=context_updates,
        event_intents=(WorkflowEventIntent(kind="job_retry_requested"),),
    )


def build_stage_enqueue_transition(job: JobRecord, *, stage: str) -> WorkflowTransition:
    """返回 stage 入队后的统一 job patch。"""

    if stage == "submit_to_mineru" and job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许进入 MinerU 提交流程")
    if stage == "convert_parsed_result":
        if job.source_kind != "source_pdf":
            raise JobWorkflowViolation("只有 source_pdf 任务允许进入 parsed 结果后处理流程")
        if job.resolved_lifecycle_status() != "parsed" or job.resolved_execution_status() != "idle":
            raise JobWorkflowViolation(f"当前状态 `{job.projected_status()}` 不允许进入 parsed 结果后处理流程")
        return WorkflowTransition(
            next_execution_status="queued",
            context_updates={"progress": 65},
            event_intents=(WorkflowEventIntent(kind="stage_enqueued", details={"stage": stage}),),
        )

    return WorkflowTransition(
        next_execution_status="queued",
        context_updates={"progress": 10},
        event_intents=(WorkflowEventIntent(kind="stage_enqueued", details={"stage": stage}),),
    )


def build_conversion_started_transition(job: JobRecord) -> WorkflowTransition:
    """返回 convert_package 开始执行时的统一 job patch。"""

    return WorkflowTransition(
        next_execution_status="converting",
        context_updates={
            "progress": 50,
            "error_code": None,
            "error_message": None,
        },
        event_intents=(WorkflowEventIntent(kind="conversion_started"),),
    )


def build_parsed_result_conversion_started_transition(job: JobRecord) -> WorkflowTransition:
    """返回 parsed 结果后处理 stage 开始执行时的统一 job patch。"""

    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许执行 parsed 结果后处理")
    if job.resolved_lifecycle_status() != "parsed":
        raise JobWorkflowViolation(f"当前状态 `{job.projected_status()}` 不允许执行 parsed 结果后处理")

    return WorkflowTransition(
        next_execution_status="converting",
        context_updates={
            "progress": 80,
            "error_code": None,
            "error_message": None,
        },
        event_intents=(build_parsed_result_conversion_started_intent(),),
    )


def build_parsed_result_conversion_failed_transition(
    job: JobRecord,
    *,
    error_code: str,
    error_message: str,
) -> WorkflowTransition:
    """返回 parsed 结果后处理失败时的统一 job patch。"""

    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许执行 parsed 结果后处理")

    return WorkflowTransition(
        next_lifecycle_status="failed",
        next_execution_status="idle",
        context_updates={
            "progress": 100,
            "error_code": error_code,
            "error_message": error_message,
        },
        event_intents=(
            WorkflowEventIntent(
                kind="job_failed",
                details={"error_code": error_code, "error_message": error_message},
            ),
        ),
    )


def build_conversion_failed_transition(
    job: JobRecord,
    *,
    error_code: str,
    error_message: str,
) -> WorkflowTransition:
    """返回 convert_package 失败时的统一 job patch 和事件意图。"""

    event_intents: list[WorkflowEventIntent] = []
    if job.translation_mode == "en2zh" and error_code.startswith("translation_"):
        event_intents.append(
            WorkflowEventIntent(
                kind="translation_failed",
                details={"error_code": error_code, "error_message": error_message},
            )
        )
    event_intents.append(
        WorkflowEventIntent(
            kind="job_failed",
            details={"error_code": error_code, "error_message": error_message},
        )
    )
    return WorkflowTransition(
        next_lifecycle_status="failed",
        next_execution_status="idle",
        context_updates={
            "progress": 100,
            "error_code": error_code,
            "error_message": error_message,
        },
        event_intents=tuple(event_intents),
    )


def build_conversion_completed_transition(
    job: JobRecord,
    *,
    document_language: str,
) -> WorkflowTransition:
    """返回 convert_package 成功完成时的统一 job patch。"""

    return WorkflowTransition(
        next_lifecycle_status="completed",
        next_execution_status="idle",
        context_updates={
            "progress": 100,
            "result_ready": True,
            "resolved_document_language": document_language,
        },
        event_intents=(WorkflowEventIntent(kind="job_completed"),),
    )


def build_mineru_submission_started_transition(job: JobRecord) -> WorkflowTransition:
    """返回 submit_to_mineru 开始执行时的统一 job patch。"""

    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许提交 MinerU")

    return WorkflowTransition(
        next_execution_status="submitting",
        context_updates={
            "progress": 15,
            "error_code": None,
            "error_message": None,
        },
        event_intents=(WorkflowEventIntent(kind="mineru_submit_started"),),
    )


def build_mineru_submission_failed_transition(
    job: JobRecord,
    *,
    error_message: str,
) -> WorkflowTransition:
    """返回 submit_to_mineru 失败时的统一 job patch 和事件意图。"""

    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许提交 MinerU")

    return WorkflowTransition(
        next_lifecycle_status="failed",
        next_execution_status="idle",
        context_updates={
            "progress": 100,
            "error_code": "mineru_submit_failed",
            "error_message": error_message,
        },
        event_intents=(
            WorkflowEventIntent(
                kind="mineru_submit_failed",
                details={"error_code": "mineru_submit_failed", "error_message": error_message},
            ),
            WorkflowEventIntent(
                kind="job_failed",
                details={"error_code": "mineru_submit_failed", "error_message": error_message},
            ),
        ),
    )


def build_mineru_submission_succeeded_transition(
    job: JobRecord,
    *,
    batch_id: str,
    data_id: str,
    callback_seed: str | None,
) -> WorkflowTransition:
    """返回 submit_to_mineru 成功时的统一 job patch。"""

    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许提交 MinerU")

    return WorkflowTransition(
        next_execution_status="parsing",
        context_updates={
            "progress": 25,
            **build_source_pdf_context_patch(
                job,
                batch_id=batch_id,
                data_id=data_id,
                callback_seed=callback_seed,
                upstream_status="submitted",
            ),
        },
        event_intents=(
            WorkflowEventIntent(
                kind="mineru_submit_succeeded",
                details={"batch_id": batch_id, "data_id": data_id},
            ),
        ),
    )


def build_cancel_transition(job: JobRecord) -> WorkflowTransition:
    """返回 cancel 动作的 job patch。"""

    current_status = job.projected_status()
    if current_status in {"completed", "failed", "canceled"}:
        raise JobWorkflowViolation(f"当前状态 `{current_status}` 不允许 cancel。")
    if job.resolved_execution_status() == "converting":
        raise JobWorkflowViolation("当前任务正在执行中，暂不支持中断式取消。")

    return WorkflowTransition(
        next_lifecycle_status="canceled",
        next_execution_status="idle",
        context_updates={
            "progress": 100,
            "error_code": None,
            "error_message": None,
            "result_ready": False,
        },
        event_intents=(WorkflowEventIntent(kind="job_canceled"),),
    )


def build_cleanup_local_files_transition(job: JobRecord) -> WorkflowTransition:
    """校验 cleanup-local-files 是否允许执行。"""

    if job.resolved_lifecycle_status() != "completed" or job.resolved_execution_status() != "idle":
        raise JobWorkflowViolation(f"当前状态 `{job.projected_status()}` 不允许 cleanup-local-files。")
    return WorkflowTransition(event_intents=(WorkflowEventIntent(kind="cleanup_local_files"),))


def build_mineru_callback_transition(
    job: JobRecord,
    *,
    callback_state: str,
    batch_id: str | None,
    data_id: str | None,
    full_zip_url: str | None,
) -> WorkflowTransition:
    """根据 callback payload 生成统一的 workflow 迁移结果。"""

    lifecycle_status = job.resolved_lifecycle_status()
    execution_status = job.resolved_execution_status()
    if execution_status != "parsing" and lifecycle_status not in {"parsed", "failed"}:
        raise JobWorkflowViolation(f"当前任务状态 {job.projected_status()} 不允许处理 MinerU callback")
    if job.source_kind != "source_pdf":
        raise JobWorkflowViolation("只有 source_pdf 任务允许处理 MinerU callback")

    source_pdf_patch_kwargs: dict[str, Any] = {
        "upstream_status": callback_state or job.read_mineru_status(),
    }
    if data_id:
        source_pdf_patch_kwargs["data_id"] = str(data_id)
    if batch_id:
        source_pdf_patch_kwargs["batch_id"] = str(batch_id)
    if full_zip_url:
        source_pdf_patch_kwargs["result_zip_url"] = str(full_zip_url)
    context_updates: dict[str, Any] = {
        **build_source_pdf_context_patch(job, **source_pdf_patch_kwargs),
    }

    if callback_state == "done" and full_zip_url:
        context_updates["progress"] = 60
        return WorkflowTransition(
            next_lifecycle_status="parsed",
            next_execution_status="idle",
            context_updates=context_updates,
            event_intents=(WorkflowEventIntent(kind="mineru_callback_processed"),),
        )

    if callback_state == "failed":
        context_updates.update(
            {
                "progress": 100,
                "error_code": "mineru_failed",
                "error_message": "MinerU 返回 failed",
            }
        )
        return WorkflowTransition(
            next_lifecycle_status="failed",
            next_execution_status="idle",
            context_updates=context_updates,
            event_intents=(WorkflowEventIntent(kind="mineru_callback_failed"),),
        )

    return WorkflowTransition(
        context_updates=context_updates,
        event_intents=(WorkflowEventIntent(kind="mineru_callback_processed"),),
    )
