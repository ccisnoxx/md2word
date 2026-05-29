from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from app.core.translation_models import TranslationProfileSnapshot


ConversionTranslationMode = Literal["direct", "en2zh"]
ConversionDocumentLanguage = Literal["auto", "zh", "en"]
ResolvedDocumentLanguage = Literal["zh", "en"]


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    file_type: str
    path: Path


@dataclass(frozen=True, slots=True)
class ConversionRequest:
    job_id: str
    package_path: Path
    output_path: Path
    template_path: Path | None
    subscript_config_path: Path | None
    translation_mode: ConversionTranslationMode
    document_language: ConversionDocumentLanguage
    use_mineru_header_footer: bool
    translation_model: str
    translation_api_key: str | None
    translation_base_url: str | None
    translation_target_language: str
    translation_domain: str
    translation_prompt_version: str
    translation_max_pages: int
    translation_max_chars: int
    translation_profile: TranslationProfileSnapshot | None = None
    translation_request_output: Path | None = None
    translation_trace_output: Path | None = None


@dataclass(frozen=True, slots=True)
class ConversionResult:
    source_path: Path
    output_docx_path: Path
    pages: int
    document_language: ResolvedDocumentLanguage
    artifacts: list[ArtifactDescriptor] = field(default_factory=list)


class ConversionFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ConversionEntrypoint(Protocol):
    def convert(self, request: ConversionRequest) -> ConversionResult: ...
