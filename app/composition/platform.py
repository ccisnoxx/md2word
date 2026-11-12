from __future__ import annotations

# app/composition/platform.py: 装配审计、验收、认证、内部用户、文件、资源版本与保存视图等平台服务。

from dataclasses import dataclass

from app.core.config import Settings
from app.domains.acceptance.service import AcceptanceRunService
from app.domains.audit.service import AuditService
from app.domains.files import FileRetentionPolicyService, FileUploadService
from app.domains.resources.service import ResourceVersionService
from app.domains.saved_views.service import SavedViewService
from app.domains.users.service import InternalUserManagementService
from app.infrastructure.persistence import PersistenceAdapters
from app.services.auth import AuthService


@dataclass(frozen=True)
class PlatformServices:
    audit_service: AuditService
    acceptance_run_service: AcceptanceRunService
    auth_service: AuthService
    internal_user_management_service: InternalUserManagementService
    file_retention_policy_service: FileRetentionPolicyService
    file_upload_service: FileUploadService
    resource_version_service: ResourceVersionService | None
    saved_view_service: SavedViewService


def build_platform_services(settings: Settings, adapters: PersistenceAdapters) -> PlatformServices:
    """只构造，不执行种子写入；`AuthService` 构造时导入配置用户属于其自身合同。"""

    file_retention_policy_service = FileRetentionPolicyService(
        settings,
        adapters.file_retention_policy_repository,
        adapters.document_file_repository,
    )
    return PlatformServices(
        audit_service=AuditService(adapters.audit_event_repository),
        acceptance_run_service=AcceptanceRunService(adapters.acceptance_run_repository),
        auth_service=AuthService(settings, adapters.internal_user_repository),
        internal_user_management_service=InternalUserManagementService(adapters.internal_user_repository),
        file_retention_policy_service=file_retention_policy_service,
        file_upload_service=FileUploadService(
            settings,
            adapters.document_file_repository,
            retention_days_resolver=file_retention_policy_service.resolve_retention_days,
        ),
        # 资源版本能力只在持久化后端提供资源版本仓储时启用，下游据此决定是否构造版本化服务。
        resource_version_service=(
            ResourceVersionService(adapters.resource_version_repository)
            if adapters.resource_version_repository is not None
            else None
        ),
        saved_view_service=SavedViewService(adapters.saved_view_repository),
    )
