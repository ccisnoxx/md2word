from __future__ import annotations

# app/domains/document_jobs/use_cases/common.py: 各用例共享的常量、结果数据类与 API 异常。

import logging
from dataclasses import dataclass
from typing import Any

from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobRecord
from app.domains.document_jobs.preview import PREVIEW_FILE_TYPES
from app.domains.document_jobs.schemas import (
    DocumentJobAvailableActionResponse,
    DocumentJobDownloadClassification,
)
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.services.document_ir.models import DocumentIR, TableReferenceProvenance
from app.services.document_ir.table_reference_assets import DecodedTableReference


DOCUMENT_JOB_LIST_SORTS = {"created_at_desc", "created_at_asc", "updated_at_desc", "updated_at_asc"}


DOCUMENT_JOB_DOWNLOAD_FILE_TYPES: set[DocumentFileType] = {
    *PREVIEW_FILE_TYPES,
    "source_pdf",
    "mineru_raw_result",
    "document_ir",
    "image_assets_archive",
    "generated_word",
    "ai_call_log",
    "ai_debug_archive",
}


DOCUMENT_JOB_FILE_TYPE_ORDER = {
    "source_pdf": 0,
    "generated_word": 10,
    "mineru_raw_result": 20,
    "document_ir": 30,
    "image_assets_archive": 40,
    "ai_call_log": 50,
    "ai_debug_archive": 60,
}


DOCUMENT_JOB_DELETE_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


DEFAULT_DOCUMENT_JOB_DELETE_REASON = "admin_preview_confirm_delete"


UNREAD_RESULT = object()


SYSTEM_LOGGER = logging.getLogger("system")


class NewGenerationRequestUnavailable(ApiError):
    """503 的命令对账上下文；未知结果不携带否定接受声明。"""

    def __init__(self, request_id: str, *, reason_code: str, accepted_generation: int | None = None):
        message = ("新代请求暂不可确认，请保留原 request_id 对账。" if accepted_generation is None
            else "新代已接受，Worker 投递结果未确认，请保留原 request_id 对账。" if reason_code == "worker_enqueue_failed"
            else "新代已接受，当前状态暂不可读取，请保留原 request_id 对账。")
        super().__init__(503, "service_unavailable", message,
            reason_code=reason_code)
        self.generation_request_id = request_id
        self.accepted_generation = accepted_generation


@dataclass(frozen=True)
class ReviewCommit:
    job: DocumentJobRecord
    accepted_record_id: str
    accepted_sequence: int


@dataclass(frozen=True)
class DocumentJobDownloadPolicy:
    """同次签发和动作投影共用的只读分类，不作为授权凭证持久化。"""

    classification: DocumentJobDownloadClassification | None = None
    warning_code: str | None = None
    warning_message: str | None = None


@dataclass(frozen=True)
class TableReferenceSnapshot:
    job: DocumentJobRecord
    file: DocumentFileRecord
    document: DocumentIR
    references: list[DecodedTableReference]
    provenance: TableReferenceProvenance | None


@dataclass(frozen=True)
class TableReferenceContent:
    """完成快照与完整性检查后，交给认证 HTTP 响应及审计的安全读取结果。"""

    content: bytes
    mime_type: str
    filename: str
    file_id: str
    ir_file_id: str
    generation: int


@dataclass(frozen=True)
class DocumentJobListResult:
    """列表筛选、统计与行响应共享同次观察的任务和动作。"""

    items: list[tuple[DocumentJobRecord, dict[str, DocumentJobAvailableActionResponse]]]
    total: int
    summary: dict[str, int]
    filtered_summary: dict[str, int]
    translation_qa_summary: dict[str, int]


@dataclass(frozen=True)
class DocumentJobDeletePlanFile:
    """任务删除计划中的单个文件决策，不暴露 object_key 或本地路径。"""

    file_id: str
    file_type: str | None
    storage_provider: str | None
    status_before: str | None
    status_after: str | None
    size_bytes: int | None
    action: str
    outcome: str
    reason: str
    deleted: bool = False
    metadata_updated: bool = False
    s3_delete_contract: dict[str, Any] | None = None

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "size_bytes": self.size_bytes,
            "action": self.action,
            "outcome": self.outcome,
            "reason": self.reason,
            "deleted": self.deleted,
            "metadata_updated": self.metadata_updated,
            "s3_delete_contract": self.s3_delete_contract,
        }


@dataclass(frozen=True)
class DocumentJobDeletePlan:
    """任务删除预览或执行结果；router 负责转换为 API response model。"""

    job: DocumentJobRecord
    action_mode: str
    confirmation_phrase: str
    preview_hash: str
    totals: dict[str, int]
    files: list[DocumentJobDeletePlanFile]
    safety: dict[str, bool]
