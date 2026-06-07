# File: app/domains/ops/alert_destinations.py
# Purpose: Validate staged Ops alert destination configuration without sending notifications.

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import status

from app.api.v1.routers.health_schemas import HealthOpsAlertItem
from app.core.errors import ApiError
from app.domains.jobs.models import utc_now
from app.domains.ops.alert_delivery import ALERT_DELIVERY_BATCH_LIMIT


ALERT_DESTINATION_CHANNELS = {"slack", "email", "webhook"}
DEFAULT_ALERT_DESTINATION_RATE_LIMIT_PER_HOUR = 60
DEFAULT_ALERT_DESTINATION_DEDUPE_WINDOW_MINUTES = 60


@dataclass(frozen=True, slots=True)
class OpsAlertDestinationConfig:
    """保存单个 staged alert destination 的安全配置摘要。"""

    destination_id: str
    channel: str
    enabled: bool
    secret_ref: str
    target_label: str
    allowlist: list[str]
    rate_limit_per_hour: int
    dedupe_window_minutes: int


@dataclass(frozen=True, slots=True)
class OpsAlertDestinationDryRunItem:
    """返回单个 destination 的配置 dry-run 结果。"""

    destination_id: str
    channel: str
    enabled: bool
    secret_ref: str
    secret_ref_present: bool
    target_label: str
    allowlist: list[str]
    rate_limit_per_hour: int
    dedupe_window_minutes: int
    status: str
    missing_gates: list[str]
    matched_alert_codes: list[str]
    blocked_alert_codes: list[str]

    def to_dict(self) -> dict[str, object]:
        """转换为 API response 可校验的字典。"""

        return {
            "destination_id": self.destination_id,
            "channel": self.channel,
            "enabled": self.enabled,
            "secret_ref": self.secret_ref,
            "secret_ref_present": self.secret_ref_present,
            "target_label": self.target_label,
            "allowlist": self.allowlist,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "dedupe_window_minutes": self.dedupe_window_minutes,
            "status": self.status,
            "missing_gates": self.missing_gates,
            "matched_alert_codes": self.matched_alert_codes,
            "blocked_alert_codes": self.blocked_alert_codes,
        }


@dataclass(frozen=True, slots=True)
class OpsAlertDestinationDryRunReport:
    """汇总 alert destination config dry-run 响应。"""

    generated_at: datetime
    action_mode: str
    requested_alert_codes: list[str]
    requested_destination_ids: list[str]
    configured_count: int
    selected_count: int
    config_errors: list[str]
    destinations: list[OpsAlertDestinationDryRunItem]

    def to_dict(self) -> dict[str, object]:
        """转换为 router response 的基础字典。"""

        return {
            "generated_at": self.generated_at,
            "action_mode": self.action_mode,
            "requested_alert_codes": self.requested_alert_codes,
            "requested_destination_ids": self.requested_destination_ids,
            "configured_count": self.configured_count,
            "selected_count": self.selected_count,
            "config_errors": self.config_errors,
            "destinations": [item.to_dict() for item in self.destinations],
        }


