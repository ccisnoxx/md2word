# File: app/domains/ops/real_alert_delivery.py
# Purpose: Guard and execute the Phase 7 Slack webhook alert delivery pilot.

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol
from uuid import uuid4

from fastapi import status

from app.api.v1.routers.health_schemas import HealthOpsAlertItem
from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.audit.models import AuditEvent
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.resources.models import utc_now
from app.domains.ops.alert_delivery_contract import ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION
from app.domains.ops.alert_destinations import OpsAlertDestinationDryRunService
from app.domains.ops.schemas import OpsAlertDeliveryChannel, OpsAlertDeliveryMode


REAL_ALERT_DELIVERY_AUDIT_ACTION = "ops.alert_delivery_real"
REAL_ALERT_DELIVERY_ADAPTER_ID = "slack_webhook_real"
REAL_ALERT_DELIVERY_DESTINATION_ID = "ops-slack-primary"
REAL_ALERT_DELIVERY_CHANNEL = "slack"
REAL_ALERT_DELIVERY_SECRET_REF = "OPS_SLACK_WEBHOOK_URL"
REAL_ALERT_DELIVERY_TARGET_LABEL = "#ops-alerts-phase7-pilot"
REAL_ALERT_DELIVERY_ALERT_CODE = "stage_spool_failed_messages_present"
REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE = "SEND REAL OPS ALERTS"
REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES = 60
REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR = 3
REAL_ALERT_DELIVERY_TIMEOUT_SECONDS = 10

RealAlertDeliveryOutcome = Literal[
    "deliverable",
    "sent",
    "deduped",
    "blocked",
    "rate_limited",
    "failed",
    "timed_out",
]


class SecretResolver(Protocol):
    """按 secret ref 解析 secret value；实现方不得记录或返回给 API。"""

    def resolve_secret(self, secret_ref: str) -> str | None:
        """返回 secret value；未配置时返回 None。"""


class EnvironmentSecretResolver:
    """从环境变量读取 secret value，避免把 secret 加入 settings 响应模型。"""

    def resolve_secret(self, secret_ref: str) -> str | None:
        """读取指定环境变量并过滤空值。"""

        value = os.environ.get(secret_ref)
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


@dataclass(frozen=True, slots=True)
class RealAlertDeliveryAttempt:
    """描述一次已通过 gate 的 Slack webhook 发送尝试。"""

    delivery_id: str
    destination_id: str
    target_label: str
    alert_code: str
    title: str | None
    severity: str | None
    source: str | None
    dedupe_key: str
    idempotency_key: str
    operation_id: str
    timeout_seconds: int
    webhook_url: str


@dataclass(frozen=True, slots=True)
class RealAlertDeliveryProviderResult:
    """保存 provider 调用的脱敏结果，不包含 webhook URL 或响应正文。"""

    outcome: RealAlertDeliveryOutcome
    provider_request_id: str | None
    error_code: str | None
    retryable: bool
    provider_calls_executed: bool
    external_delivery_executed: bool


class RealAlertDeliveryProvider(Protocol):
    """Slack webhook provider 边界；测试可注入 fake provider 避免真实网络调用。"""

    def send(self, attempt: RealAlertDeliveryAttempt) -> RealAlertDeliveryProviderResult:
        """执行一次 provider 调用并返回脱敏结果。"""


class SlackWebhookAlertDeliveryProvider:
    """使用 Slack Incoming Webhook 执行真实发送；仅在所有 gate 通过后被调用。"""

    def send(self, attempt: RealAlertDeliveryAttempt) -> RealAlertDeliveryProviderResult:
        """向 Slack webhook POST 最小 payload，并丢弃响应正文。"""

        payload = {
            "text": f"[md2word ops] {attempt.alert_code}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*md2word ops alert*\n"
                            f"*code*: `{attempt.alert_code}`\n"
                            f"*severity*: `{attempt.severity or 'unknown'}`\n"
                            f"*source*: `{attempt.source or 'unknown'}`\n"
                            f"*title*: {attempt.title or '-'}\n"
                            f"*target*: `{attempt.target_label}`"
                        ),
                    },
                }
            ],
        }
        request = urllib.request.Request(
            attempt.webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=attempt.timeout_seconds) as response:
                response.close()
            return RealAlertDeliveryProviderResult(
                outcome="sent",
                provider_request_id=None,
                error_code=None,
                retryable=False,
                provider_calls_executed=True,
                external_delivery_executed=True,
            )
        except TimeoutError:
            return self._timed_out_result()
        except socket.timeout:
            return self._timed_out_result()
        except urllib.error.HTTPError as exc:
            return RealAlertDeliveryProviderResult(
                outcome="failed",
                provider_request_id=None,
                error_code=f"http_{exc.code}",
                retryable=exc.code >= 500 or exc.code == 429,
                provider_calls_executed=True,
                external_delivery_executed=False,
            )
        except urllib.error.URLError as exc:
            return RealAlertDeliveryProviderResult(
                outcome="failed",
                provider_request_id=None,
                error_code=exc.reason.__class__.__name__,
                retryable=True,
                provider_calls_executed=True,
                external_delivery_executed=False,
            )

    def _timed_out_result(self) -> RealAlertDeliveryProviderResult:
        """构造统一 timeout 结果，避免调用方解析异常类型。"""

        return RealAlertDeliveryProviderResult(
            outcome="timed_out",
            provider_request_id=None,
            error_code="timeout",
            retryable=True,
            provider_calls_executed=True,
            external_delivery_executed=False,
        )


