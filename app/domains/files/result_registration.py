"""结果凭据、预览候选和文件生命周期的纯规则；在 adapter 文件锁内调用。"""

from datetime import datetime, timezone
import json
from pathlib import PurePosixPath
import re
from typing import Any

from app.domains.files.models import DocumentFileRecord, WORD_PREVIEW_FILE_TYPES
from app.domains.resources.models import utc_now


REVIEW_SOURCE_FIELDS = (
    "tenant_id", "company_id", "job_id", "file_type", "mime_type", "storage_provider",
    "bucket", "object_key", "size_bytes", "checksum_sha256", "etag", "status", "expires_at", "metadata",
)


def review_source_descriptor(file: DocumentFileRecord) -> dict[str, Any]:
    """固定来源集合不包含显示名、时间戳和服务端观察计数。"""
    descriptor = file.model_dump(mode="json", include=set(REVIEW_SOURCE_FIELDS))
    if file.deletion_claim is not None:
        descriptor["deletion_claim"] = file.deletion_claim
    if file.expires_at is not None:
        expiry = file.expires_at if file.expires_at.tzinfo is not None else file.expires_at.replace(tzinfo=timezone.utc)
        descriptor["expires_at"] = expiry.astimezone(timezone.utc).isoformat()
    return descriptor


def revised_file(existing: DocumentFileRecord, updated: DocumentFileRecord) -> DocumentFileRecord:
    """仅锁内现值拥有计数；描述改回旧值也必须产生新的观察身份。"""
    if updated.id != existing.id:
        raise ValueError("文件更新不允许改变 id。")
    changed = (
        "generated_word" in {existing.file_type, updated.file_type}
        and json.dumps(review_source_descriptor(existing), sort_keys=True, ensure_ascii=False, allow_nan=False)
        != json.dumps(review_source_descriptor(updated), sort_keys=True, ensure_ascii=False, allow_nan=False)
    )
    return updated.model_copy(update={"review_source_revision": existing.review_source_revision + int(changed)})


def is_result_candidate(file: DocumentFileRecord) -> bool:
    return (file.file_type == "generated_word"
            and type(file.metadata.get("document_job_result_protocol")) is int
            and file.metadata["document_job_result_protocol"] == 1)


def is_preview_candidate(file: DocumentFileRecord) -> bool:
    """仅本协议的内部预览候选可按保留期回收，普通待上传文件语义保持。"""
    return (file.file_type in WORD_PREVIEW_FILE_TYPES
            and type(file.metadata.get("word_preview_artifact_protocol")) is int
            and file.metadata["word_preview_artifact_protocol"] == 1)


def ensure_result_descriptor_matches(existing: DocumentFileRecord, descriptor: DocumentFileRecord) -> None:
    """共用不可变身份与物化 etag 合同，生命周期仍由实际物化入口判断。"""
    # etag 由对象写入返回，pending 尚无此字段；其余身份和 evidence 必须逐项保留。
    excluded = {"status", "etag", "updated_at", "review_source_revision"}
    if existing.model_dump(exclude=excluded) != descriptor.model_dump(exclude=excluded):
        raise ValueError("结果候选与选定凭据的不可变描述冲突。")
    if descriptor.status != "uploaded":
        raise ValueError("物化必须使用已选定的完整上传描述。")
    if existing.status == "uploaded" and existing.etag != descriptor.etag:
        raise ValueError("已物化结果的 etag 与凭据冲突。")


def materialized_file(existing: DocumentFileRecord, descriptor: DocumentFileRecord) -> DocumentFileRecord:
    """实际物化时检查生命周期，保留到期/删除失败与不可复活规则。"""
    ensure_result_descriptor_matches(existing, descriptor)
    expires_at = existing.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if existing.deletion_claim is not None or existing.status not in {"pending_upload", "uploaded"} or (expires_at is not None and expires_at <= utc_now()):
        raise ValueError("结果候选已过期或删除，不能物化。")
    if existing.status == "uploaded":
        return existing
    if not is_result_candidate(existing):
        raise ValueError("只有结果协议候选允许物化。")
    return revised_file(existing, existing.model_copy(update={"status": "uploaded", "etag": descriptor.etag, "updated_at": utc_now()}))


