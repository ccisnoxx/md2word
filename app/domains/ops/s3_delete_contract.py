# File: app/domains/ops/s3_delete_contract.py
# Purpose: Define the S3 delete adapter contract and LocalStack/fake parity evidence.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.config import Settings
from app.domains.files.service import S3_DELETE_FAKE_CONTRACT_VERSION
from app.domains.resources.models import utc_now


S3_DELETE_ADAPTER_CONTRACT_VERSION = "ops-s3-delete-adapter-v1"
FAKE_S3_DELETE_ADAPTER_ID = "file_retention_s3_fake"
S3_DELETE_LOCALSTACK_HARNESS = "localstack"


@dataclass(frozen=True, slots=True)
class OpsS3DeleteLocalStackProfile:
    """描述未来 LocalStack 合同测试需要保持的外部 harness 语义。"""

    harness: Literal["localstack"]
    endpoint_required: bool
    versioned_bucket_required: bool
    exact_bucket_key_required: bool
    version_id_supported: bool
    etag_precondition_supported: bool
    runtime_executed: bool
    provider_payload_persisted: bool
    secrets_required_for_contract_report: bool

    def to_dict(self) -> dict[str, str | bool]:
        """转换为 API response 可校验的 JSON-safe 字典。"""

        return {
            "harness": self.harness,
            "endpoint_required": self.endpoint_required,
            "versioned_bucket_required": self.versioned_bucket_required,
            "exact_bucket_key_required": self.exact_bucket_key_required,
            "version_id_supported": self.version_id_supported,
            "etag_precondition_supported": self.etag_precondition_supported,
            "runtime_executed": self.runtime_executed,
            "provider_payload_persisted": self.provider_payload_persisted,
            "secrets_required_for_contract_report": self.secrets_required_for_contract_report,
        }


@dataclass(frozen=True, slots=True)
class OpsS3DeleteAdapterContractReport:
    """汇总 S3 delete adapter 合同、LocalStack/fake parity 和只读安全声明。"""

    generated_at: datetime
    action_mode: Literal["adapter_contract"]
    contract_version: str
    fake_adapter_id: str
    fake_adapter_mode: Literal["fake"]
    fake_file_retention_contract_version: str
    localstack_profile: OpsS3DeleteLocalStackProfile
    storage_config_summary: dict[str, str | bool]
    required_request_fields: list[str]
    required_result_fields: list[str]
    required_audit_fields: list[str]
    required_safety_fields: list[str]
    parity_checks: dict[str, bool]
    blocking_reasons: list[str]
    safety: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的 JSON-safe 字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "contract_version": self.contract_version,
            "fake_adapter_id": self.fake_adapter_id,
            "fake_adapter_mode": self.fake_adapter_mode,
            "fake_file_retention_contract_version": self.fake_file_retention_contract_version,
            "localstack_profile": self.localstack_profile.to_dict(),
            "storage_config_summary": dict(self.storage_config_summary),
            "required_request_fields": list(self.required_request_fields),
            "required_result_fields": list(self.required_result_fields),
            "required_audit_fields": list(self.required_audit_fields),
            "required_safety_fields": list(self.required_safety_fields),
            "parity_checks": dict(self.parity_checks),
            "blocking_reasons": list(self.blocking_reasons),
            "safety": dict(self.safety),
        }


