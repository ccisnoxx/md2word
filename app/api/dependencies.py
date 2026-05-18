from __future__ import annotations

import hashlib
import json
import secrets

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.runtime import AppRuntime
from app.core.mineru_callback import validate_mineru_result_url


def get_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def get_trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", ""))


def require_jobs_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    mode = runtime.settings.jobs_access_mode
    if mode == "open":
        return
    if mode == "token":
        if not runtime.settings.jobs_access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JOBS_ACCESS_TOKEN 未配置，jobs token 模式不可用。",
            )
        if x_jobs_token != runtime.settings.jobs_access_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="jobs token 校验失败。",
            )
        return
    require_admin_access(runtime, x_admin_token)


def require_job_ops_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_jobs_token: str | None = Header(default=None, alias="X-Jobs-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    # 当前按用户要求复用普通 jobs 访问口径；后续若要收紧，只需在这里切回 admin/token 策略。
    require_jobs_access(runtime, x_jobs_token, x_admin_token)


def require_admin_access(
    runtime: AppRuntime = Depends(get_runtime),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    if not runtime.settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_TOKEN 未配置，管理接口不可用。",
        )
    if x_admin_token != runtime.settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin token 校验失败。",
        )


def verify_mineru_callback_identity(request: Request, runtime: AppRuntime) -> None:
    settings = runtime.settings
    if settings.public_deployment_mode == "internal":
        return
    if not settings.mineru_callback_token:
        raise HTTPException(status_code=503, detail="MINERU_CALLBACK_TOKEN 未配置，公开 callback 已关闭")

    query_token_name = settings.mineru_callback_token_query_name or "callback_token"
    token = request.headers.get("X-MinerU-Callback-Token") or request.query_params.get(query_token_name)
    if not secrets.compare_digest(str(token or ""), settings.mineru_callback_token):
        raise HTTPException(status_code=403, detail="MinerU callback 鉴权失败")


def verify_mineru_callback_request(payload: dict) -> dict:
    normalized = normalize_mineru_callback_payload(payload)
    if not normalized.get("batch_id") and not normalized.get("data_id"):
        raise HTTPException(status_code=400, detail="回调 payload 缺少 batch_id/data_id")
    return normalized


def verify_mineru_callback_result_url(payload: dict, runtime: AppRuntime) -> None:
    full_zip_url = payload.get("full_zip_url")
    if full_zip_url is None:
        return
    try:
        validate_mineru_result_url(str(full_zip_url), runtime.settings.allowed_mineru_result_hosts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def normalize_mineru_callback_payload(payload: dict) -> dict:
    content_raw = payload.get("content")
    content_dict = _parse_mineru_callback_content(content_raw)
    if content_dict is None and isinstance(payload.get("data"), dict):
        content_dict = payload.get("data")

    normalized = dict(payload)
    if not isinstance(content_dict, dict):
        return normalized

    extract_results = content_dict.get("extract_result")
    matched_item: dict | None = None
    if isinstance(extract_results, list) and extract_results:
        first = extract_results[0]
        if isinstance(first, dict):
            matched_item = first

    batch_id = payload.get("batch_id") or content_dict.get("batch_id")
    data_id = payload.get("data_id") or content_dict.get("data_id")
    state = payload.get("state") or content_dict.get("state")
    full_zip_url = payload.get("full_zip_url") or content_dict.get("full_zip_url")

    if matched_item is not None:
        data_id = data_id or matched_item.get("data_id")
        state = state or matched_item.get("state")
        full_zip_url = (
            full_zip_url
            or matched_item.get("full_zip_url")
            or matched_item.get("full_zip_oss_url")
            or matched_item.get("result_zip_url")
        )

    normalized["data"] = content_dict
    if batch_id is not None:
        normalized["batch_id"] = batch_id
    if data_id is not None:
        normalized["data_id"] = data_id
    if state is not None:
        normalized["state"] = state
    if full_zip_url is not None:
        normalized["full_zip_url"] = full_zip_url
    return normalized


def verify_mineru_callback_checksum_for_job(payload: dict, job, runtime: AppRuntime) -> None:
    checksum = payload.get("checksum")
    content = payload.get("content")
    if checksum is None:
        return
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="回调 payload content 缺失，无法校验 checksum")
    uid = payload.get("uid")
    if uid is None and isinstance(payload.get("data"), dict):
        uid = payload["data"].get("uid")
    if uid is None:
        uid = runtime.settings.mineru_uid
    _verify_mineru_callback_checksum(checksum, str(uid or ""), content, getattr(job, "mineru_callback_seed", None))


def _verify_mineru_callback_checksum(checksum: str, uid: str, content: str, seed: str | None) -> None:
    if not isinstance(checksum, str) or not checksum.strip():
        raise HTTPException(status_code=400, detail="回调 payload checksum 无效")
    if not isinstance(seed, str) or not seed.strip():
        raise HTTPException(status_code=409, detail="当前任务缺少 callback seed，无法校验 MinerU callback checksum")
    expected = hashlib.sha256(f"{uid}{seed}{content}".encode("utf-8")).hexdigest()
    if not secrets.compare_digest(checksum.strip().lower(), expected.lower()):
        raise HTTPException(status_code=403, detail="MinerU callback checksum 校验失败")


def _parse_mineru_callback_content(content: object) -> dict | None:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"回调 payload content 不是合法 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="回调 payload content 必须是 JSON 对象")
    return parsed