class OpsAlertDestinationDryRunService:
    """解析并 dry-run alert destination 配置；不会发送通知或读取 secret value。"""

    def __init__(
        self,
        *,
        destinations_json: str,
        current_alerts: list[HealthOpsAlertItem],
    ) -> None:
        self.destinations_json = destinations_json
        self.current_alerts = current_alerts

    def dry_run(
        self,
        *,
        alert_codes: list[str],
        destination_ids: list[str],
    ) -> OpsAlertDestinationDryRunReport:
        """执行只读配置 dry-run，按可选精确 alert codes 评估 allowlist。"""

        generated_at = utc_now()
        normalized_alert_codes = self._validate_alert_codes(alert_codes)
        normalized_destination_ids = self._validate_destination_ids(destination_ids)
        self._ensure_alerts_active(normalized_alert_codes)
        configs, config_errors = self._load_configs()
        selected_configs, selection_errors = self._select_configs(
            configs,
            destination_ids=normalized_destination_ids,
        )
        config_errors.extend(selection_errors)
        items = [
            self._build_item(
                config,
                requested_alert_codes=normalized_alert_codes,
            )
            for config in selected_configs
        ]
        return OpsAlertDestinationDryRunReport(
            generated_at=generated_at,
            action_mode="config_dry_run",
            requested_alert_codes=normalized_alert_codes,
            requested_destination_ids=normalized_destination_ids,
            configured_count=len(configs),
            selected_count=len(items),
            config_errors=config_errors,
            destinations=items,
        )

    def _load_configs(self) -> tuple[list[OpsAlertDestinationConfig], list[str]]:
        """解析 settings JSON，逐条收集配置错误而不是中断 dry-run。"""

        raw_text = self.destinations_json.strip()
        if not raw_text:
            return [], []
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return [], [f"OPS_ALERT_DESTINATIONS_JSON 不是合法 JSON: {exc.msg}"]
        if not isinstance(decoded, list):
            return [], ["OPS_ALERT_DESTINATIONS_JSON 必须是 JSON array。"]

        configs: list[OpsAlertDestinationConfig] = []
        errors: list[str] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(decoded):
            config, item_errors = self._parse_config_item(item, index=index)
            errors.extend(item_errors)
            if config is None:
                continue
            if config.destination_id in seen_ids:
                errors.append(f"destinations[{index}].destination_id 重复: {config.destination_id}")
                continue
            seen_ids.add(config.destination_id)
            configs.append(config)
        return configs, errors

    def _parse_config_item(
        self,
        item: object,
        *,
        index: int,
    ) -> tuple[OpsAlertDestinationConfig | None, list[str]]:
        """解析单个 destination item，并把字段问题转换为错误列表。"""

        if not isinstance(item, dict):
            return None, [f"destinations[{index}] 必须是 object。"]
        errors: list[str] = []
        destination_id = self._string_field(item, "destination_id")
        channel = self._string_field(item, "channel")
        enabled = item.get("enabled", False)
        secret_ref = self._string_field(item, "secret_ref")
        target_label = self._string_field(item, "target_label")
        allowlist = self._string_list_field(item, "allowlist", index=index, errors=errors)
        rate_limit_per_hour = self._int_field(
            item,
            "rate_limit_per_hour",
            default=DEFAULT_ALERT_DESTINATION_RATE_LIMIT_PER_HOUR,
            minimum=1,
            maximum=1000,
            index=index,
            errors=errors,
        )
        dedupe_window_minutes = self._int_field(
            item,
            "dedupe_window_minutes",
            default=DEFAULT_ALERT_DESTINATION_DEDUPE_WINDOW_MINUTES,
            minimum=1,
            maximum=1440,
            index=index,
            errors=errors,
        )

        if not destination_id:
            errors.append(f"destinations[{index}].destination_id 不能为空。")
        if channel not in ALERT_DESTINATION_CHANNELS:
            errors.append(f"destinations[{index}].channel 必须是 slack/email/webhook。")
        if not isinstance(enabled, bool):
            errors.append(f"destinations[{index}].enabled 必须是 boolean。")
        if len(set(allowlist)) != len(allowlist):
            errors.append(f"destinations[{index}].allowlist 不能包含重复 alert code。")

        if errors:
            return None, errors
        return (
            OpsAlertDestinationConfig(
                destination_id=destination_id,
                channel=channel,
                enabled=enabled,
                secret_ref=secret_ref,
                target_label=target_label,
                allowlist=allowlist,
                rate_limit_per_hour=rate_limit_per_hour,
                dedupe_window_minutes=dedupe_window_minutes,
            ),
            [],
        )

    def _select_configs(
        self,
        configs: list[OpsAlertDestinationConfig],
        *,
        destination_ids: list[str],
    ) -> tuple[list[OpsAlertDestinationConfig], list[str]]:
        """按请求中的 destination_ids 选择配置，未知 ID 作为 dry-run error 返回。"""

        if not destination_ids:
            return configs, []
        configs_by_id = {config.destination_id: config for config in configs}
        selected = [configs_by_id[destination_id] for destination_id in destination_ids if destination_id in configs_by_id]
        missing_ids = [destination_id for destination_id in destination_ids if destination_id not in configs_by_id]
        errors = [f"destination_ids 未配置: {', '.join(missing_ids)}"] if missing_ids else []
        return selected, errors

    def _build_item(
        self,
        config: OpsAlertDestinationConfig,
        *,
        requested_alert_codes: list[str],
    ) -> OpsAlertDestinationDryRunItem:
        """根据 destination 配置和请求 alert codes 生成 dry-run gate 结果。"""

        matched_codes = [
            alert_code
            for alert_code in requested_alert_codes
            if alert_code in config.allowlist
        ]
        blocked_codes = [
            alert_code
            for alert_code in requested_alert_codes
            if alert_code not in config.allowlist
        ]
        missing_gates: list[str] = []
        if not config.enabled:
            missing_gates.append("destination_disabled")
        if not config.secret_ref:
            missing_gates.append("missing_secret_ref")
        if not config.target_label:
            missing_gates.append("missing_target_label")
        if requested_alert_codes and blocked_codes:
            missing_gates.append("alert_code_not_allowlisted")
        if not requested_alert_codes:
            missing_gates.append("alert_codes_not_requested")
        missing_gates.append("real_delivery_not_implemented")

        return OpsAlertDestinationDryRunItem(
            destination_id=config.destination_id,
            channel=config.channel,
            enabled=config.enabled,
            secret_ref=config.secret_ref,
            secret_ref_present=bool(config.secret_ref),
            target_label=config.target_label,
            allowlist=list(config.allowlist),
            rate_limit_per_hour=config.rate_limit_per_hour,
            dedupe_window_minutes=config.dedupe_window_minutes,
            status=self._status_from_gates(missing_gates),
            missing_gates=missing_gates,
            matched_alert_codes=matched_codes,
            blocked_alert_codes=blocked_codes,
        )

    def _status_from_gates(self, missing_gates: list[str]) -> str:
        """把 gates 归约为页面可读的 dry-run 状态。"""

        if "destination_disabled" in missing_gates:
            return "disabled"
        if "missing_secret_ref" in missing_gates or "missing_target_label" in missing_gates:
            return "missing_config"
        if "alert_code_not_allowlisted" in missing_gates:
            return "blocked"
        if "alert_codes_not_requested" in missing_gates:
            return "config_valid"
        return "dry_run_passed"

    def _validate_alert_codes(self, alert_codes: list[str]) -> list[str]:
        """校验请求 alert code 列表，避免隐式全量或重复 target。"""

        if len(alert_codes) > ALERT_DELIVERY_BATCH_LIMIT:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"单次最多允许 dry-run {ALERT_DELIVERY_BATCH_LIMIT} 个 alert code。",
            )
        normalized = [alert_code.strip() for alert_code in alert_codes]
        if any(not alert_code for alert_code in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "alert_codes 不能包含空白项。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "alert_codes 不能包含重复项。")
        return normalized

    def _validate_destination_ids(self, destination_ids: list[str]) -> list[str]:
        """校验请求 destination id 列表，保持精确目标语义。"""

        normalized = [destination_id.strip() for destination_id in destination_ids]
        if any(not destination_id for destination_id in normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "destination_ids 不能包含空白项。")
        if len(set(normalized)) != len(normalized):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "destination_ids 不能包含重复项。")
        return normalized

    def _ensure_alerts_active(self, alert_codes: list[str]) -> None:
        """确认请求中的 alert codes 都来自当前 active ops-alerts 响应。"""

        if not alert_codes:
            return
        active_codes = {alert.code for alert in self.current_alerts}
        inactive = [alert_code for alert_code in alert_codes if alert_code not in active_codes]
        if inactive:
            raise ApiError(
                status.HTTP_409_CONFLICT,
                "conflict",
                f"alert code 当前未激活: {', '.join(inactive)}",
            )

    def _string_field(self, item: dict[str, object], key: str) -> str:
        """读取字符串字段；非字符串按空值处理并由调用方决定是否报错。"""

        value = item.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    def _string_list_field(
        self,
        item: dict[str, object],
        key: str,
        *,
        index: int,
        errors: list[str],
    ) -> list[str]:
        """读取字符串列表字段，并过滤空字符串。"""

        value = item.get(key, [])
        if value is None:
            return []
        if not isinstance(value, list):
            errors.append(f"destinations[{index}].{key} 必须是 string array。")
            return []
        normalized: list[str] = []
        for value_index, entry in enumerate(value):
            if not isinstance(entry, str):
                errors.append(f"destinations[{index}].{key}[{value_index}] 必须是 string。")
                continue
            stripped = entry.strip()
            if stripped:
                normalized.append(stripped)
        return normalized

    def _int_field(
        self,
        item: dict[str, object],
        key: str,
        *,
        default: int,
        minimum: int,
        maximum: int,
        index: int,
        errors: list[str],
    ) -> int:
        """读取带边界的 int 字段，非法值记录错误并回退默认值。"""

        value = item.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"destinations[{index}].{key} 必须是 integer。")
            return default
        if value < minimum or value > maximum:
            errors.append(f"destinations[{index}].{key} 必须在 {minimum}..{maximum} 之间。")
            return default
        return value