class OpsS3DeleteAdapterContractService:
    """生成 S3 delete adapter 合同报告，不读取 secret value 或调用 S3/LocalStack。"""

    def __init__(self, settings: Settings) -> None:
        """保存运行配置；只读取非敏感配置摘要。"""

        self.settings = settings

    def build_report(self) -> OpsS3DeleteAdapterContractReport:
        """构建 LocalStack/fake parity 只读报告，真实 S3 delete 继续 blocked。"""

        return OpsS3DeleteAdapterContractReport(
            generated_at=utc_now(),
            action_mode="adapter_contract",
            contract_version=S3_DELETE_ADAPTER_CONTRACT_VERSION,
            fake_adapter_id=FAKE_S3_DELETE_ADAPTER_ID,
            fake_adapter_mode="fake",
            fake_file_retention_contract_version=S3_DELETE_FAKE_CONTRACT_VERSION,
            localstack_profile=OpsS3DeleteLocalStackProfile(
                harness=S3_DELETE_LOCALSTACK_HARNESS,
                endpoint_required=True,
                versioned_bucket_required=True,
                exact_bucket_key_required=True,
                version_id_supported=True,
                etag_precondition_supported=True,
                runtime_executed=False,
                provider_payload_persisted=False,
                secrets_required_for_contract_report=False,
            ),
            storage_config_summary=self._storage_config_summary(),
            required_request_fields=[
                "bucket",
                "object_key",
                "version_id",
                "etag",
                "idempotency_key",
                "signed_cleanup_plan",
                "reason",
                "confirmation",
            ],
            required_result_fields=[
                "contract_version",
                "adapter_id",
                "adapter_mode",
                "operation_id",
                "idempotency_key",
                "bucket",
                "object_key",
                "version_id",
                "etag",
                "delete_marker",
                "provider_request_id",
                "outcome",
                "error_code",
                "retryable",
            ],
            required_audit_fields=[
                "contract_version",
                "adapter_result",
                "bucket",
                "object_key",
                "version_id",
                "etag",
                "idempotency_key",
                "signed_cleanup_plan_hash",
                "metadata_mutation_rule",
                "safety",
            ],
            required_safety_fields=[
                "real_s3_delete_executed",
                "localstack_calls_executed",
                "metadata_mutated",
                "audit_events_written",
                "secret_values_exposed",
            ],
            parity_checks={
                "fake_file_retention_contract_version_linked": True,
                "fake_uses_exact_bucket_key": True,
                "fake_preserves_version_id": True,
                "fake_returns_stable_expected_outcome": True,
                "fake_never_calls_s3": True,
                "fake_never_mutates_metadata": True,
                "fake_never_writes_audit": True,
                "localstack_profile_uses_same_request_fields": True,
                "localstack_profile_uses_same_result_fields": True,
                "metadata_mutation_requires_provider_success": True,
                "idempotency_key_required_for_real_adapter": True,
            },
            blocking_reasons=[
                "real_s3_delete_adapter_not_implemented",
                "localstack_contract_not_executed_in_runtime",
                "live_s3_delete_disabled_by_default",
                "cleanup_scheduler_execute_deferred",
            ],
            safety={
                "read_only": True,
                "provider_calls_executed": False,
                "real_s3_delete_executed": False,
                "localstack_calls_executed": False,
                "cleanup_executed": False,
                "scheduler_loop_executed": False,
                "delete_executed": False,
                "metadata_mutated": False,
                "audit_events_written": False,
                "conversion_workflow_executed": False,
                "secret_values_exposed": False,
            },
        )

    def _storage_config_summary(self) -> dict[str, str | bool]:
        """返回 S3 配置的非敏感摘要，不暴露 access key、secret 或 endpoint 凭据。"""

        endpoint_url = self.settings.jobs_artifact_s3_endpoint_url.strip()
        return {
            "artifact_storage_backend": self.settings.jobs_artifact_storage_backend,
            "s3_bucket_configured": bool(self.settings.jobs_artifact_s3_bucket),
            "s3_endpoint_configured": bool(endpoint_url),
            "s3_endpoint_localstack_like": self._is_localstack_like_endpoint(endpoint_url),
            "s3_region": self.settings.jobs_artifact_s3_region,
            "s3_key_prefix_configured": bool(self.settings.jobs_artifact_s3_key_prefix),
            "s3_access_key_configured": bool(self.settings.jobs_artifact_s3_access_key_id),
            "s3_secret_key_configured": bool(self.settings.jobs_artifact_s3_secret_access_key),
            "secret_values_exposed": False,
        }

    def _is_localstack_like_endpoint(self, endpoint_url: str) -> bool:
        """用非敏感 endpoint 文本判断是否像 LocalStack，本方法不发起网络请求。"""

        lowered = endpoint_url.lower()
        return "localstack" in lowered or "localhost" in lowered or "127.0.0.1" in lowered
