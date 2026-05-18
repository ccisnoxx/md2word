from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_runtime, require_admin_access
from app.core.runtime import AppRuntime
from app.schemas.api_v1 import TemplateDetailResponse, TemplateListResponse


router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
def list_templates(
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> TemplateListResponse:
    items = runtime.template_read_service.list_templates(url_for=request.url_for)
    return TemplateListResponse(items=items)


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


@router.patch("/{template_id}/default", response_model=TemplateDetailResponse, dependencies=[Depends(require_admin_access)])
def set_default_template(
    template_id: str,
    request: Request,
    runtime: AppRuntime = Depends(get_runtime),
) -> TemplateDetailResponse:
    try:
        runtime.template_read_service.set_default_template(template_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    detail = runtime.template_read_service.get_template_detail(template_id, url_for=request.url_for)
    assert detail is not None
    return detail
