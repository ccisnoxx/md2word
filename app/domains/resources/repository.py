from __future__ import annotations

# app/domains/resources/repository.py: 定义 resource version domain 依赖的持久化端口。

from typing import Protocol

from app.domains.resources.models import ResourceType, ResourceVersionRecord


class ResourceVersionRepositoryProtocol(Protocol):
    """模板、术语和翻译配置共用的资源版本持久化合同。"""

    def save_resource_version(self, record: ResourceVersionRecord) -> ResourceVersionRecord: ...
    def get_resource_version(
        self,
        resource_type: ResourceType,
        resource_id: str,
        version: str,
    ) -> ResourceVersionRecord | None: ...
    def list_resource_versions(self, resource_type: ResourceType, resource_id: str) -> list[ResourceVersionRecord]: ...
    def set_default_resource_version(self, resource_type: ResourceType, resource_id: str, version: str) -> None: ...
    def get_default_resource_version(self, resource_type: ResourceType, resource_id: str) -> ResourceVersionRecord | None: ...
