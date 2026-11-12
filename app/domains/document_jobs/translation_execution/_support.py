"""翻译批次执行的无状态共用辅助：存储异常识别、错误码归类与审计文件 ID 提取。"""

from __future__ import annotations

import sqlite3

from app.domains.translation.audit import TranslationCallAuditRecorder
from app.domains.translation.document_ir_translator import DocumentIRTranslationError
from app.domains.translation.integrity import TranslationIntegrityError
from app.domains.translation.provider import TranslationProviderResponseError


class TranslationBatchStorageError(RuntimeError):
    """翻译成功响应已审计，但批次结果或状态提交写入失败。"""


def is_metadata_storage_error(error: Exception) -> bool:
    """识别仓储驱动异常，避免把数据库故障当成 Provider 失败重试。"""

    error_module = type(error).__module__
    return isinstance(error, (OSError, sqlite3.Error)) or error_module.startswith("pymysql.")


def translation_batch_error_code(error: Exception) -> str:
    if isinstance(error, (TranslationIntegrityError, DocumentIRTranslationError)):
        return error.code
    if isinstance(error, TranslationProviderResponseError) and error.suspected_truncation:
        return "translation_provider_truncated"
    if isinstance(error, (TranslationProviderResponseError, ValueError, KeyError)):
        return "translation_provider_invalid_response"
    return "translation_provider_failed"


def recorder_call_log_file_ids(recorder: TranslationCallAuditRecorder | None) -> list[str]:
    if recorder is None:
        return []
    file_ids = list(getattr(recorder, "call_log_file_ids", []))
    if file_ids:
        return file_ids
    return [recorder.call_log_file_id] if recorder.call_log_file_id is not None else []


def recorder_debug_archive_file_ids(recorder: TranslationCallAuditRecorder | None) -> list[str]:
    if recorder is None:
        return []
    file_ids = list(getattr(recorder, "debug_archive_file_ids", []))
    if file_ids:
        return file_ids
    return [recorder.debug_archive_file_id] if recorder.debug_archive_file_id is not None else []
