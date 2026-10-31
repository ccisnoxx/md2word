"""word-preview-exec/v1 的固定请求、结果和能力 schema。"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from app.services.preview.models import PreviewPolicy, PreviewErrorCode, SHA256_PATTERN
from app.services.preview.page_quality import PageObservationBatch, PageQualityPolicy

PROTOCOL = "word-preview-exec/v1"


class ProtocolRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_version: Literal["word-preview-exec/v1"]
    profile_id: str
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    provider_version: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.+-]+$")


class ExecutorCapabilities(ProtocolRecord):
    engine_version: str = Field(min_length=1, max_length=100)
    validator_version: str = Field(min_length=1, max_length=100)
    pdf_full_decode: StrictBool
    png_decode: StrictBool


class OutputFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    mime_type: str
    size_bytes: StrictInt = Field(gt=0)
    sha256: str = Field(pattern=SHA256_PATTERN)


class PageFile(OutputFile):
    page_index: StrictInt = Field(ge=0)
    width: StrictInt = Field(gt=0)
    height: StrictInt = Field(gt=0)


class ExecutorResult(ProtocolRecord):
    status: Literal["ok", "error"]
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    page_count: StrictInt | None = Field(default=None, gt=0)
    pdf: OutputFile | None = None
    pages: list[PageFile] = Field(default_factory=list)
    error_code: PreviewErrorCode | None = None


def render_request(docx_hash: str, size: int, policy: PreviewPolicy, budget_ms: int) -> dict:
    return {
        "protocol_version": PROTOCOL,
        "input": {"path": "source.docx", "sha256": docx_hash, "size_bytes": size},
        "profile_id": policy.profile_id, "profile_sha256": policy.profile_sha256,
        "render_pages": policy.render_pages, "budget_ms": budget_ms,
        "limits": {name: getattr(policy, name) for name in (
            "max_output_bytes", "max_pages", "max_page_pixels", "max_temp_bytes",
            "max_cpu_seconds", "max_memory_bytes", "max_processes",
        )},
    }


# 页面观测使用独立协议，避免改变旧 render schema 的封闭字段和退出语义。
OBSERVE_PROTOCOL = "word-page-observe/v1"


class ObserveLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    max_output_bytes: StrictInt = Field(gt=0)
    max_pages: StrictInt = Field(gt=0)
    max_page_pixels: StrictInt = Field(gt=0)
    max_temp_bytes: StrictInt = Field(gt=0)
    max_cpu_seconds: StrictInt = Field(gt=0)
    max_memory_bytes: StrictInt = Field(gt=0)
    max_processes: StrictInt = Field(gt=0)


class ObserveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    protocol_version: Literal["word-page-observe/v1"] = OBSERVE_PROTOCOL
    input: OutputFile
    pages: list[PageFile]
    page_count: StrictInt = Field(gt=0)
    profile_id: str
    profile_sha256: str = Field(pattern=SHA256_PATTERN)
    analyzer_version: Literal["native-page-observer/v1"]
    policy: PageQualityPolicy
    budget_ms: StrictInt = Field(gt=0)
    limits: ObserveLimits


class ObserveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocol_version: Literal["word-page-observe/v1"] = OBSERVE_PROTOCOL
    observation: PageObservationBatch


def observe_request(pdf_hash: str, size: int, *, pages: list[PageFile], page_count: int,
                    policy: PageQualityPolicy, preview_policy: PreviewPolicy, budget_ms: int) -> ObserveRequest:
    return ObserveRequest(input=OutputFile(path="preview.pdf", mime_type="application/pdf", size_bytes=size, sha256=pdf_hash),
        pages=pages, page_count=page_count, profile_id=policy.profile_id, profile_sha256=policy.profile_sha256,
        analyzer_version=policy.analyzer_version, policy=policy, budget_ms=budget_ms,
        limits=ObserveLimits(**{key: getattr(preview_policy, key) for key in ObserveLimits.model_fields}))
