"""结果候选的不可变描述与文件生命周期规则；在 adapter 的文件锁内调用。"""

from datetime import datetime, timezone
from typing import Any

from app.domains.files.models import DocumentFileRecord
from app.domains.resources.models import utc_now


def is_result_candidate(file: DocumentFileRecord) -> bool:
    return (file.file_type == "generated_word"
            and type(file.metadata.get("document_job_result_protocol")) is int
            and file.metadata["document_job_result_protocol"] == 1)


def materialized_file(existing: DocumentFileRecord, descriptor: DocumentFileRecord) -> DocumentFileRecord:
    # etag 由对象写入返回，pending 尚无此字段；其余身份和 evidence 必须逐项保留。
    excluded = {"status", "etag", "updated_at"}
    if existing.model_dump(exclude=excluded) != descriptor.model_dump(exclude=excluded):
        raise ValueError("结果候选与选定凭据的不可变描述冲突。")
    if descriptor.status != "uploaded":
        raise ValueError("物化必须使用已选定的完整上传描述。")
    expires_at = existing.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if existing.status not in {"pending_upload", "uploaded"} or (expires_at is not None and expires_at <= utc_now()):
        raise ValueError("结果候选已过期或删除，不能物化。")
    if existing.status == "uploaded":
        if existing.etag != descriptor.etag:
            raise ValueError("已物化结果的 etag 与凭据冲突。")
        return existing
    if not is_result_candidate(existing):
        raise ValueError("只有结果协议候选允许物化。")
    return existing.model_copy(update={"status": "uploaded", "etag": descriptor.etag, "updated_at": utc_now()})


def expired_file(existing: DocumentFileRecord, *, now: datetime) -> DocumentFileRecord:
    expires_at = existing.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (expires_at is not None and expires_at <= now
            and (existing.status == "uploaded" or (existing.status == "pending_upload" and is_result_candidate(existing)))):
        return existing.model_copy(update={"status": "expired", "updated_at": now})
    return existing


def patched_file(existing: DocumentFileRecord, patch: dict[str, Any]) -> DocumentFileRecord:
    if existing.status in {"expired", "deleted"} and patch.get("status", existing.status) not in {existing.status, "deleted"}:
        raise ValueError("过期或已删除文件不能恢复可用状态。")
    return DocumentFileRecord.model_validate(existing.model_copy(update=patch).model_dump(mode="python"))
