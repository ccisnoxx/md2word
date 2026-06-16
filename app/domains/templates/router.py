from __future__ import annotations

# app/domains/templates/router.py: 提供模板查询、下载和默认模板切换接口。

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_runtime, get_trace_id, require_admin_actor
from app.api.errors import bad_request_http_exception, not_found_http_exception
from app.domains.audit.models import ActorContext
from app.core.runtime import AppRuntime
from app.domains.templates.schemas import (
    TemplateDeleteResponse,
    TemplateDetailResponse,
    TemplateListResponse,
    TemplateUpdateRequest,
    TemplateVersionDefaultRequest,
    TemplateVersionListResponse,
    TemplateVersionPublishRequest,
    TemplateVersionResponse,
)


router = APIRouter(prefix="/templates", tags=["templates"])


async def _save_template_upload_to_temp(upload: UploadFile, runtime: AppRuntime) -> Path:
    filename = Path(upload.filename or "").name
    if not filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板文件必须是 .docx 格式。",
        )

    runtime.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = runtime.settings.tmp_dir / f"template_{uuid4().hex}.docx"
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
    return temp_path


def _parse_render_policy(raw_value: str | None) -> dict:
    if raw_value is None or not raw_value.strip():
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="render_policy_json 必须是 JSON object。",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="render_policy_json 必须是 JSON object。",
        )
    return parsed


