"""质量、预览、复核与新代请求的严格 DTO；只服务新复核 API，不改变旧 QA 与任务详情的序列化合同。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.domains.document_jobs.models import (
    DocumentJobDeliveryStatus,
    DocumentJobQualityStatus,
    DocumentJobReviewStatus,
)
from app.domains.document_jobs.views.quality_review import (
    QualityChecksum,
    QualityCount,
    QualityHash,
    QualityId,
    QualityIssue,
    QualityReviewModel,
)
from app.services.document_ir.table_value_column_review import TableValueColumnCorrection, TableValueColumnReview


class ReviewExpectedSourceRequest(QualityReviewModel):
    """五字段均必填；null 表示登记值缺失，不能作为任意来源通配符。"""
    generation: QualityCount
    result_file_id: QualityId | None
    result_sha256: QualityChecksum | None
    file_review_source_revision: QualityCount | None
    receipt_sha256: QualityChecksum | None


class ManualTableValueColumnCorrectionRequest(TableValueColumnCorrection):
    """HTTP 数组可进入领域 tuple，自动出处不属于人工输入。"""

    original_column_range: tuple[QualityCount, QualityCount] = Field(strict=False)
    pdf_binding: SkipJsonSchema[None] = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _reject_pdf_binding(cls, value):
        if isinstance(value, dict) and "pdf_binding" in value:
            raise ValueError("人工核定不能提交自动出处。")
        return value


class ManualTableValueColumnReviewRequest(TableValueColumnReview):
    corrections: tuple[ManualTableValueColumnCorrectionRequest, ...] = Field(min_length=1, strict=False)


class DocumentJobNewGenerationRequest(QualityReviewModel):
    """固定原模式与快照的新代命令，不接受配置或状态覆盖。"""

    request_id: str = Field(description="客户端生成并保留的 UUID；接受前归一为规范格式。")
    note: str
    expected_source: ReviewExpectedSourceRequest
    action: Literal["replay_table_value_columns"] | None = Field(
        default=None, description="核定型请求显式选择从当前同源 MinerU 存档生成新一代。")
    table_value_column_reviews: tuple[ManualTableValueColumnReviewRequest, ...] | None = Field(
        default=None, min_length=1, strict=False, description="同包核定动作所需的整批人工原格记录。")

    @model_validator(mode="after")
    def _validate_action(self) -> Self:
        if (self.action is None) != (self.table_value_column_reviews is None):
            raise ValueError("同包核定动作与人工核定批次必须同时提供。")
        return self

    @field_validator("request_id")
    @classmethod
    def _request_key(cls, value: str) -> str:
        from uuid import UUID
        try:
            key = str(UUID(value))
        except ValueError:
            raise ValueError("request_id 必须是 UUID。") from None
        return key

    @field_validator("note")
    @classmethod
    def _request_note(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 1000:
            raise ValueError("新代原因去除首尾空白后必须为 1..1000 字。")
        return value


class DocumentJobGenerationCurrentResponse(BaseModel):
    """对账仅公开当前任务状态，不附带原配置、私有账本或下载能力。"""

    id: str
    status: str
    stage: str
    progress: int
    retry_count: int
    result_file_id: str | None
    quality_status: DocumentJobQualityStatus
    review_status: DocumentJobReviewStatus
    delivery_status: DocumentJobDeliveryStatus


class DocumentJobNewGenerationResponse(BaseModel):
    """不可变接受事实与当前观察分列，重放可能已观察到后续代次。"""

    accepted: Literal[True] = True
    request_id: str
    job_id: str
    accepted_generation: int
    accepted_at: datetime
    source: ReviewExpectedSourceRequest
    audit_id: str
    replayed: bool
    current_generation: int
    current_job: DocumentJobGenerationCurrentResponse


class DocumentJobNewGenerationErrorDetailResponse(QualityReviewModel):
    code: str
    message: str
    status_code: int
    request_id: str | None
    trace_id: str | None
    reason_code: str | None = None
    generation_request_id: str | None = None
    accepted: Literal[True] | None = None
    accepted_generation: int | None = None


class DocumentJobNewGenerationErrorResponse(QualityReviewModel):
    detail: JsonValue
    error_code: str
    request_id: str | None
    trace_id: str | None
    error: DocumentJobNewGenerationErrorDetailResponse


class DocumentReviewUpdateRequest(QualityReviewModel):
    status: DocumentJobReviewStatus
    issue_type: QualityIssue | None = None
    note: str | None = Field(default=None, max_length=1000)
    expected_source: ReviewExpectedSourceRequest
    acknowledged_table_semantics_report_sha256: QualityHash | None = Field(default=None,
        description="批准时确认已核对该表格报告中的疑似数值列归属。填写当前表格质量详情的 report_sha256。")

    @model_validator(mode="after")
    def _confirm_on_approval(self):
        if self.status != "approved" and self.acknowledged_table_semantics_report_sha256 is not None:
            raise ValueError("仅批准复核可以确认数值列归属报告。")
        return self


class QualityReviewErrorDetailResponse(QualityReviewModel):
    code: str
    message: str
    status_code: int
    request_id: str | None
    trace_id: str | None
    reason_code: str | None = None


class QualityReviewErrorResponse(QualityReviewModel):
    """受控质量、复核和发布操作的安全错误模型，兼容原 detail 结构。"""
    detail: JsonValue
    error_code: str
    request_id: str | None
    trace_id: str | None
    error: QualityReviewErrorDetailResponse
