"""HTTP routes for personal saved views on operations pages."""

from __future__ import annotations

# File: app/domains/saved_views/router.py
# Purpose: Expose personal saved-view APIs for operations workbench pages.

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_runtime, require_current_user
from app.core.runtime import AppRuntime
from app.domains.saved_views.models import SavedViewPageKey
from app.domains.saved_views.schemas import (
    SavedViewCreateRequest,
    SavedViewListResponse,
    SavedViewReorderRequest,
    SavedViewResponse,
    SavedViewUpdateRequest,
)
from app.services.auth.models import AuthenticatedUser


router = APIRouter(prefix="/saved-views", tags=["saved-views"])


@router.get("", response_model=SavedViewListResponse)
def list_saved_views(
    page_key: SavedViewPageKey = Query(...),
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> SavedViewListResponse:
    return SavedViewListResponse(
        items=[
            _build_saved_view_response(record)
            for record in runtime.saved_view_service.list_views(user=user, page_key=page_key)
        ]
    )


@router.post("", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedViewCreateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> SavedViewResponse:
    record = runtime.saved_view_service.create_view(
        user=user,
        page_key=payload.page_key,
        name=payload.name,
        filters=payload.filters,
        sort=payload.sort,
        is_default=payload.is_default,
        position=payload.position,
    )
    return _build_saved_view_response(record)


@router.patch("/{view_id}", response_model=SavedViewResponse)
def update_saved_view(
    view_id: str,
    payload: SavedViewUpdateRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> SavedViewResponse:
    record = runtime.saved_view_service.update_view(
        user=user,
        view_id=view_id,
        name=payload.name,
        filters=payload.filters,
        sort=payload.sort,
        is_default=payload.is_default,
        position=payload.position,
    )
    return _build_saved_view_response(record)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_view(
    view_id: str,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> Response:
    runtime.saved_view_service.delete_view(user=user, view_id=view_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reorder", response_model=SavedViewListResponse)
def reorder_saved_views(
    payload: SavedViewReorderRequest,
    runtime: AppRuntime = Depends(get_runtime),
    user: AuthenticatedUser = Depends(require_current_user),
) -> SavedViewListResponse:
    return SavedViewListResponse(
        items=[
            _build_saved_view_response(record)
            for record in runtime.saved_view_service.reorder_views(
                user=user,
                page_key=payload.page_key,
                view_ids=payload.view_ids,
            )
        ]
    )


def _build_saved_view_response(record) -> SavedViewResponse:
    return SavedViewResponse.model_validate(record.model_dump(mode="python"))
