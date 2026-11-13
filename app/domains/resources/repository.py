from __future__ import annotations

# app/domains/resources/repository.py: 定义 resource version domain 依赖的持久化端口。

from typing import Protocol

from app.domains.audit.models import AuditEvent
from app.domains.resources.models import (
    ResourceDefaultPointer,
    ResourceType,
    ResourceVersionRecord,
    ResourceVersionStatus,
)


class ResourceDefaultCommitUnknownError(RuntimeError):
    """默认指针事务已进入提交阶段，无法确认数据库是否已提交。"""


class ResourceVersionRepositoryProtocol(Protocol):
    """模板、术语和翻译配置共用的资源版本持久化合同。"""

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord: ...
    def update_resource_version_if_current(
        self,
        record: ResourceVersionRecord,
        *,
        expected_snapshot_hash: str,
        expected_status: ResourceVersionStatus | None = None,
    ) -> ResourceVersionRecord | None: ...
    def create_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord: ...
    def allocate_next_version(self, resource_type: ResourceType, resource_id: str, minimum_next: int) -> int: ...
    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None: ...
    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]: ...
    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None: ...
    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None: ...
    def get_default_resource_pointer(self, resource_type: ResourceType, resource_id: str) -> ResourceDefaultPointer | None: ...
    def switch_default_resource_version(
        self,
        record: ResourceVersionRecord,
        *,
        expected_pointer: ResourceDefaultPointer | None,
        audit_event: AuditEvent | None = None,
    ) -> ResourceVersionRecord | None: ...
    def disable_template_version_if_not_default(self, template_id: str, version: str) -> ResourceVersionRecord: ...
