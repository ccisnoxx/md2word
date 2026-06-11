# File: app/domains/files/library_search.py
# Purpose: Provide read-only, path-safe search over document_files metadata.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.domains.files.models import DocumentFileRecord
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.files.service import RETENTION_DELETE_SUPPORTED_LOCAL_PROVIDERS
from app.domains.resources.models import utc_now


FileLibrarySort = Literal[
    "created_at_desc",
    "created_at_asc",
    "updated_at_desc",
    "updated_at_asc",
    "expires_at_desc",
    "expires_at_asc",
    "size_bytes_desc",
    "size_bytes_asc",
]


@dataclass(frozen=True, slots=True)
class FileLibrarySearchQuery:
    """封装 document_files 只读搜索筛选、排序和分页参数。"""

    page: int = 1
    page_size: int = 50
    sort: FileLibrarySort = "created_at_desc"
    q: str | None = None
    file_type: str | None = None
    status: str | None = None
    storage_provider: str | None = None
    job_id: str | None = None
    created_by: str | None = None
    expires_from: datetime | None = None
    expires_to: datetime | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class FileLibrarySearchItem:
    """安全文件库行；不包含 object_key、bucket、checksum、etag 或 metadata。"""

    file_id: str
    job_id: str | None
    file_type: str
    storage_provider: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    expires_at: datetime | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    expired: bool
    physical_delete_candidate: bool

    def to_dict(self) -> dict[str, object]:
        """转换为 API schema 可校验的安全字典。"""

        return {
            "file_id": self.file_id,
            "job_id": self.job_id,
            "file_type": self.file_type,
            "storage_provider": self.storage_provider,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "expires_at": self.expires_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expired": self.expired,
            "physical_delete_candidate": self.physical_delete_candidate,
        }


@dataclass(frozen=True, slots=True)
class FileLibrarySearchPage:
    """保存一次文件库搜索分页结果。"""

    generated_at: datetime
    page: int
    page_size: int
    total: int
    sort: FileLibrarySort
    items: list[FileLibrarySearchItem]
    filters: dict[str, str]


class FileLibrarySearchService:
    """基于 document_files repository 提供无副作用 metadata 搜索。"""

    def __init__(self, repository: DocumentFileRepositoryProtocol) -> None:
        self.repository = repository

    def search(self, query: FileLibrarySearchQuery, *, now: datetime | None = None) -> FileLibrarySearchPage:
        """执行内存筛选、排序、分页和安全字段投影。"""

        generated_at = now or utc_now()
        records = [
            record
            for record in self.repository.list_document_files()
            if self._matches_query(record, query)
        ]
        records.sort(key=lambda record: self._sort_key(record, query.sort), reverse=query.sort.endswith("_desc"))
        total = len(records)
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        return FileLibrarySearchPage(
            generated_at=generated_at,
            page=query.page,
            page_size=query.page_size,
            total=total,
            sort=query.sort,
            items=[self._build_item(record, now=generated_at) for record in records[start:end]],
            filters=_build_filter_summary(query),
        )

    def _matches_query(self, record: DocumentFileRecord, query: FileLibrarySearchQuery) -> bool:
        """判断文件 metadata 是否满足所有筛选条件。"""

        if query.file_type is not None and record.file_type != query.file_type:
            return False
        if query.status is not None and record.status != query.status:
            return False
        if query.storage_provider is not None and record.storage_provider != query.storage_provider:
            return False
        if query.job_id is not None and record.job_id != query.job_id:
            return False
        if query.created_by is not None and record.created_by != query.created_by:
            return False
        if not _matches_optional_datetime(record.expires_at, query.expires_from, query.expires_to):
            return False
        if not _matches_optional_datetime(record.created_at, query.created_from, query.created_to):
            return False
        normalized_query = _normalize_optional_text(query.q)
        if normalized_query is not None and normalized_query not in self._search_blob(record):
            return False
        return True

    def _search_blob(self, record: DocumentFileRecord) -> str:
        """拼接安全搜索字段；不包含 object_key、bucket、checksum、etag 或 metadata。"""

        values = [
            record.id,
            record.job_id,
            record.file_type,
            record.storage_provider,
            record.original_filename,
            record.mime_type,
            record.status,
            record.created_by,
        ]
        return "\n".join(value for value in values if value is not None).lower()

    def _sort_key(self, record: DocumentFileRecord, sort: FileLibrarySort) -> tuple[object, str]:
        """返回稳定排序 key，缺失 expires_at 的记录排在同方向末尾附近。"""

        if sort.startswith("updated_at_"):
            return (_comparable_datetime(record.updated_at), record.id)
        if sort.startswith("expires_at_"):
            missing_expires_at = datetime.min if sort.endswith("_desc") else datetime.max
            fallback = missing_expires_at.replace(tzinfo=timezone.utc)
            return (_comparable_datetime(record.expires_at) if record.expires_at is not None else fallback, record.id)
        if sort.startswith("size_bytes_"):
            return (record.size_bytes, record.id)
        return (_comparable_datetime(record.created_at), record.id)

    def _build_item(self, record: DocumentFileRecord, *, now: datetime) -> FileLibrarySearchItem:
        """把完整 metadata 记录投影为安全文件库行。"""

        expired = record.expires_at is not None and _comparable_datetime(record.expires_at) <= _comparable_datetime(now)
        physical_delete_candidate = (
            record.status == "expired"
            and expired
            and record.storage_provider in RETENTION_DELETE_SUPPORTED_LOCAL_PROVIDERS
            and bool(record.object_key.strip())
        )
        return FileLibrarySearchItem(
            file_id=record.id,
            job_id=record.job_id,
            file_type=record.file_type,
            storage_provider=record.storage_provider,
            original_filename=record.original_filename,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            status=record.status,
            expires_at=record.expires_at,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expired=expired,
            physical_delete_candidate=physical_delete_candidate,
        )


def _build_filter_summary(query: FileLibrarySearchQuery) -> dict[str, str]:
    """输出已生效筛选摘要，便于前端和审计排查。"""

    filters: dict[str, str] = {}
    for key in ("q", "file_type", "status", "storage_provider", "job_id", "created_by"):
        value = getattr(query, key)
        normalized = _normalize_optional_text(value)
        if normalized is not None:
            filters[key] = normalized
    for key in ("expires_from", "expires_to", "created_from", "created_to"):
        value = getattr(query, key)
        if isinstance(value, datetime):
            filters[key] = value.isoformat()
    return filters


def _matches_optional_datetime(value: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    """按可选起止时间过滤；字段缺失时不匹配日期范围查询。"""

    if start is None and end is None:
        return True
    if value is None:
        return False
    comparable = _comparable_datetime(value)
    if start is not None and comparable < _comparable_datetime(start):
        return False
    if end is not None and comparable > _comparable_datetime(end):
        return False
    return True


def _normalize_optional_text(value: str | None) -> str | None:
    """清理可选文本筛选条件，空字符串视为未传。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _comparable_datetime(value: datetime) -> datetime:
    """把 naive datetime 视为 UTC，避免比较时区不一致时报错。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