@dataclass(frozen=True, slots=True)
class OpsRealAlertDeliveryAdapterResult:
    """描述 real alert delivery adapter 的脱敏执行结果。"""

    channel: OpsAlertDeliveryChannel
    alert_code: str
    operation_id: str
    idempotency_key: str
    dedupe_key: str
    timeout_seconds: int
    outcome: RealAlertDeliveryOutcome
    provider_request_id: str | None = None
    error_code: str | None = None
    retryable: bool = False
    provider_calls_executed: bool = False
    external_delivery_executed: bool = False

    def to_dict(self) -> dict[str, str | int | bool | None]:
        """转换为 API response 和 audit details 共用的安全字典。"""

        return {
            "contract_version": ALERT_DELIVERY_ADAPTER_CONTRACT_VERSION,
            "adapter_id": REAL_ALERT_DELIVERY_ADAPTER_ID,
            "adapter_mode": "real",
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
            "payload_persisted": False,
            "secret_values_exposed": False,
        }


@dataclass(frozen=True, slots=True)
class OpsRealAlertDeliveryItem:
    """描述 pilot 目标的一次 real-send preview 或 execution 结果。"""

    alert_code: str
    destination_id: str
    target_label: str
    severity: str | None
    source: str | None
    title: str | None
    outcome: RealAlertDeliveryOutcome
    dedupe_key: str
    idempotency_key: str
    missing_gates: list[str]
    reason: str
    audit_event_written: bool
    adapter_result: OpsRealAlertDeliveryAdapterResult

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的字典。"""

        return {
            "alert_code": self.alert_code,
            "destination_id": self.destination_id,
            "target_label": self.target_label,
            "severity": self.severity,
            "source": self.source,
            "title": self.title,
            "outcome": self.outcome,
            "dedupe_key": self.dedupe_key,
            "idempotency_key": self.idempotency_key,
            "missing_gates": list(self.missing_gates),
            "reason": self.reason,
            "audit_event_written": self.audit_event_written,
            "adapter_result": self.adapter_result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OpsRealAlertDeliveryReport:
    """汇总一次 Slack webhook pilot preview 或 execution。"""

    generated_at: datetime
    action_mode: OpsAlertDeliveryMode
    channel: OpsAlertDeliveryChannel
    confirmation_phrase: str
    dedupe_window_minutes: int
    requested_alert_codes: list[str]
    requested_destination_ids: list[str]
    delivery_id: str
    totals: dict[str, int]
    gate_snapshot: dict[str, object]
    rollback: dict[str, object]
    items: list[OpsRealAlertDeliveryItem]

    def to_dict(self) -> dict[str, object]:
        """转换为 router response 的基础字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "channel": self.channel,
            "confirmation_phrase": self.confirmation_phrase,
            "dedupe_window_minutes": self.dedupe_window_minutes,
            "requested_alert_codes": list(self.requested_alert_codes),
            "requested_destination_ids": list(self.requested_destination_ids),
            "delivery_id": self.delivery_id,
            "totals": dict(self.totals),
            "gate_snapshot": dict(self.gate_snapshot),
            "rollback": dict(self.rollback),
            "items": [item.to_dict() for item in self.items],
        }


