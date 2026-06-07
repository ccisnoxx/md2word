# File: app/domains/ops/alert_delivery_contract.py
# Purpose: Define the real alert delivery adapter contract and fake-adapter parity evidence.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domains.jobs.models import utc_now
from app.domains.ops.schemas import OpsAlertDeliveryChannel


ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION = "ops-alert-delivery-adapter-v1"
FAKE_ALERT_DELIVERY_ADAPTER_ID = "local_outbox_fake"
ALERT_DELIVERY_REAL_CHANNELS = ["slack", "email", "webhook"]
ALERT_DELIVERY_CONTRACT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class OpsAlertDeliveryAdapterResult:
    """描述一次 alert delivery adapter 结果；fake 和未来 real adapter 共用该合同。"""

    contract_version: str
    adapter_id: str
    adapter_mode: Literal["fake"]
    channel: OpsAlertDeliveryChannel
    alert_code: str
    operation_id: str
    idempotency_key: str
    dedupe_key: str
    timeout_seconds: int
    outcome: str
    provider_request_id: str | None = None
    error_code: str | None = None
    retryable: bool = False
    provider_calls_executed: bool = False
    external_delivery_executed: bool = False
    payload_persisted: bool = False
    secret_values_exposed: bool = False

    def to_dict(self) -> dict[str, str | int | bool | None]:
        """转换为 API response 和 audit details 可复用的安全字典。"""

        return {
            "contract_version": self.contract_version,
            "adapter_id": self.adapter_id,
            "adapter_mode": self.adapter_mode,
            "channel": self.channel,
            "alert_code": self.alert_code,
            "operation_id": self.operation_id,
            "idempotency_key": self.idempotency_key,
            "dedupe_key": self.dedupe_key,
            "timeout_seconds": self.timeout_seconds,
            "outcome": self.outcome,
            "provider_request_id": self.provider_request_id,
            "error_code": self.error_code,
            "retryable": self.retryable,
            "provider_calls_executed": self.provider_calls_executed,
            "external_delivery_executed": self.external_delivery_executed,
            "payload_persisted": self.payload_persisted,
            "secret_values_exposed": self.secret_values_exposed,
        }


@dataclass(frozen=True, slots=True)
class OpsAlertDeliveryAdapterContractReport:
    """汇总 alert delivery adapter 合同、fake parity 和只读安全声明。"""

    generated_at: datetime
    action_mode: Literal["adapter_contract"]
    contract_version: str
    fake_adapter_id: str
    fake_adapter_mode: Literal["fake"]
    real_channels: list[str]
    required_request_fields: list[str]
    required_result_fields: list[str]
    required_audit_fields: list[str]
    required_safety_fields: list[str]
    parity_checks: dict[str, bool]
    destination_count: int
    destination_channels: list[str]
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
            "real_channels": list(self.real_channels),
            "required_request_fields": list(self.required_request_fields),
            "required_result_fields": list(self.required_result_fields),
            "required_audit_fields": list(self.required_audit_fields),
            "required_safety_fields": list(self.required_safety_fields),
            "parity_checks": dict(self.parity_checks),
            "destination_count": self.destination_count,
            "destination_channels": list(self.destination_channels),
            "blocking_reasons": list(self.blocking_reasons),
            "safety": dict(self.safety),
        }


class OpsAlertDeliveryAdapterContractService:
    """生成 alert delivery adapter 合同报告，不读取 secret value 或发送通知。"""

    def __init__(self, *, destinations_json: str) -> None:
        self.destinations_json = destinations_json

    def build_report(self) -> OpsAlertDeliveryAdapterContractReport:
        """构建真实 alert delivery adapter 合同和 fake parity 只读报告。"""

        destination_count, destination_channels = self._destination_summary()
        return OpsAlertDeliveryAdapterContractReport(
            generated_at=utc_now(),
            action_mode="adapter_contract",
            contract_version=ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION,
            fake_adapter_id=FAKE_ALERT_DELIVERY_ADAPTER_ID,
            fake_adapter_mode="fake",
            real_channels=list(ALERT_DELIVERY_REAL_CHANNELS),
            required_request_fields=[
                "destination_id",
                "channel",
                "alert_code",
                "dedupe_key",
                "idempotency_key",
                "timeout_seconds",
                "reason",
                "confirmation",
            ],
            required_result_fields=[
                "contract_version",
                "adapter_id",
                "adapter_mode",
                "operation_id",
                "provider_request_id",
                "outcome",
                "error_code",
                "retryable",
            ],
            required_audit_fields=[
                "contract_version",
                "adapter_result",
                "dedupe_key",
                "idempotency_key",
                "timeout_seconds",
                "safety",
            ],
            required_safety_fields=[
                "provider_calls_executed",
                "external_delivery_executed",
                "payload_persisted",
                "secret_values_exposed",
            ],
            parity_checks={
                "fake_uses_same_contract_version": True,
                "fake_returns_adapter_result": True,
                "fake_uses_stable_dedupe_key": True,
                "fake_uses_stable_idempotency_key": True,
                "fake_records_structured_audit_details": True,
                "fake_never_resolves_secret_values": True,
                "fake_never_calls_provider": True,
                "fake_never_sends_external_delivery": True,
            },
            destination_count=destination_count,
            destination_channels=destination_channels,
            blocking_reasons=[
                "real_send_requires_explicit_endpoint_and_confirmation",
                "live_delivery_disabled_by_default",
            ],
            safety={
                "read_only": True,
                "provider_calls_executed": False,
                "external_delivery_executed": False,
                "audit_events_written": False,
                "cleanup_executed": False,
                "delete_executed": False,
                "conversion_workflow_executed": False,
                "secret_values_exposed": False,
            },
        )

    def _destination_summary(self) -> tuple[int, list[str]]:
        """只解析 destination channel 摘要，不读取 secret value。"""

        raw_text = self.destinations_json.strip()
        if not raw_text:
            return 0, []
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError:
            return 0, []
        if not isinstance(decoded, list):
            return 0, []
        channels = sorted(
            {
                item.get("channel")
                for item in decoded
                if isinstance(item, dict)
                and isinstance(item.get("channel"), str)
                and item.get("channel") in ALERT_DELIVERY_REAL_CHANNELS
            }
        )
        return len([item for item in decoded if isinstance(item, dict)]), channels


def build_fake_alert_delivery_adapter_result(
    *,
    alert_code: str,
    channel: OpsAlertDeliveryChannel,
    dedupe_key: str,
    outcome: str,
) -> OpsAlertDeliveryAdapterResult:
    """构造 fake adapter result，字段与未来 real adapter contract 保持同形。"""

    return OpsAlertDeliveryAdapterResult(
        contract_version=ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION,
        adapter_id=FAKE_ALERT_DELIVERY_ADAPTER_ID,
        adapter_mode="fake",
        channel=channel,
        alert_code=alert_code,
        operation_id=f"{FAKE_ALERT_DELIVERY_ADAPTER_ID}:{dedupe_key}",
        idempotency_key=f"ops_alert_delivery:{dedupe_key}",
        dedupe_key=dedupe_key,
        timeout_seconds=ALERT_DELIVERY_CONTRACT_TIMEOUT_SECONDS,
        outcome=outcome,
    )
