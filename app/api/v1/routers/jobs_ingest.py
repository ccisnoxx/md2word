from __future__ import annotations

# app/api/v1/routers/jobs_ingest.py: 接收 job 创建请求并提交后台 stage 调度。

import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.dependencies import get_runtime, get_trace_id, require_jobs_access
from app.core.job_models import ConversionOptions
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import JobAcceptedResponse


router = APIRouter()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_conversion_options(
    template_id: str | None,
    translation_mode: str | None,
    document_language: str | None,
    use_mineru_header_footer: bool,
    runtime: AppRuntime,
) -> ConversionOptions:
    normalized_translation_mode = (_normalize_optional_text(translation_mode) or runtime.settings.default_translation_mode).lower()
    normalized_document_language = (_normalize_optional_text(document_language) or "auto").lower()
    try:
        normalized_template_id = runtime.template_read_service.resolve_selected_template_id(_normalize_optional_text(template_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if normalized_translation_mode not in {"direct", "en2zh"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="translation_mode 仅支持 direct 或 en2zh。",
        )
    if normalized_document_language not in {"auto", "zh", "en"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_language 仅支持 auto、zh、en。",
        )

    return ConversionOptions(
        template_id=normalized_template_id,
        translation_mode=normalized_translation_mode,
        document_language=normalized_document_language,
        use_mineru_header_footer=use_mineru_header_footer,
    )


def _ensure_translation_available(runtime: AppRuntime, options: ConversionOptions) -> None:
    if options.translation_mode != "en2zh":
        return
    dependency_checks = runtime.health_service.build_dependency_checks()
    if not dependency_checks["translation_available"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=dependency_checks.get("translation_unavailable_reason", "翻译能力当前不可用。"),
        )


async def _save_upload_to_temp(upload: UploadFile, runtime: AppRuntime) -> Path:
    filename = _normalize_optional_text(upload.filename)
    if filename is None or not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件必须是 .zip 格式的 MinerU 输出包。",
        )

    runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = runtime.settings.tmp_dir / f"upload_{uuid4().hex}.zip"
    total_size = 0

    with temp_path.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > runtime.settings.jobs_upload_max_bytes:
                output.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"上传文件超过大小限制 {runtime.settings.jobs_upload_max_bytes} bytes。",
                )
            output.write(chunk)
    await upload.close()

    if not zipfile.is_zipfile(temp_path):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不是合法 zip 包。",
        )
    return temp_path


async def _save_pdf_upload_to_temp(upload: UploadFile, runtime: AppRuntime) -> Path:
    filename = _normalize_optional_text(upload.filename)
    if filename is None or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件必须是 .pdf 格式。",
        )
    if upload.content_type and upload.content_type.lower() not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 PDF content-type: {upload.content_type}",
        )

    runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = runtime.settings.tmp_dir / f"upload_{uuid4().hex}.pdf"
    total_size = 0
    file_header = b""

    with temp_path.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            if not file_header:
                file_header = chunk[:8]
            total_size += len(chunk)
            if total_size > runtime.settings.jobs_upload_max_bytes:
                output.close()
                temp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"上传文件超过大小限制 {runtime.settings.jobs_upload_max_bytes} bytes。",
                )
            output.write(chunk)
    await upload.close()

    if not file_header.startswith(b"%PDF-"):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件不是合法 PDF。",
        )
    return temp_path


@router.post("", response_model=JobAcceptedResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_jobs_access)])
async def create_job(
    background_tasks: BackgroundTasks,
    request: Request,
    package: UploadFile = File(...),
    template_id: str | None = Form(default=None),
    translation_mode: str | None = Form(default=None),
    document_language: str | None = Form(default=None),
    use_mineru_header_footer: bool = Form(default=False),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobAcceptedResponse:
    options = _build_conversion_options(
        template_id,
        translation_mode,
        document_language,
        use_mineru_header_footer,
        runtime,
    )
    _ensure_translation_available(runtime, options)
    temp_upload_path = await _save_upload_to_temp(package, runtime)

    try:
        job, stage_message = runtime.command_service.create_job_from_saved_upload(
            temp_upload_path=temp_upload_path,
            source_filename=package.filename or temp_upload_path.name,
            options=options,
            trace_id=trace_id,
        )
    except Exception:
        temp_upload_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(runtime.stage_dispatcher.dispatch, stage_message.id)
    return JobAcceptedResponse(
        job_id=job.id,
        trace_id=trace_id,
        status=job.status,
        translation_mode=job.translation_mode,
    )


@router.post("/pdf", response_model=JobAcceptedResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_jobs_access)])
async def create_pdf_job(
    background_tasks: BackgroundTasks,
    pdf: UploadFile = File(...),
    template_id: str | None = Form(default=None),
    translation_mode: str | None = Form(default=None),
    document_language: str | None = Form(default=None),
    use_mineru_header_footer: bool = Form(default=False),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> JobAcceptedResponse:
    if not runtime.settings.mineru_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MINERU_API_TOKEN 未配置，PDF 在线解析不可用。",
        )
    options = _build_conversion_options(
        template_id,
        translation_mode,
        document_language,
        use_mineru_header_footer,
        runtime,
    )
    _ensure_translation_available(runtime, options)
    temp_upload_path = await _save_pdf_upload_to_temp(pdf, runtime)

    try:
        job, stage_message = runtime.command_service.create_job_from_pdf_upload(
            temp_upload_path=temp_upload_path,
            source_filename=pdf.filename or temp_upload_path.name,
            options=options,
            trace_id=trace_id,
        )
    except Exception:
        temp_upload_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(runtime.stage_dispatcher.dispatch, stage_message.id)
    return JobAcceptedResponse(
        job_id=job.id,
        trace_id=trace_id,
        status=job.status,
        translation_mode=job.translation_mode,
    )
