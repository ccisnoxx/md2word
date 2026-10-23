"""word-preview-exec/v1 的固定请求、结果和能力 schema。"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from app.services.preview.models import PreviewPolicy, PreviewErrorCode, SHA256_PATTERN

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