class OpsRealAlertDeliveryService:
    """执行 Phase 7 Slack webhook pilot 的 gate、preview 和受控发送。"""

    def __init__(
        self,
        *,
        settings: Settings,
        destinations_json: str,
        current_alerts: list[HealthOpsAlertItem],
        audit_event_repository: AuditEventRepositoryProtocol,
        provider: RealAlertDeliveryProvider,
        secret_resolver: SecretResolver,
    ) -> None:
        self.settings = settings
        self.destinations_json = destinations_json
        self.current_alerts = current_alerts
        self.audit_event_repository = audit_event_repository
        self.provider = provider
        self.secret_resolver = secret_resolver

    def preview(
        self,
        *,
        alert_codes: list[str],
        destination_ids: list[str],
        dedupe_window_minutes: int,
    ) -> OpsRealAlertDeliveryReport:
        """预览 real-send gates，不解析 secret value、不调用 provider、不写 audit。"""

        context = self._build_context(
            alert_codes=alert_codes,
            destination_ids=destination_ids,
            dedupe_window_minutes=dedupe_window_minutes,
            confirmation=REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
            resolve_secret=False,
        )
        outcome: RealAlertDeliveryOutcome = "blocked" if context["missing_gates"] else "deliverable"
        return self._build_report(
            generated_at=utc_now(),
            action_mode="real_send_preview",
            context=context,
            outcome=outcome,
            reason=self._reason_for_outcome(outcome, context["missing_gates"]),
            audit_event_written=False,
            provider_result=None,
        )

    def real_send(
        self,
        *,
        alert_codes: list[str],
        destination_ids: list[str],
        reason: str,
        confirmation: str,
        dedupe_window_minutes: int,
    ) -> OpsRealAlertDeliveryReport:
        """执行受控 real-send；只有所有 gate 通过后才解析 secret 并调用 provider。"""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if confirmation != REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"confirmation 必须为 {REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE}。",
            )
        generated_at = utc_now()
        context = self._build_context(
            alert_codes=alert_codes,
            destination_ids=destination_ids,
            dedupe_window_minutes=dedupe_window_minutes,
            confirmation=confirmation,
            resolve_secret=True,
        )
        if context["missing_gates"]:
            return self._build_report(
                generated_at=generated_at,
                action_mode="real_send",
                context=context,
                outcome="blocked",
                reason=self._reason_for_outcome("blocked", context["missing_gates"]),
                audit_event_written=True,
                provider_result=None,
            )
        if self._is_deduped(generated_at=generated_at, idempotency_key=context["idempotency_key"]):
            return self._build_report(
                generated_at=generated_at,
                action_mode="real_send",
                context=context,
                outcome="deduped",
                reason="dedupe window 内已存在成功 real Slack delivery audit。",
                audit_event_written=True,
                provider_result=None,
            )
        if self._is_rate_limited(generated_at=generated_at, destination_id=REAL_ALERT_DELIVERY_DESTINATION_ID):
            return self._build_report(
                generated_at=generated_at,
                action_mode="real_send",
                context=context,
                outcome="rate_limited",
                reason="destination 在 1 小时窗口内已达到 Phase 7 pilot rate limit。",
                audit_event_written=True,
                provider_result=None,
            )
        provider_result = self.provider.send(
            RealAlertDeliveryAttempt(
                delivery_id=context["delivery_id"],
                destination_id=REAL_ALERT_DELIVERY_DESTINATION_ID,
                target_label=REAL_ALERT_DELIVERY_TARGET_LABEL,
                alert_code=REAL_ALERT_DELIVERY_ALERT_CODE,
                title=context["alert"].title,
                severity=context["alert"].severity,
                source=context["alert"].source,
                dedupe_key=context["dedupe_key"],
                idempotency_key=context["idempotency_key"],
                operation_id=context["operation_id"],
                timeout_seconds=REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
                webhook_url=context["secret_value"],
            )
        )
        return self._build_report(
            generated_at=generated_at,
            action_mode="real_send",
            context=context,
            outcome=provider_result.outcome,
            reason=self._reason_for_outcome(provider_result.outcome, []),
            audit_event_written=True,
            provider_result=provider_result,
        )

    def audit_reason(self, *, human_reason: str, report: OpsRealAlertDeliveryReport) -> str:
        """生成 compact audit reason，避免写入 secret 或完整 Slack payload。"""

        normalized_reason = " ".join(human_reason.strip().split())
        item = report.items[0]
        return (
            f"reason={normalized_reason} channel={report.channel} "
            f"destination={item.destination_id} alert={item.alert_code} "
            f"outcome={item.outcome} dedupe_key={item.dedupe_key} "
            f"idempotency_key={item.idempotency_key}"
        )

    def _build_context(
        self,
        *,
        alert_codes: list[str],
        destination_ids: list[str],
        dedupe_window_minutes: int,
        confirmation: str,
        resolve_secret: bool,
    ) -> dict[str, object]:
        """校验请求、destination 和 capability gates，并按需解析 secret。"""

        self._validate_exact_request(alert_codes=alert_codes, destination_ids=destination_ids)
        if dedupe_window_minutes != REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"dedupe_window_minutes 必须为 {REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES}。",
            )
        alert = self._active_alert()
        destination = self._pilot_destination()
        missing_gates = self._capability_gates()
        missing_gates.extend(self._destination_gates(destination))
        secret_value: str | None = None
        if resolve_secret and not missing_gates:
            secret_value = self.secret_resolver.resolve_secret(REAL_ALERT_DELIVERY_SECRET_REF)
            if not secret_value:
                missing_gates.append("secret_ref_unresolved")
        delivery_id = f"alert_delivery_{uuid4().hex[:12]}"
        dedupe_key = f"{REAL_ALERT_DELIVERY_ALERT_CODE}:{REAL_ALERT_DELIVERY_DESTINATION_ID}:real"
        idempotency_key = f"ops_alert_delivery_real:{REAL_ALERT_DELIVERY_DESTINATION_ID}:{REAL_ALERT_DELIVERY_ALERT_CODE}"
        return {
            "alert": alert,
            "destination": destination,
            "delivery_id": delivery_id,
            "dedupe_key": dedupe_key,
            "idempotency_key": idempotency_key,
            "operation_id": f"{REAL_ALERT_DELIVERY_ADAPTER_ID}:{idempotency_key}",
            "missing_gates": self._unique(missing_gates),
            "secret_value": secret_value,
            "confirmation": confirmation,
        }

    def _validate_exact_request(self, *, alert_codes: list[str], destination_ids: list[str]) -> None:
        """强制 Phase 7 pilot 只能请求一个固定 destination 和 alert code。"""

        normalized_alerts = [item.strip() for item in alert_codes]
        normalized_destinations = [item.strip() for item in destination_ids]
        if normalized_alerts != [REAL_ALERT_DELIVERY_ALERT_CODE]:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"alert_codes 必须精确等于 [{REAL_ALERT_DELIVERY_ALERT_CODE}]。",
            )
        if normalized_destinations != [REAL_ALERT_DELIVERY_DESTINATION_ID]:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"destination_ids 必须精确等于 [{REAL_ALERT_DELIVERY_DESTINATION_ID}]。",
            )

    def _active_alert(self) -> HealthOpsAlertItem:
        """返回当前 active pilot alert；未激活时阻断执行。"""

        for alert in self.current_alerts:
            if alert.code == REAL_ALERT_DELIVERY_ALERT_CODE:
                return alert
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "conflict",
            f"alert code 当前未激活: {REAL_ALERT_DELIVERY_ALERT_CODE}",
        )

    def _pilot_destination(self) -> dict[str, object]:
        """复用 destination dry-run parser，并返回 pilot destination 安全摘要。"""

        report = OpsAlertDestinationDryRunService(
            destinations_json=self.destinations_json,
            current_alerts=self.current_alerts,
        ).dry_run(
            alert_codes=[REAL_ALERT_DELIVERY_ALERT_CODE],
            destination_ids=[REAL_ALERT_DELIVERY_DESTINATION_ID],
        )
        if report.config_errors:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"alert destination 配置无效: {'; '.join(report.config_errors)}",
            )
        if len(report.destinations) != 1:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"destination 未配置: {REAL_ALERT_DELIVERY_DESTINATION_ID}",
            )
        return report.destinations[0].to_dict()

    def _capability_gates(self) -> list[str]:
        """检查 integration capability flag、dry-run 和 kill switch。"""

        missing_gates: list[str] = []
        if not self.settings.integration_alert_delivery_enabled:
            missing_gates.append("integration_alert_delivery_disabled")
        if self.settings.integration_alert_delivery_dry_run:
            missing_gates.append("dry_run_only")
        if self.settings.integration_alert_delivery_kill_switch:
            missing_gates.append("kill_switch_active")
        return missing_gates

    def _destination_gates(self, destination: dict[str, object]) -> list[str]:
        """校验 fixed pilot destination 的 channel、allowlist、rate 和 secret ref 摘要。"""

        missing_gates: list[str] = []
        if destination.get("channel") != REAL_ALERT_DELIVERY_CHANNEL:
            missing_gates.append("pilot_destination_channel_mismatch")
        if destination.get("enabled") is not True:
            missing_gates.append("destination_disabled")
        if destination.get("secret_ref") != REAL_ALERT_DELIVERY_SECRET_REF:
            missing_gates.append("pilot_secret_ref_mismatch")
        if destination.get("target_label") != REAL_ALERT_DELIVERY_TARGET_LABEL:
            missing_gates.append("pilot_target_label_mismatch")
        if REAL_ALERT_DELIVERY_ALERT_CODE not in destination.get("allowlist", []):
            missing_gates.append("alert_code_not_allowlisted")
        if destination.get("rate_limit_per_hour") != REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR:
            missing_gates.append("pilot_rate_limit_mismatch")
        if destination.get("dedupe_window_minutes") != REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES:
            missing_gates.append("pilot_dedupe_window_mismatch")
        return missing_gates

    def _is_deduped(self, *, generated_at: datetime, idempotency_key: str) -> bool:
        """检查 dedupe window 内是否已经有同一 idempotency key 的成功发送。"""

        since = generated_at - timedelta(minutes=REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES)
        for event in self._recent_real_events(since=since):
            details = event.details or {}
            if (
                details.get("idempotency_key") == idempotency_key
                and details.get("outcome") == "sent"
            ):
                return True
        return False

    def _is_rate_limited(self, *, generated_at: datetime, destination_id: str) -> bool:
        """检查 1 小时窗口内同一 destination 的 provider 尝试次数。"""

        since = generated_at - timedelta(hours=1)
        counted_outcomes = {"sent", "failed", "timed_out"}
        attempts = 0
        for event in self._recent_real_events(since=since):
            details = event.details or {}
            if details.get("destination_id") != destination_id:
                continue
            if details.get("outcome") in counted_outcomes:
                attempts += 1
        return attempts >= REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR

    def _recent_real_events(self, *, since: datetime) -> list[AuditEvent]:
        """读取最近 real delivery audit events，用于 dedupe 和 rate-limit 判断。"""

        return [
            event
            for event in self.audit_event_repository.list_audit_events()
            if event.action == REAL_ALERT_DELIVERY_AUDIT_ACTION and event.created_at >= since
        ]

    def _build_report(
        self,
        *,
        generated_at: datetime,
        action_mode: OpsAlertDeliveryMode,
        context: dict[str, object],
        outcome: RealAlertDeliveryOutcome,
        reason: str,
        audit_event_written: bool,
        provider_result: RealAlertDeliveryProviderResult | None,
    ) -> OpsRealAlertDeliveryReport:
        """把 gate context 和 provider result 组装成统一 response。"""

        alert = context["alert"]
        missing_gates = list(context["missing_gates"])
        adapter_result = self._adapter_result(
            context=context,
            outcome=outcome,
            provider_result=provider_result,
        )
        item = OpsRealAlertDeliveryItem(
            alert_code=REAL_ALERT_DELIVERY_ALERT_CODE,
            destination_id=REAL_ALERT_DELIVERY_DESTINATION_ID,
            target_label=REAL_ALERT_DELIVERY_TARGET_LABEL,
            severity=alert.severity,
            source=alert.source,
            title=alert.title,
            outcome=outcome,
            dedupe_key=context["dedupe_key"],
            idempotency_key=context["idempotency_key"],
            missing_gates=missing_gates,
            reason=reason,
            audit_event_written=audit_event_written,
            adapter_result=adapter_result,
        )
        return OpsRealAlertDeliveryReport(
            generated_at=generated_at,
            action_mode=action_mode,
            channel=REAL_ALERT_DELIVERY_CHANNEL,
            confirmation_phrase=REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
            dedupe_window_minutes=REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
            requested_alert_codes=[REAL_ALERT_DELIVERY_ALERT_CODE],
            requested_destination_ids=[REAL_ALERT_DELIVERY_DESTINATION_ID],
            delivery_id=context["delivery_id"],
            totals=self._totals(outcome=outcome, audit_event_written=audit_event_written),
            gate_snapshot=self._gate_snapshot(missing_gates=missing_gates),
            rollback=self._rollback(),
            items=[item],
        )

    def _adapter_result(
        self,
        *,
        context: dict[str, object],
        outcome: RealAlertDeliveryOutcome,
        provider_result: RealAlertDeliveryProviderResult | None,
    ) -> OpsRealAlertDeliveryAdapterResult:
        """把 provider result 映射为统一 adapter evidence。"""

        return OpsRealAlertDeliveryAdapterResult(
            channel=REAL_ALERT_DELIVERY_CHANNEL,
            alert_code=REAL_ALERT_DELIVERY_ALERT_CODE,
            operation_id=context["operation_id"],
            idempotency_key=context["idempotency_key"],
            dedupe_key=context["dedupe_key"],
            timeout_seconds=REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
            outcome=outcome,
            provider_request_id=provider_result.provider_request_id if provider_result else None,
            error_code=provider_result.error_code if provider_result else None,
            retryable=provider_result.retryable if provider_result else False,
            provider_calls_executed=provider_result.provider_calls_executed if provider_result else False,
            external_delivery_executed=provider_result.external_delivery_executed if provider_result else False,
        )

    def _totals(self, *, outcome: RealAlertDeliveryOutcome, audit_event_written: bool) -> dict[str, int]:
        """生成 totals，保持与 fake delivery response 的宽松字典风格兼容。"""

        keys = ["requested", "deliverable", "sent", "deduped", "blocked", "rate_limited", "failed", "timed_out"]
        totals = {key: 0 for key in keys}
        totals["requested"] = 1
        if outcome in totals:
            totals[outcome] = 1
        totals["audit_events_written"] = 1 if audit_event_written else 0
        return totals

    def _gate_snapshot(self, *, missing_gates: list[str]) -> dict[str, object]:
        """返回不含 secret value 的 gate 快照。"""

        return {
            "destination_id": REAL_ALERT_DELIVERY_DESTINATION_ID,
            "channel": REAL_ALERT_DELIVERY_CHANNEL,
            "secret_ref": REAL_ALERT_DELIVERY_SECRET_REF,
            "secret_value_exposed": False,
            "target_label": REAL_ALERT_DELIVERY_TARGET_LABEL,
            "allowed_alert_code": REAL_ALERT_DELIVERY_ALERT_CODE,
            "confirmation_phrase": REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE,
            "rate_limit_per_hour": REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR,
            "dedupe_window_minutes": REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
            "timeout_seconds": REAL_ALERT_DELIVERY_TIMEOUT_SECONDS,
            "integration_alert_delivery_enabled": self.settings.integration_alert_delivery_enabled,
            "integration_alert_delivery_dry_run": self.settings.integration_alert_delivery_dry_run,
            "integration_alert_delivery_kill_switch": self.settings.integration_alert_delivery_kill_switch,
            "missing_gates": list(missing_gates),
        }

    def _rollback(self) -> dict[str, object]:
        """返回页面和审计可展示的配置回滚口径。"""

        return {
            "disable_flag": "INTEGRATION_ALERT_DELIVERY_ENABLED=false",
            "enable_kill_switch": "INTEGRATION_ALERT_DELIVERY_KILL_SWITCH=true",
            "restore_dry_run": "INTEGRATION_ALERT_DELIVERY_DRY_RUN=true",
            "disable_destination": REAL_ALERT_DELIVERY_DESTINATION_ID,
            "remove_or_rotate_secret_ref": REAL_ALERT_DELIVERY_SECRET_REF,
        }

    def _reason_for_outcome(self, outcome: RealAlertDeliveryOutcome, missing_gates: list[str]) -> str:
        """生成单条 item reason，避免把完整 provider payload 写出。"""

        if outcome == "deliverable":
            return "Phase 7 Slack webhook pilot gates 已通过 preview；未解析 secret、未调用 provider。"
        if outcome == "sent":
            return "Phase 7 Slack webhook pilot 已完成 provider 调用。"
        if outcome == "deduped":
            return "dedupe window 内已存在成功发送，未再次调用 provider。"
        if outcome == "rate_limited":
            return "Phase 7 Slack destination rate limit 阻断，未调用 provider。"
        if outcome == "timed_out":
            return "Slack webhook provider 调用超时，响应正文未保存。"
        if outcome == "failed":
            return "Slack webhook provider 调用失败，响应正文未保存。"
        return f"Phase 7 Slack webhook pilot gates blocked: {', '.join(missing_gates)}"

    def _unique(self, values: list[str]) -> list[str]:
        """保持输入顺序去重，避免重复 gate reason 干扰审阅。"""

        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result
