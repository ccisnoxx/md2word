"""Worker 失败分类、安全消息和证据的纯决策；状态提交与日志由执行器负责。"""

from __future__ import annotations

import zipfile
from typing import Any

from app.clients.mineru_client import MinerUError
from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobStage
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.services.document_ir.artifact_validator import MinerUArtifactValidationError
from app.services.document_ir.integrity import DocumentIntegrityError
from app.services.document_ir.table_placeholder import TablePlaceholderError
from app.services.renderer.render_event_summary import build_renderer_event_summary
from app.services.renderer.table_renderer import TableRenderError
from app.services.failure_context import FAILURE_CONTEXT_ATTRIBUTE
from app.services.tables.evidence import TableEvidenceError
from app.services.tables.html_normalizer import TableBuildError
from app.services.tables.quality import TableValidationError


# 消息只由固定错误码或固定文本构造的异常；其消息可原样作为任务 error_message。
SAFE_MESSAGE_ERRORS = (MinerUArtifactValidationError, TablePlaceholderError, TableRenderError, TableBuildError,
                       TableEvidenceError, TableValidationError, TranslationIntegrityError)
_EXPECTED_WORKER_ERRORS = (ApiError, FileNotFoundError, OSError, ValueError, RuntimeError, MinerUError, zipfile.BadZipFile)


def failed_stage_for_current_stage(stage: DocumentJobStage) -> DocumentJobStage:
    if stage == "uploaded":
        return "uploaded"
    if stage in {"translating", "translation_validating", "rendering", "quality_checking", "uploading"}:
        return stage
    if stage == "ir_converting":
        return "ir_converting"
    return "parsing"


def classify_worker_failure(
    exc: Exception,
    stage: DocumentJobStage,
) -> tuple[DocumentJobStage, str]:
    failed_stage = failed_stage_for_current_stage(stage)
    if isinstance(exc, (TablePlaceholderError, DocumentIntegrityError, TableEvidenceError)) and stage == "uploading":
        return "quality_checking", "render_failed"
    if isinstance(exc, MinerUError) or failed_stage == "parsing":
        return failed_stage, "mineru_failed"
    if isinstance(exc, (DocumentIRTranslationError, TranslationIntegrityError)):
        return failed_stage, "translation_failed"
    if isinstance(exc, zipfile.BadZipFile) or failed_stage == "ir_converting":
        return failed_stage, "document_ir_failed"
    if failed_stage in {"rendering", "quality_checking"}:
        return failed_stage, "render_failed"
    if failed_stage in {"translating", "translation_validating"}:
        if isinstance(exc, (ApiError, FileNotFoundError, OSError)):
            return failed_stage, "oss_failed"
        return failed_stage, "translation_failed"
    if failed_stage == "uploading" or isinstance(exc, (ApiError, FileNotFoundError, OSError)):
        return failed_stage, "oss_failed"
    return failed_stage, "document_job_worker_failed"


def worker_failure_message(error: Exception) -> str:
    """Worker 失败消息唯一构造点：只保留由固定码/固定文本构造的消息，任意异常原文不进入任务、事件或日志。"""
    if isinstance(error, DocumentIntegrityError):
        return str(DocumentIntegrityError(error.boundary, build_renderer_event_summary(dict(error.evidence))))
    if isinstance(error, MinerUError):
        return "MinerU 外部调用失败。"
    if isinstance(error, OSError):
        return "Worker 文件或对象存储操作失败。"
    if isinstance(error, SAFE_MESSAGE_ERRORS):
        return str(error)
    if isinstance(error, DocumentIRTranslationError):
        # 该类型会包装上游 str(exc)，只公开机器码。
        return f"翻译处理失败：{error.code}。"
    return f"Worker 执行失败（{type(error).__name__}），详见事件 trace_id。"


def worker_failure_evidence(error: Exception) -> dict[str, Any]:
    """提取原异常拥有的结构化报告，不读取可能已换代的任务状态。"""

    evidence: dict[str, Any] = {}
    if isinstance(error, MinerUArtifactValidationError):
        evidence["mineru_validation"] = error.report.model_dump(mode="json")
    elif isinstance(error, TablePlaceholderError) and getattr(error, "mineru_validation_report", None) is not None:
        evidence["mineru_validation"] = error.mineru_validation_report.model_dump(mode="json")
    elif isinstance(error, DocumentIntegrityError):
        evidence = dict(error.evidence)
    validation_input = getattr(error, "mineru_validation_input", None)
    if validation_input is not None:
        evidence["mineru_validation_input"] = validation_input
    context = getattr(error, FAILURE_CONTEXT_ATTRIBUTE, None)
    if isinstance(context, dict):
        # 原因码优先取固定错误码，其次完整性阻断码，否则为异常类型名；均由白名单再次过滤。
        flags = error.evidence.get("blocking_quality_flags") if isinstance(error, DocumentIntegrityError) else None
        code = getattr(error, "code", None)
        reason = (code if isinstance(code, str) else flags[0] if isinstance(flags, list) and flags
                  and isinstance(flags[0], str) else type(error).__name__)
        evidence["failure_context"] = {**context, "reason_code": reason}
    return build_renderer_event_summary(evidence)


def stage_attempt_failure(error: Exception, stage: DocumentJobStage) -> tuple[DocumentJobStage, str, str]:
    """普通阶段的最终失败决策；超时已由调用方按原顺序收口。"""

    failed_stage, error_code = classify_worker_failure(error, stage)
    error_message = worker_failure_message(error)
    if not isinstance(error, _EXPECTED_WORKER_ERRORS):
        error_code = "document_job_unexpected_error"
        error_message = "Worker 执行发生未预期异常。"
    return failed_stage, error_code, error_message


def render_failure(
    error: Exception, stage: DocumentJobStage, *, validating_legacy: bool,
) -> tuple[DocumentJobStage, str, DocumentJobStage | None]:
    """返回渲染最终阶段、错误码及未预期异常日志的原始阶段。

    渲染路径沿用安全消息；TableEvidence 与 legacy 规则按原顺序覆盖错误码，
    不改写覆盖前日志记录的阶段。
    """

    failed_stage, error_code = classify_worker_failure(error, stage)
    unexpected_log_stage = None
    if not isinstance(error, _EXPECTED_WORKER_ERRORS):
        error_code = "document_job_unexpected_error"
        unexpected_log_stage = failed_stage
    if isinstance(error, TableEvidenceError):
        failed_stage, error_code = "quality_checking", "render_failed"
    if validating_legacy:
        failed_stage, error_code = "uploading", "oss_failed"
        if (isinstance(error, DocumentIntegrityError)
                and error.evidence.get("renderer_content_contract_version") == "renderer-content/v2"):
            failed_stage, error_code = "quality_checking", "render_failed"
    return failed_stage, error_code, unexpected_log_stage
