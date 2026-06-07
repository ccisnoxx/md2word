# File: app/domains/ops/alert_delivery.py
# Purpose: Provide Admin-only fake Ops alert delivery outbox preview and execution logic.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import status

from app.api.v1.routers.health_schemas import HealthOpsAlertItem
from app.core.errors import ApiError
from app.domains.audit.models import AuditEvent
from app.domains.audit.repository import AuditEventRepositoryProtocol
from app.domains.jobs.models import utc_now
from app.domains.ops.alert_delivery_contract import (
    OpsAlertDeliveryAdapterResult,
    build_fake_alert_delivery_adapter_result,
)
from app.domains.ops.schemas import (
    OpsAlertDeliveryChannel,
    OpsAlertDeliveryMode,
)


ALERT_DELIVERY_BATCH_LIMIT = 10
ALERT_DELIVERY_CONFIRMATION_PHRASE = "SEND FAKE OPS ALERTS"
ALERT_DELIVERY_AUDIT_ACTION = "ops.alert_delivery_fake"


@dataclass(frozen=True, slots=True)
class OpsAlertDeliveryItem:
    """描述一个 alert code 的 dry-run 或 fake delivery 结果。"""

    alert_code: str
    severity: str | None
    source: str | None
    title: str | None
    outcome: str
    dedupe_key: str | None
    reason: str
    audit_event_written: bool = False
    adapter_result: OpsAlertDeliveryAdapterResult | None = None

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的字典。"""

        return {
            "alert_code": self.alert_code,
            "severity": self.severity,
            "source": self.source,
            "title": self.title,
            "outcome": self.outcome,
            "dedupe_key": self.dedupe_key,
            "reason": self.reason,
            "audit_event_written": self.audit_event_written,
            "adapter_result": self.adapter_result.to_dict() if self.adapter_result else None,
        }


@dataclass(frozen=True, slots=True)
class OpsAlertDeliveryReport:
    """汇总一次 Ops alert delivery preview 或 fake execution。"""

    generated_at: datetime
    action_mode: OpsAlertDeliveryMode
    channel: OpsAlertDeliveryChannel
    confirmation_phrase: str
    dedupe_window_minutes: int
    requested_alert_codes: list[str]
    delivery_id: str
    totals: dict[str, int]
    items: list[OpsAlertDeliveryItem]

    def to_dict(self) -> dict[str, object]:
        """转换为 router response 的基础字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "channel": self.channel,
            "confirmation_phrase": self.confirmation_phrase,
            "dedupe_window_minutes": self.dedupe_window_minutes,
            "requested_alert_codes": self.requested_alert_codes,
            "delivery_id": self.delivery_id,
            "totals": self.totals,
            "items": [item.to_dict() for item in self.items],
        }