def expired_file(existing: DocumentFileRecord, *, now: datetime) -> DocumentFileRecord:
    expires_at = existing.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    expirable_pending = existing.status == "pending_upload" and (
        is_result_candidate(existing) or is_preview_candidate(existing)
    )
    if expires_at is not None and expires_at <= now and (existing.status == "uploaded" or expirable_pending):
        return revised_file(existing, existing.model_copy(update={"status": "expired", "updated_at": now}))
    return existing


def patched_file(existing: DocumentFileRecord, patch: dict[str, Any]) -> DocumentFileRecord:
    if is_preview_candidate(existing) and patch.get("status") == "uploaded":
        expires_at = existing.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at is None or expires_at <= utc_now():
            raise ValueError("预览候选已过期，不能确认上传。")
    if "deletion_claim" in patch and patch["deletion_claim"] != existing.deletion_claim:
        raise ValueError("删除预留只能由文件生命周期端口维护。")
    if "review_source_revision" in patch:
        raise ValueError("复核来源序号由文件仓储维护，不能指定。")
    if patch.get("id", existing.id) != existing.id:
        raise ValueError("文件更新不允许改变 id。")
    if existing.status in {"expired", "deleted"} and patch.get("status", existing.status) not in {existing.status, "deleted"}:
        raise ValueError("过期或已删除文件不能恢复可用状态。")
    return revised_file(existing, DocumentFileRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python")))


def ensure_file_mutation_allowed(existing: DocumentFileRecord, updated: DocumentFileRecord, *, protected: bool) -> None:
    """发布保护与删除预留在实际文件写入序列化点判断。"""
    if existing.deletion_claim is not None and updated != existing:
        raise ValueError("文件已预留删除，不能修改或恢复。")
    if protected and updated != existing:
        raise ValueError("文件被不可变发布记录引用，不能修改。")


def reserved_file_deletion(existing: DocumentFileRecord, *, claim_id: str, now: datetime) -> DocumentFileRecord:
    if not claim_id or existing.status not in {"uploaded", "expired"}:
        raise ValueError("当前文件状态不能预留删除。")
    if existing.deletion_claim is not None:
        if existing.deletion_claim == claim_id:
            return existing
        raise ValueError("文件已由其他删除请求预留。")
    return existing.model_copy(update={"deletion_claim": claim_id, "updated_at": now})


def finished_file_deletion(existing: DocumentFileRecord, *, claim_id: str, now: datetime) -> DocumentFileRecord:
    if existing.deletion_claim != claim_id:
        raise ValueError("删除收尾与当前预留不一致。")
    return revised_file(existing, existing.model_copy(update={"status": "deleted", "updated_at": now}))


def ensure_new_file_identity(file: DocumentFileRecord) -> None:
    """仅新建和重绑执行 canonical 准入，file_id 必须占据唯一固定路径槽。"""
    parts = PurePosixPath(file.object_key).parts
    if (not parts or PurePosixPath(file.object_key).is_absolute() or ".." in parts
            or str(PurePosixPath(file.object_key)) != file.object_key
            or any(re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None for value in parts)
            or file.id in {".", ".."}):
        raise ValueError("新文件对象路径必须是规范且安全的独立身份。")
    source = len(parts) >= 4 and parts[-4] == "document-files" and parts[-2] == file.id
    generated = any(len(parts) >= count and parts[-count] == "document-jobs"
        and parts[-count + 4] == file.id and parts[-count + 3] == file.file_type
        for count in (6, 7))
    if not (source or generated):
        raise ValueError("新文件对象路径缺少固定位置的独立 file_id。")
    root_position = len(parts) - (4 if source else next(count for count in (6, 7)
        if len(parts) >= count and parts[-count] == "document-jobs"
        and parts[-count + 4] == file.id and parts[-count + 3] == file.file_type))
    if file.storage_provider != "s3" and root_position != 0:
        raise ValueError("本地文件对象路径不接受额外前缀。")


def retained_file_expiry(file: DocumentFileRecord, repository: Any) -> datetime | None:
    """只在权威保护成立时忽略普通 expiry，原文件对象始终不变。"""
    if file.status == "uploaded" and file.deletion_claim is None and repository.is_document_file_protected(file.id):
        return None
    expiry = file.expires_at
    return expiry.replace(tzinfo=timezone.utc) if expiry is not None and expiry.tzinfo is None else expiry


def file_lifecycle_unavailable(file: DocumentFileRecord, repository: Any, *, now: datetime) -> bool:
    expiry = retained_file_expiry(file, repository)
    return file.status != "uploaded" or file.deletion_claim is not None or expiry is not None and expiry <= now
