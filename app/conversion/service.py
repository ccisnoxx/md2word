from __future__ import annotations

from app.conversion.contracts import (
    ArtifactDescriptor,
    ConversionFailure,
    ConversionRequest,
    ConversionResult,
)
from app.conversion.runtime_facade import load_pages, materialize_input, resolve_document_language, run_conversion


class ConversionService:
    def convert(self, request: ConversionRequest) -> ConversionResult:
        try:
            preferred_document_language = request.document_language
            if request.translation_mode == "en2zh" and preferred_document_language == "auto":
                preferred_document_language = "zh"

            with materialize_input(request.package_path) as package_root:
                pages, source_path = load_pages(package_root)
                resolved_document_language = resolve_document_language(
                    pages,
                    preferred=preferred_document_language,
                )

            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            if request.translation_request_output is not None:
                request.translation_request_output.parent.mkdir(parents=True, exist_ok=True)
            if request.translation_trace_output is not None:
                request.translation_trace_output.parent.mkdir(parents=True, exist_ok=True)

            run_conversion(
                job_id=request.job_id,
                input_path=str(request.package_path),
                output_path=str(request.output_path),
                template_path=str(request.template_path) if request.template_path else None,
                subscript_config=str(request.subscript_config_path) if request.subscript_config_path else None,
                no_template=request.template_path is None,
                use_mineru_header_footer=request.use_mineru_header_footer,
                document_language=request.document_language,
                translation_mode=request.translation_mode,
                translation_model=request.translation_model,
                translation_api_key=request.translation_api_key,
                translation_base_url=request.translation_base_url,
                translation_target_language=request.translation_target_language,
                translation_domain=request.translation_domain,
                translation_prompt_version=request.translation_prompt_version,
                translation_max_pages=request.translation_max_pages,
                translation_max_chars=request.translation_max_chars,
                translation_profile=(
                    {
                        "translation_profile_id": request.translation_profile.translation_profile_id,
                        "version": request.translation_profile.version,
                        "snapshot_hash": request.translation_profile.snapshot_hash,
                    }
                    if request.translation_profile is not None
                    else None
                ),
                translation_request_output=str(request.translation_request_output) if request.translation_request_output else None,
                translation_trace_output=str(request.translation_trace_output) if request.translation_trace_output else None,
            )
            if not request.output_path.exists():
                raise ConversionFailure("docx_save_failed", f"DOCX 输出文件不存在: {request.output_path}")

            artifacts = [ArtifactDescriptor(file_type="result_docx", path=request.output_path)]
            if request.translation_request_output is not None and request.translation_request_output.exists():
                artifacts.append(
                    ArtifactDescriptor(
                        file_type="translation_request",
                        path=request.translation_request_output,
                    )
                )
            if request.translation_trace_output is not None and request.translation_trace_output.exists():
                artifacts.append(
                    ArtifactDescriptor(
                        file_type="translation_trace",
                        path=request.translation_trace_output,
                    )
                )

            return ConversionResult(
                source_path=source_path,
                output_docx_path=request.output_path,
                pages=len(pages),
                document_language=resolved_document_language,
                artifacts=artifacts,
            )
        except ConversionFailure:
            raise
        except Exception as exc:
            raise ConversionFailure(self._classify_error_code(exc), str(exc)) from exc

    @staticmethod
    def _classify_error_code(exc: Exception) -> str:
        message = str(exc)
        if "非法路径" in message or "越界" in message or "符号链接" in message:
            return "invalid_package"
        if "content_list" in message:
            return "missing_content_list"
        if "OPENAI_API_KEY" in message:
            return "translation_unavailable"
        if "openai Python SDK" in message:
            return "translation_unavailable"
        if "LLM" in message or "JSON" in message or "items 数组" in message:
            return "translation_failed"
        if "模板文件不存在" in message:
            return "template_not_found"
        return "conversion_failed"
