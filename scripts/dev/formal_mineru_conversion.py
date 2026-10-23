#!/usr/bin/env python3
"""通过正式 DocumentIR Word renderer 转换本地 MinerU 结果包。"""

from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.domains.translation.document_ir_translator import DocumentIRTranslationBatchPlan, DocumentIRTranslationService
from app.domains.translation.models import TranslationProviderRequest, TranslationProviderResult
from app.domains.translation.modes import is_translation_mode, language_pair_for_translation_mode, normalize_translation_mode
from app.domains.translation.provider import OpenAICompatibleTranslationProvider, TranslationProviderResponseError
from app.domains.translation.provider_config import EffectiveAiProviderConfig
from app.services.document_ir import MinerUToDocumentIRService
from app.services.document_ir.models import DocumentIR, DocumentIRAsset
from app.services.renderer import DocumentIRRenderOptions, DocumentIRWordRenderer
from app.services.renderer.word_renderer import DocumentIRRenderResult
from app.services.renderer.evidence import build_renderer_evidence, ensure_renderer_integrity


LOCAL_JOB_ID = "local_mineru_debug"
LOCAL_SOURCE_FILE_ID = "local_mineru_input"


@dataclass(frozen=True, slots=True)
class FormalMinerUConversionRequest:
    """正式 DocumentIR 转换核心的本地文件请求。"""

    input_path: Path
    output_path: Path
    template_path: Path | None = None
    layout_config_path: Path | None = None
    subscript_config_path: Path | None = None
    no_template: bool = False
    use_mineru_header_footer: bool = False
    document_language: str = "auto"
    translation_mode: str = "direct"
    translation_request_output: Path | None = None
    translation_response: Path | None = None
    translation_trace_output: Path | None = None
    translation_model: str | None = None
    translation_api_key: str | None = None
    translation_base_url: str | None = None
    translation_max_pages: int = 20
    translation_max_chars: int = 60_000
    job_id: str = LOCAL_JOB_ID
    source_file_id: str = LOCAL_SOURCE_FILE_ID


@dataclass(frozen=True, slots=True)
class FormalMinerUConversionResult:
    """正式渲染链路产生的本地文件与诊断。"""

    source_path: Path
    output_docx_path: Path
    document_ir_path: Path
    source_document_ir_path: Path | None
    pages: int
    blocks: int
    image_assets: int
    document_language: str
    renderer_metadata: dict[str, Any]
    docx_quality: dict[str, Any]
    quality_flags: list[str] = field(default_factory=list)


