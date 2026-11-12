from __future__ import annotations

# app/composition/health.py: 装配健康检查与告警投递端口。

from dataclasses import dataclass

from app.composition.document_pipeline import DocumentPipeline
from app.composition.platform import PlatformServices
from app.core.config import Settings
from app.domains.ops.real_alert_delivery import EnvironmentSecretResolver, SlackWebhookAlertDeliveryProvider
from app.infrastructure.persistence import PersistenceAdapters
from app.services.health_service import HealthService


@dataclass(frozen=True)
class ObservabilityServices:
    health_service: HealthService
    alert_delivery_provider: SlackWebhookAlertDeliveryProvider
    secret_resolver: EnvironmentSecretResolver


def build_observability_services(
    settings: Settings,
    adapters: PersistenceAdapters,
    platform: PlatformServices,
    pipeline: DocumentPipeline,
) -> ObservabilityServices:
    resource_version_service = platform.resource_version_service
    return ObservabilityServices(
        health_service=HealthService(
            settings,
            effective_repository_backend=adapters.backend_name,
            artifact_storage_backend=settings.jobs_artifact_storage_backend,
            document_job_repository=adapters.document_job_repository,
            document_job_callback_message_store=adapters.document_job_callback_message_store,
            internal_user_repository=adapters.internal_user_repository,
            audit_event_repository=adapters.audit_event_repository,
            resource_version_repository=(
                resource_version_service.repository if resource_version_service is not None else None
            ),
            default_template_id_getter=pipeline.template_read_service.get_default_template_id,
            ai_provider_config_service=pipeline.ai_provider_config_service,
            mineru_config_service=pipeline.mineru_config_service,
        ),
        alert_delivery_provider=SlackWebhookAlertDeliveryProvider(),
        secret_resolver=EnvironmentSecretResolver(),
    )