def _template_versioning_unavailable_http_exception(exc: RuntimeError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get("", response_model=TemplateListResponse)
def list_templates(
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> TemplateListResponse:
    items = runtime.template_read_service.list_templates(url_for=request.url_for)
    return TemplateListResponse(items=items)


@router.post("", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: Request,
    template_id: str = Form(...),
    name: str = Form(...),
    description: str = Form(default=""),
    enabled: bool = Form(default=True),
    layout_config_path: str | None = Form(default=None),
    render_policy_json: str = Form(default="{}"),
    template: UploadFile = File(...),
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateDetailResponse:
    temp_path = await _save_template_upload_to_temp(template, runtime)
    render_policy = _parse_render_policy(render_policy_json)
    try:
        runtime.template_read_service.create_template(
            template_id=template_id,
            name=name,
            description=description,
            enabled=enabled,
            source_path=temp_path,
            source_filename=template.filename or f"{template_id}.docx",
            layout_config_path=layout_config_path,
            render_policy=render_policy,
        )
    except FileNotFoundError as exc:
        temp_path.unlink(missing_ok=True)
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        temp_path.unlink(missing_ok=True)
        raise bad_request_http_exception(exc) from exc

    detail = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    assert detail is not None
    runtime.audit_service.record(
        actor=actor,
        action="template.create",
        target_type="template",
        target_id=detail.id,
        trace_id=trace_id,
    )
    return detail


@router.post("/{template_id}/versions", response_model=TemplateVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    template_id: str,
    layout_config_path: str | None = Form(default=None),
    render_policy_json: str = Form(default="{}"),
    template: UploadFile = File(...),
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateVersionResponse:
    temp_path = await _save_template_upload_to_temp(template, runtime)
    render_policy = _parse_render_policy(render_policy_json)
    try:
        version = runtime.template_read_service.create_template_version(
            template_id,
            source_path=temp_path,
            source_filename=template.filename or f"{template_id}.docx",
            layout_config_path=layout_config_path,
            render_policy=render_policy,
        )
        runtime.audit_service.record(
            actor=actor,
            action="template.version_create",
            target_type="template",
            target_id=f"{template_id}@{version.version}",
            trace_id=trace_id,
        )
        return version
    except RuntimeError as exc:
        temp_path.unlink(missing_ok=True)
        raise _template_versioning_unavailable_http_exception(exc) from exc
    except FileNotFoundError as exc:
        temp_path.unlink(missing_ok=True)
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        temp_path.unlink(missing_ok=True)
        raise bad_request_http_exception(exc) from exc


@router.get("/{template_id}/versions", response_model=TemplateVersionListResponse)
def list_template_versions(
    template_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> TemplateVersionListResponse:
    try:
        items = runtime.template_read_service.list_template_versions(template_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    return TemplateVersionListResponse(template_id=template_id, items=items)


@router.post("/{template_id}/versions/{version}/publish", response_model=TemplateVersionResponse)
def publish_template_version(
    template_id: str,
    version: int,
    payload: TemplateVersionPublishRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateVersionResponse:
    try:
        return runtime.template_read_service.publish_template_version(
            template_id,
            version,
            make_default=payload.make_default,
            publish_reason=payload.publish_reason,
            verification_job_id=payload.verification_job_id,
            verification_note=payload.verification_note,
            actor=actor,
            trace_id=trace_id,
        )
    except RuntimeError as exc:
        raise _template_versioning_unavailable_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{template_id}/versions/{version}/set-default", response_model=TemplateVersionResponse)
def set_default_template_version(
    template_id: str,
    version: int,
    payload: TemplateVersionDefaultRequest,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateVersionResponse:
    try:
        return runtime.template_read_service.set_default_template_version(
            template_id,
            version,
            set_default_reason=payload.set_default_reason,
            actor=actor,
            trace_id=trace_id,
        )
    except RuntimeError as exc:
        raise _template_versioning_unavailable_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.post("/{template_id}/versions/{version}/disable", response_model=TemplateVersionResponse)
def disable_template_version(
    template_id: str,
    version: int,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateVersionResponse:
    try:
        return runtime.template_read_service.disable_template_version(
            template_id,
            version,
            actor=actor,
            trace_id=trace_id,
        )
    except RuntimeError as exc:
        raise _template_versioning_unavailable_http_exception(exc) from exc
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc


@router.get("/{template_id}", response_model=TemplateDetailResponse)
def get_template_detail(
    template_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> TemplateDetailResponse:
    template = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板不存在: {template_id}",
        )
    return template


@router.get("/{template_id}/download", name="download_template")
def download_template(
    template_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> FileResponse:
    detail = runtime.template_read_service.get_template_detail(template_id, url_for=None)
    if detail is None or not detail.template.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板文件不存在: {template_id}",
        )
    path = runtime.template_read_service.get_template_path(template_id)
    assert path is not None
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@router.patch("/{template_id}", response_model=TemplateDetailResponse)
def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
    request: Request,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateDetailResponse:
    try:
        runtime.template_read_service.update_template_metadata(
            template_id,
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            layout_config_path=payload.layout_config_path,
            render_policy=payload.render_policy,
        )
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc

    detail = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板不存在: {template_id}",
        )
    runtime.audit_service.record(
        actor=actor,
        action="template.update",
        target_type="template",
        target_id=template_id,
        trace_id=trace_id,
    )
    return detail


@router.put("/{template_id}/file", response_model=TemplateDetailResponse)
async def replace_template_file(
    template_id: str,
    request: Request,
    template: UploadFile = File(...),
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateDetailResponse:
    temp_path = await _save_template_upload_to_temp(template, runtime)
    try:
        runtime.template_read_service.replace_template_file(
            template_id,
            source_path=temp_path,
            source_filename=template.filename or f"{template_id}.docx",
        )
    except FileNotFoundError as exc:
        temp_path.unlink(missing_ok=True)
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        temp_path.unlink(missing_ok=True)
        raise bad_request_http_exception(exc) from exc

    detail = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    assert detail is not None
    runtime.audit_service.record(
        actor=actor,
        action="template.replace_file",
        target_type="template",
        target_id=template_id,
        trace_id=trace_id,
    )
    return detail


@router.patch("/{template_id}/default", response_model=TemplateDetailResponse)
def set_default_template(
    template_id: str,
    request: Request,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateDetailResponse:
    try:
        runtime.template_read_service.set_default_template(template_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc

    detail = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    assert detail is not None
    runtime.audit_service.record(
        actor=actor,
        action="template.set_default_legacy",
        target_type="template",
        target_id=template_id,
        trace_id=trace_id,
    )
    return detail


@router.delete("/{template_id}", response_model=TemplateDeleteResponse)
def delete_template(
    template_id: str,
    actor: ActorContext = Depends(require_admin_actor),
    runtime: AppRuntime = Depends(get_runtime),
    trace_id: str = Depends(get_trace_id),
) -> TemplateDeleteResponse:
    try:
        runtime.template_read_service.delete_template(template_id)
    except FileNotFoundError as exc:
        raise not_found_http_exception(exc) from exc
    except ValueError as exc:
        raise bad_request_http_exception(exc) from exc
    runtime.audit_service.record(
        actor=actor,
        action="template.delete",
        target_type="template",
        target_id=template_id,
        trace_id=trace_id,
    )
    return TemplateDeleteResponse(id=template_id, deleted=True)