class OpsAlertDeliveryService:
    """基于当前 ops-alerts 生成本地 fake outbox delivery 合同。"""

    def __init__(
        self,
        *,
        current_alerts: list[HealthOpsAlertItem],
        audit_event_repository: AuditEventRepositoryProtocol,
    ) -> None:
        self.current_alerts = current_alerts
        self.audit_event_repository = audit_event_repository

    def preview(
        self,
        *,
        alert_codes: list[str],
        channel: OpsAlertDeliveryChannel,
        dedupe_window_minutes: int,
    ) -> OpsAlertDeliveryReport:
        """预览精确 alert codes，不写 audit、不发送通知。"""

        generated_at = utc_now()
        normalized_codes = self._validate_alert_codes(alert_codes)
        alerts_by_code = self._active_alerts_by_code()
        self._ensure_alerts_active(normalized_codes, alerts_by_code)
        items = [
            self._build_item(
                alert=alerts_by_code[alert_code],
                channel=channel,
                outcome="deliverable",
                reason="当前告警可进入 fake outbox delivery preview。",
                audit_event_written=False,
            )
            for alert_code in normalized_codes
        ]
        return self._build_report(
            generated_at=generated_at,
            action_mode="dry_run",
            channel=channel,
            dedupe_window_minutes=dedupe_window_minutes,
            requested_alert_codes=normalized_codes,
            items=items,
        )

    def fake_send(
        self,
        *,
        alert_codes: list[str],
        channel: OpsAlertDeliveryChannel,
        reason: str,
        confirmation: str,
        dedupe_window_minutes: int,
    ) -> OpsAlertDeliveryReport:
        """执行本地 fake outbox delivery；只写审计，不发送外部通知。"""

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if confirmation != ALERT_DELIVERY_CONFIRMATION_PHRASE:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"confirmation 必须为 {ALERT_DELIVERY_CONFIRMATION_PHRASE}。",
            )
        generated_at = utc_now()
        normalized_codes = self._validate_alert_codes(alert_codes)
        alerts_by_code = self._active_alerts_by_code()
        self._ensure_alerts_active(normalized_codes, alerts_by_code)
        recent_dedupe_keys = self._recent_dedupe_keys(
            generated_at=generated_at,
            dedupe_window_minutes=dedupe_window_minutes,
        )
        items: list[OpsAlertDeliveryItem] = []
        for alert_code in normalized_codes:
            alert = alerts_by_code[alert_code]
            dedupe_key = self._dedupe_key(alert_code, channel)
            if dedupe_key in recent_dedupe_keys:
                items.append(
                    self._build_item(
                        alert=alert,
                        channel=channel,
                        outcome="deduped",
                        reason="dedupe window 内已存在 fake outbox delivery audit。",
                        audit_event_written=False,
                    )
                )
                continue
            items.append(
                self._build_item(
                    alert=alert,
                    channel=channel,
                    outcome="fake_delivered",
                    reason="fake local outbox delivery recorded。",
                    audit_event_written=True,
                )
            )
        return self._build_report(
            generated_at=generated_at,
            action_mode="fake_send",
            channel=channel,
            dedupe_window_minutes=dedupe_window_minutes,
            requested_alert_codes=normalized_codes,
            items=items,
        )

    def audit_reason(self, *, human_reason: str, report: OpsAlertDeliveryReport) -> str:
        """生成 compact audit reason，避免写入完整 health payload。"""

        normalized_reason = " ".join(human_reason.strip().split())
        delivered_keys = [
            item.dedupe_key or self._dedupe_key(item.alert_code, report.channel)
            for item in report.items
            if item.outcome == "fake_delivered"
        ]
        return (
            f"reason={normalized_reason} channel={report.channel} "
            f"alerts={','.join(report.requested_alert_codes)} "
            f"dedupe_keys={','.join(delivered_keys)} "
            f"fake_delivered={report.totals.get('fake_delivered', 0)} "
            f"deduped={report.totals.get('deduped', 0)} "
            f"skipped={report.totals.get('skipped', 0)} failed={report.totals.get('failed', 0)}"
        )

    def _validate_alert_codes(self, alert_codes: list[str]) -> list[str]:
        """校验 alert code 列表，避免隐式全量或重复投递。"""

        if not alert_codes:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "alert_codes 不能为空。")
        if len(alert_codes) > ALERT_DELIVERY_BATCH_LIMIT:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"单次最多允许处理 {ALERT_DELIVERY_BATCH_LIMIT} 个 alert code。",
            )
        normalized = [alert_code.strip() for alert_code in alert_codes]
        if any(not alert_code for alert_code in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "alert_codes 不能包含空白项。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "alert_codes 不能包含重复项。")
        return normalized

    def _ensure_alerts_active(
        self,
        alert_codes: list[str],
        alerts_by_code: dict[str, HealthOpsAlertItem],
    ) -> None:
        """确认请求目标都来自当前活跃 ops-alerts 响应。"""

        inactive = [alert_code for alert_code in alert_codes if alert_code not in alerts_by_code]
        if inactive:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"alert code 当前未激活: {', '.join(inactive)}",
            )

    def _active_alerts_by_code(self) -> dict[str, HealthOpsAlertItem]:
        """按 code 索引当前只读 health ops alerts。"""

        return {alert.code: alert for alert in self.current_alerts}

    def _recent_dedupe_keys(
        self,
        *,
        generated_at: datetime,
        dedupe_window_minutes: int,
    ) -> set[str]:
        """从近期 audit event reason 中提取已 fake delivery 的 dedupe keys。"""

        since = generated_at - timedelta(minutes=dedupe_window_minutes)
        keys: set[str] = set()
        for event in self.audit_event_repository.list_audit_events():
            if event.action != ALERT_DELIVERY_AUDIT_ACTION or event.created_at < since:
                continue
            for key in self._extract_dedupe_keys(event):
                keys.add(key)
        return keys

    def _extract_dedupe_keys(self, event: AuditEvent) -> list[str]:
        """从 compact audit reason 解析 dedupe_keys 字段。"""

        reason = event.reason or ""
        for part in reason.split():
            if not part.startswith("dedupe_keys="):
                continue
            raw_value = part.removeprefix("dedupe_keys=")
            return [item for item in raw_value.split(",") if item]
        return []

    def _build_item(
        self,
        *,
        alert: HealthOpsAlertItem,
        channel: OpsAlertDeliveryChannel,
        outcome: str,
        reason: str,
        audit_event_written: bool,
    ) -> OpsAlertDeliveryItem:
        """把 health alert 映射为 delivery item。"""

        dedupe_key = self._dedupe_key(alert.code, channel)
        return OpsAlertDeliveryItem(
            alert_code=alert.code,
            severity=alert.severity,
            source=alert.source,
            title=alert.title,
            outcome=outcome,
            dedupe_key=dedupe_key,
            reason=reason,
            audit_event_written=audit_event_written,
            adapter_result=build_fake_alert_delivery_adapter_result(
                alert_code=alert.code,
                channel=channel,
                dedupe_key=dedupe_key,
                outcome=outcome,
            ),
        )

    def _build_report(
        self,
        *,
        generated_at: datetime,
        action_mode: OpsAlertDeliveryMode,
        channel: OpsAlertDeliveryChannel,
        dedupe_window_minutes: int,
        requested_alert_codes: list[str],
        items: list[OpsAlertDeliveryItem],
    ) -> OpsAlertDeliveryReport:
        """汇总 preview/fake-send 结果计数。"""

        totals = {
            "requested": len(requested_alert_codes),
            "deliverable": sum(1 for item in items if item.outcome == "deliverable"),
            "fake_delivered": sum(1 for item in items if item.outcome == "fake_delivered"),
            "deduped": sum(1 for item in items if item.outcome == "deduped"),
            "skipped": sum(1 for item in items if item.outcome.startswith("skipped_")),
            "failed": sum(1 for item in items if item.outcome == "failed"),
            "audit_events_written": 1 if any(item.audit_event_written for item in items) else 0,
        }
        return OpsAlertDeliveryReport(
            generated_at=generated_at,
            action_mode=action_mode,
            channel=channel,
            confirmation_phrase=ALERT_DELIVERY_CONFIRMATION_PHRASE,
            dedupe_window_minutes=dedupe_window_minutes,
            requested_alert_codes=requested_alert_codes,
            delivery_id=f"alert_delivery_{uuid4().hex[:12]}",
            totals=totals,
            items=items,
        )

    def _dedupe_key(self, alert_code: str, channel: OpsAlertDeliveryChannel) -> str:
        """生成 fake delivery 的稳定幂等 key。"""

        return f"{alert_code}:{channel}"