class LocalTranslationResponseProvider:
    """按原顺序消费本地响应；禁止以字典覆盖、筛选或重排修复返回项。"""

    def __init__(self, response_path: Path, expected_requests: tuple[TranslationProviderRequest, ...]) -> None:
        self.response_path = response_path
        self._position = 0

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise TranslationProviderResponseError("本地翻译响应包含重复 JSON 键。")
                result[key] = value
            return result

        payload = json.loads(response_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        self._batches = None
        if isinstance(payload, dict) and set(payload) == {"batches"} and isinstance(payload["batches"], list):
            self._batches = []
            for batch in payload["batches"]:
                if not isinstance(batch, dict) or set(batch) not in ({"items"}, {"batch_id", "items"}):
                    raise TranslationProviderResponseError("本地翻译响应批次字段无效。")
                if "batch_id" in batch and (not isinstance(batch["batch_id"], str) or not batch["batch_id"].strip()):
                    raise TranslationProviderResponseError("本地翻译响应批次 ID 无效。")
                items = OpenAICompatibleTranslationProvider._parse_items({"items": batch["items"]})
                self._batches.append((batch.get("batch_id"), items))
            self._items = ()
        else:
            self._items = OpenAICompatibleTranslationProvider._parse_items(payload)
        if self._batches is not None:
            if len(self._batches) != len(expected_requests):
                raise TranslationProviderResponseError("本地翻译响应批次数与实际计划不一致。")
            for (batch_id, items), request in zip(self._batches, expected_requests):
                if batch_id is not None and batch_id != request.batch_id:
                    raise TranslationProviderResponseError("本地翻译响应批次 ID 与实际计划不一致。")
                if tuple(item.id for item in items) != tuple(item.id for item in request.items):
                    raise TranslationProviderResponseError("本地翻译响应批次有序 ID 与实际计划不一致。")
        elif tuple(item.id for item in self._items) != tuple(item.id for request in expected_requests for item in request.items):
            raise TranslationProviderResponseError("本地翻译响应完整有序 ID 与实际计划不一致。")

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        if self._batches is not None:
            if self._position >= len(self._batches):
                raise TranslationProviderResponseError("本地翻译响应缺少批次。")
            batch_id, items = self._batches[self._position]
            self._position += 1
            if batch_id is not None and batch_id != request.batch_id:
                raise TranslationProviderResponseError("本地翻译响应批次 ID 与实际请求不一致。")
        else:
            end = self._position + len(request.items)
            items = self._items[self._position:end]
            self._position = end
        return TranslationProviderResult(items=items, response_id=str(self.response_path))


class RequestOnlyTranslationProvider:
    """仅供共享计划与请求准备使用，不执行翻译。"""

    def translate(self, request: TranslationProviderRequest) -> TranslationProviderResult:
        raise RuntimeError("仅规划 Provider 不可执行翻译。")


def run_conversion(
    *,
    input_path: str,
    output_path: str | None,
    template_path: str | None,
    subscript_config: str | None,
    no_template: bool,
    use_mineru_header_footer: bool,
    layout_config_path: str | None = None,
    document_language: str = "auto",
    translation_mode: str = "direct",
    translation_request_output: str | None = None,
    translation_response: str | None = None,
    translation_model: str | None = None,
    translation_api_key: str | None = None,
    translation_base_url: str | None = None,
    translation_max_pages: int = 20,
    translation_max_chars: int = 60_000,
    translation_trace_output: str | None = None,
    job_id: str | None = None,
    **_ignored: Any,
) -> FormalMinerUConversionResult:
    """以兼容参数形状调用正式 DocumentIR renderer 的本地入口。"""

    settings = Settings()
    resolved_template_path = _resolve_optional_path(template_path)
    resolved_layout_config_path = _resolve_optional_path(layout_config_path)
    if not no_template and resolved_template_path is None:
        resolved_template_path = settings.default_template_path
        if resolved_template_path is None:
            raise FileNotFoundError("默认 Word 模板不存在。")
    if resolved_layout_config_path is None:
        resolved_layout_config_path = settings.layout_config_path
        if resolved_layout_config_path is None:
            raise FileNotFoundError("默认版式配置文件不存在。")
    request = FormalMinerUConversionRequest(
        input_path=Path(input_path).expanduser().resolve(),
        output_path=_resolve_output_path(input_path, output_path),
        template_path=resolved_template_path if not no_template else None,
        layout_config_path=resolved_layout_config_path,
        subscript_config_path=_resolve_optional_path(subscript_config),
        no_template=bool(no_template),
        use_mineru_header_footer=bool(use_mineru_header_footer),
        document_language=str(document_language or "auto"),
        translation_mode=normalize_translation_mode(translation_mode),
        translation_request_output=_resolve_optional_path(translation_request_output),
        translation_response=_resolve_optional_path(translation_response),
        translation_trace_output=_resolve_optional_path(translation_trace_output),
        translation_model=translation_model,
        translation_api_key=translation_api_key,
        translation_base_url=translation_base_url,
        translation_max_pages=max(1, int(translation_max_pages)),
        translation_max_chars=max(1, int(translation_max_chars)),
        job_id=str(job_id or LOCAL_JOB_ID),
    )
    return convert_formal_mineru_package(request)


def convert_formal_mineru_package(request: FormalMinerUConversionRequest) -> FormalMinerUConversionResult:
    """使用 document_jobs 同一组核心服务转换本地 MinerU 结果包。"""

    _validate_request_paths(request)
    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    _mkdir_parent(request.translation_request_output)
    _mkdir_parent(request.translation_trace_output)

    with tempfile.TemporaryDirectory(prefix="formal_local_mineru_") as temp_dir:
        zip_path = _materialize_mineru_zip(request.input_path, Path(temp_dir))
        result = MinerUToDocumentIRService().convert_zip(
            zip_path,
            job_id=request.job_id,
            source_file_id=request.source_file_id,
            document_language=request.document_language,
        )
        source_document_ir = result.document
        document_ir = _translate_if_needed(source_document_ir, request)
        render_result = _render_document(document_ir, result.image_assets, request)
        word_content = render_result.content

    renderer_metadata = build_renderer_evidence(document_ir, word_content, formula_report=render_result.formula_report)
    ensure_renderer_integrity(renderer_metadata)
    document_ir_path = _document_ir_output_path(request.output_path)
    document_ir_path.write_text(document_ir.model_dump_json(indent=2), encoding="utf-8")
    source_document_ir_path = None
    if is_translation_mode(request.translation_mode):
        source_document_ir_path = _source_document_ir_output_path(request.output_path)
        source_document_ir_path.write_text(source_document_ir.model_dump_json(indent=2), encoding="utf-8")

    request.output_path.write_bytes(word_content)
    docx_quality = renderer_metadata["docx_quality"]
    quality_flags = renderer_metadata["quality_flags"]
    return FormalMinerUConversionResult(
        source_path=request.input_path,
        output_docx_path=request.output_path,
        document_ir_path=document_ir_path,
        source_document_ir_path=source_document_ir_path,
        pages=len(document_ir.pages),
        blocks=len(document_ir.blocks),
        image_assets=len(result.image_assets),
        document_language=document_ir.metadata.document_language,
        renderer_metadata=renderer_metadata,
        docx_quality=docx_quality,
        quality_flags=quality_flags,
    )


def _translate_if_needed(document_ir: DocumentIR, request: FormalMinerUConversionRequest) -> DocumentIR:
    if not is_translation_mode(request.translation_mode):
        return document_ir
    language_pair = language_pair_for_translation_mode(request.translation_mode)
    if language_pair is None:
        return document_ir

    planner = DocumentIRTranslationService(
        RequestOnlyTranslationProvider(),
        max_chars_per_request=request.translation_max_chars,
    )
    _targets, items, batches = planner.build_translation_plan(
        document_ir, max_pages_per_batch=request.translation_max_pages,
        max_chars_per_batch=request.translation_max_chars,
        batch_id_prefix="document_ir_provider_request",
    )
    items_by_id = {item.id: item for item in items}
    prepared_requests = tuple(planner.build_provider_request(
        document_ir, [items_by_id[item_id] for item_id in batch.item_ids],
        term_version=None, language_pair=language_pair, batch_id=batch.batch_id,
        page_start=batch.page_start, page_end=batch.page_end,
        max_chars_per_request=request.translation_max_chars,
    ).request for batch in batches)
    if request.translation_request_output is not None:
        _write_translation_request(request, batches, prepared_requests)
    source_items = {item.id: item.text for item in items}
    provider = (
        LocalTranslationResponseProvider(request.translation_response, prepared_requests)
        if request.translation_response is not None
        else _build_openai_provider(request)
    )
    service = DocumentIRTranslationService(provider, max_chars_per_request=request.translation_max_chars)
    translated = service.translate(
        document_ir, term_version=None, language_pair=language_pair,
        max_pages_per_batch=request.translation_max_pages,
    )
    if request.translation_trace_output is not None:
        translated_items = {item.id: item.text for item in service.extract_translation_items(translated)[1]}
        _write_translation_trace(source_items, translated_items, request, language_pair=language_pair)
    return translated


def _build_openai_provider(request: FormalMinerUConversionRequest) -> OpenAICompatibleTranslationProvider:
    settings = Settings()
    api_key = _strip_optional(request.translation_api_key) or _strip_optional(settings.openai_api_key)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法调用翻译 provider。")
    config = EffectiveAiProviderConfig(
        backend="openai_compatible",
        base_url=_strip_optional(request.translation_base_url) or _strip_optional(settings.openai_base_url),
        api_key=api_key,
        model=_strip_optional(request.translation_model) or _strip_optional(settings.openai_model) or "deepseek-v4-flash",
        timeout_seconds=settings.translation_provider_timeout_seconds,
        max_output_tokens=settings.translation_provider_max_output_tokens,
        source="settings",
    )
    return OpenAICompatibleTranslationProvider(settings, config_resolver=lambda: config)


def _write_translation_request(
    request: FormalMinerUConversionRequest,
    batches: list[DocumentIRTranslationBatchPlan],
    prepared_requests: tuple[TranslationProviderRequest, ...],
) -> None:
    """导出共享准备接口的真实请求，不将原文项冒充编码输入。"""
    exported_batches = []
    for batch, prepared in zip(batches, prepared_requests):
        exported_batches.append({
            "batch_id": batch.batch_id, "page_start": batch.page_start, "page_end": batch.page_end,
            "item_count": batch.item_count, "char_count": batch.char_count,
            "encoded_char_count": sum(len(item.text) for item in prepared.items),
            "items": [{"id": item.id, "text": item.text} for item in prepared.items],
        })
    payload = {
        "schema_version": "document-ir-local-translation-request/v2",
        "job_id": request.job_id, "language_pair": language_pair_for_translation_mode(request.translation_mode),
        "item_count": sum(len(prepared.items) for prepared in prepared_requests),
        "items": [item for batch in exported_batches for item in batch["items"]],
        "batches": exported_batches,
    }
    request.translation_request_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_translation_trace(
    source_items: dict[str, str],
    translated_items: dict[str, str],
    request: FormalMinerUConversionRequest,
    *,
    language_pair: str,
) -> None:
    payload = {
        "schema_version": "document-ir-local-translation-trace/v1",
        "job_id": request.job_id,
        "language_pair": language_pair,
        "model": request.translation_model,
        "segments": [
            {
                "id": item_id,
                "source_text": source_text,
                "translated_text": translated_items.get(item_id, ""),
            }
            for item_id, source_text in source_items.items()
        ],
    }
    request.translation_trace_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_document(
    document_ir: DocumentIR,
    image_assets: list[Any],
    request: FormalMinerUConversionRequest,
) -> DocumentIRRenderResult:
    image_content_by_asset_id = {image_asset.asset_id: image_asset.content for image_asset in image_assets}

    def load_image(asset: DocumentIRAsset) -> bytes | None:
        return image_content_by_asset_id.get(asset.id)

    template_path = None if request.no_template else request.template_path
    return DocumentIRWordRenderer().render_to_result(
        document_ir,
        template_path=template_path,
        config_path=request.layout_config_path,
        image_loader=load_image,
        options=DocumentIRRenderOptions(
            subscript_config_path=request.subscript_config_path,
            document_language=document_ir.metadata.document_language,
        ),
    )


def _materialize_mineru_zip(input_path: Path, temp_dir: Path) -> Path:
    if input_path.is_file():
        return input_path
    if not input_path.is_dir():
        raise FileNotFoundError(f"MinerU 输入不存在: {input_path}")
    zip_path = temp_dir / f"{input_path.name or 'mineru-package'}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(input_path.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"MinerU 输入目录包含符号链接: {path}")
            if not path.is_file():
                continue
            archive.write(path, path.relative_to(input_path).as_posix())
    return zip_path


def _validate_request_paths(request: FormalMinerUConversionRequest) -> None:
    if not request.input_path.exists():
        raise FileNotFoundError(f"MinerU 输入不存在: {request.input_path}")
    if request.template_path is not None and not request.no_template and not request.template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {request.template_path}")
    if request.layout_config_path is not None and not request.layout_config_path.exists():
        raise FileNotFoundError(f"版式配置文件不存在: {request.layout_config_path}")
    if request.translation_response is not None and not request.translation_response.exists():
        raise FileNotFoundError(f"翻译响应文件不存在: {request.translation_response}")


def _document_ir_output_path(output_path: Path) -> Path:
    return output_path.with_suffix(".document-ir.json")


def _source_document_ir_output_path(output_path: Path) -> Path:
    return output_path.with_suffix(".source-document-ir.json")


def _resolve_output_path(input_path: str, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path).expanduser().resolve()
    source = Path(input_path).expanduser()
    return source.with_suffix(".docx").resolve()


def _resolve_optional_path(value: str | None) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value)).expanduser().resolve()


def _mkdir_parent(path: Path | None) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
