from __future__ import annotations

# app/domains/resources/service.py: 统一资源版本发布、默认指针和解析状态机。

from typing import Any

from app.domains.resources.models import (
    ResolvedResourceVersion,
    ResourceType,
    ResourceVersionRecord,
    ResourceVersionStatus,
    utc_now,
)
from app.domains.resources.repository import ResourceVersionRepositoryProtocol


class ResourceVersionService:
    """封装模板、术语和翻译配置共用的资源版本状态规则。"""

    def __init__(self, repository: ResourceVersionRepositoryProtocol) -> None:
        self.repository = repository

    def create_or_update_draft(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
        snapshot_hash: str,
        payload_ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ResourceVersionRecord:
        existing = self.repository.get_resource_version(resource_type, resource_id, version)
        if existing is not None and existing.status != ResourceVersionStatus.DRAFT:
            raise ValueError("已发布或已关闭的资源版本不可通过草稿路径修改。")
        now = utc_now()
        record = ResourceVersionRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            version=version,
            status=ResourceVersionStatus.DRAFT,
            snapshot_hash=snapshot_hash,
            payload_ref=payload_ref,
            payload=payload,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        return self.repository.save_resource_version(record)

    def create_draft(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
        snapshot_hash: str,
        payload_ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ResourceVersionRecord:
        """创建不可变的新草稿版本，拒绝覆盖任何同版本记录。"""

        if self.repository.get_resource_version(resource_type, resource_id, version) is not None:
            raise ValueError(f"资源版本已存在: {resource_type}/{resource_id}@{version}")
        now = utc_now()
        return self.repository.create_resource_version(
            ResourceVersionRecord(
                resource_type=resource_type,
                resource_id=resource_id,
                version=version,
                status=ResourceVersionStatus.DRAFT,
                snapshot_hash=snapshot_hash,
                payload_ref=payload_ref,
                payload=payload,
                created_at=now,
                updated_at=now,
            )
        )

    def allocate_next_version(self, resource_type: ResourceType, resource_id: str, minimum_next: int) -> int:
        """通过持久化层原子分配不复用的整数版本。"""

        if minimum_next < 1:
            raise ValueError("minimum_next 必须大于 0。")
        return self.repository.allocate_next_version(resource_type, resource_id, minimum_next)

    def publish(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
        *,
        make_default: bool = False,
    ) -> ResourceVersionRecord:
        record = self._require_version(resource_type, resource_id, version)
        if record.status != ResourceVersionStatus.DRAFT:
            raise ValueError("只有 draft 资源版本可以发布。")
        published = record.model_copy(update={"status": ResourceVersionStatus.PUBLISHED, "updated_at": utc_now()})
        saved = self.repository.save_resource_version(published)
        if make_default:
            self.repository.set_default_resource_version(resource_type, resource_id, version)
        return saved

    def set_default(self, resource_type: ResourceType, resource_id: str, version: str) -> ResolvedResourceVersion:
        record = self._require_version(resource_type, resource_id, version)
        if record.status != ResourceVersionStatus.PUBLISHED:
            raise ValueError("默认资源版本只能指向 published 版本。")
        self.repository.set_default_resource_version(resource_type, resource_id, version)
        return self._to_resolved(record)

    def rollback_default(self, resource_type: ResourceType, resource_id: str, version: str) -> ResolvedResourceVersion:
        """回滚只切换默认指针，不修改任何历史发布版本。"""

        return self.set_default(resource_type, resource_id, version)

    def disable(self, resource_type: ResourceType, resource_id: str, version: str) -> ResourceVersionRecord:
        record = self._require_version(resource_type, resource_id, version)
        self._ensure_not_default(record, "默认资源版本不能直接禁用，请先切换默认指针。")
        if record.status == ResourceVersionStatus.DISABLED:
            return record
        if record.status == ResourceVersionStatus.SUPERSEDED:
            raise ValueError("superseded 资源版本不能再切换为 disabled。")
        return self.repository.save_resource_version(
            record.model_copy(update={"status": ResourceVersionStatus.DISABLED, "updated_at": utc_now()})
        )

    def mark_superseded(self, resource_type: ResourceType, resource_id: str, version: str) -> ResourceVersionRecord:
        record = self._require_version(resource_type, resource_id, version)
        self._ensure_not_default(record, "默认资源版本不能直接标记为 superseded，请先切换默认指针。")
        if record.status == ResourceVersionStatus.SUPERSEDED:
            return record
        if record.status != ResourceVersionStatus.PUBLISHED:
            raise ValueError("只有 published 资源版本可以标记为 superseded。")
        return self.repository.save_resource_version(
            record.model_copy(update={"status": ResourceVersionStatus.SUPERSEDED, "updated_at": utc_now()})
        )

    def resolve_default(self, resource_type: ResourceType, resource_id: str) -> ResolvedResourceVersion:
        record = self.repository.get_default_resource_version(resource_type, resource_id)
        if record is None:
            raise FileNotFoundError(f"默认资源版本不存在: {resource_type}/{resource_id}")
        if record.status != ResourceVersionStatus.PUBLISHED:
            raise ValueError("默认资源版本指针指向了非 published 版本。")
        return self._to_resolved(record)

    def resolve_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
        *,
        allow_draft: bool = False,
    ) -> ResolvedResourceVersion:
        record = self._require_version(resource_type, resource_id, version)
        allowed_statuses = {ResourceVersionStatus.PUBLISHED}
        if allow_draft:
            allowed_statuses.add(ResourceVersionStatus.DRAFT)
        if record.status not in allowed_statuses:
            raise ValueError("只能解析 published 资源版本。")
        return self._to_resolved(record)

    def _require_version(self, resource_type: ResourceType, resource_id: str, version: str) -> ResourceVersionRecord:
        record = self.repository.get_resource_version(resource_type, resource_id, version)
        if record is None:
            raise FileNotFoundError(f"资源版本不存在: {resource_type}/{resource_id}@{version}")
        return record

    def _ensure_not_default(self, record: ResourceVersionRecord, message: str) -> None:
        default_record = self.repository.get_default_resource_version(record.resource_type, record.resource_id)
        if default_record is not None and default_record.version == record.version:
            raise ValueError(message)

    def _to_resolved(self, record: ResourceVersionRecord) -> ResolvedResourceVersion:
        return ResolvedResourceVersion(
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            version=record.version,
            status=record.status.value,
            snapshot_hash=record.snapshot_hash,
            payload_ref=record.payload_ref,
        )
