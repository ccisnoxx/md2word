from __future__ import annotations

# app/core/runtime.py: 保存 FastAPI 进程内共享的应用服务和边界端口。

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.jobs.dispatch import StageDispatcherProtocol


@dataclass(slots=True)
class AppRuntime:
    settings: Settings
    repository: Any
    health_service: Any
    template_read_service: Any
    term_rule_service: Any
    term_rule_import_validation_service: Any
    term_rule_file_sync_service: Any
    artifact_service: Any
    command_service: Any
    lifecycle_service: Any
    query_service: Any
    stage_service: Any
    stage_dispatcher: StageDispatcherProtocol
