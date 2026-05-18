from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings


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
