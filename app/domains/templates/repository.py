from __future__ import annotations

from typing import Any, Protocol

from app.core.errors import ApplicationError
from app.domains.audit.models import AuditEvent
from app.domains.resources.models import ResourceDefaultPointer, ResourceVersionRecord
from app.domains.templates.models import TemplateCatalogItem


class TemplateCatalogCommitUnknown(ApplicationError):
    """写入结束后连接异常，无法从该连接确认事务提交结果。"""

    def __init__(self) -> None:
        super().__init__(
            "template_catalog_commit_unknown",
            "模板操作提交结果未知，请重新读取目录和版本。",
            category="service_unavailable",
        )


class TemplateCatalogRepositoryProtocol(Protocol):
    """生产模板目录与版本关联写入的持久化边界。"""

    def get_template(self, template_id: str) -> TemplateCatalogItem | None: ...

    def list_enabled_templates(self) -> list[TemplateCatalogItem]: ...

    def create_template(self, item: TemplateCatalogItem, first_version: ResourceVersionRecord) -> None: ...

    def update_template(self, template_id: str, updates: dict[str, Any]) -> None: ...

    def delete_template(self, template_id: str) -> None: ...

    def get_default_template_id(self) -> str | None: ...

    def set_default_template(self, template_id: str, expected_version: str) -> None: ...

    def initialize_default_template(self, template_id: str, expected_version: str) -> None: ...

    def bootstrap_seed(self, item: TemplateCatalogItem, record: ResourceVersionRecord) -> None: ...

    def add_template_version(self, record: ResourceVersionRecord) -> None: ...

    def publish_template_version(
        self, record: ResourceVersionRecord, *, expected_snapshot_hash: str, make_default: bool,
    ) -> ResourceVersionRecord | None: ...

    def set_default_template_version(
        self,
        record: ResourceVersionRecord,
        *,
        expected_pointer: ResourceDefaultPointer | None,
        audit_event: AuditEvent | None = None,
    ) -> ResourceVersionRecord | None: ...

    def disable_template_version(self, template_id: str, version: str) -> ResourceVersionRecord: ...
