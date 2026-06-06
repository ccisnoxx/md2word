# File: app/domains/files/retention_policy.py
# Purpose: Define document_files retention policy records, repository port, and governance service.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol, get_args
from uuid import uuid4

from fastapi import status
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.files.models import DocumentFileRecord, DocumentFileType
from app.domains.files.repository import DocumentFileRepositoryProtocol
from app.domains.jobs.models import utc_now


FileRetentionPolicyStatus = Literal["draft", "published", "disabled"]
FileRetentionPolicyScopeType = Literal["global", "file_type"]
FileRetentionPolicySource = Literal["published_policy", "settings_fallback"]

RETENTION_POLICY_MAX_DAYS = 3650
RETENTION_POLICY_FILE_TYPES = set(get_args(DocumentFileType))


class FileRetentionPolicyRecord(BaseModel):
    """持久化的 document_files 保留策略；不删除历史策略记录。"""

    policy_id: str
    name: str
    status: FileRetentionPolicyStatus = "draft"
    scope_type: FileRetentionPolicyScopeType
    file_type: str | None = None
    retention_days: int
    description: str | None = None
    is_default: bool = False
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    published_by: str | None = None
    published_at: datetime | None = None
    disabled_by: str | None = None
    disabled_at: datetime | None = None
    reason: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """校验策略名称，避免空白名称进入治理列表。"""

        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("策略名称不能为空。")
        if len(normalized) > 120:
            raise ValueError("策略名称不能超过 120 个字符。")
        return normalized

    @field_validator("retention_days")
    @classmethod
    def validate_retention_days(cls, value: int) -> int:
        """校验保留天数范围，避免配置过短或无限制策略。"""

        if value < 1 or value > RETENTION_POLICY_MAX_DAYS:
            raise ValueError(f"retention_days 必须在 1..{RETENTION_POLICY_MAX_DAYS} 之间。")
        return value

    @model_validator(mode="after")
    def validate_scope(self) -> "FileRetentionPolicyRecord":
        """校验 scope_type 和 file_type 的组合。"""

        if self.scope_type == "global":
            self.file_type = None
        elif not self.file_type:
            raise ValueError("file_type scope 必须提供 file_type。")
        elif self.file_type not in RETENTION_POLICY_FILE_TYPES:
            raise ValueError(f"不支持的 file_type: {self.file_type}")
        return self


class FileRetentionPolicyRepositoryProtocol(Protocol):
    """document_files retention policy metadata repository 合同。"""

    def create_policy(self, record: FileRetentionPolicyRecord) -> FileRetentionPolicyRecord: ...
    def get_policy(self, policy_id: str) -> FileRetentionPolicyRecord | None: ...
    def list_policies(self) -> list[FileRetentionPolicyRecord]: ...
    def update_policy(self, policy_id: str, **patch: Any) -> FileRetentionPolicyRecord: ...


@dataclass(frozen=True, slots=True)
class EffectiveFileRetentionPolicy:
    """某个 file_type 解析得到的有效保留策略。"""

    retention_days: int
    source: FileRetentionPolicySource
    policy_id: str | None
    scope_type: FileRetentionPolicyScopeType | None
    file_type: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class FileRetentionPolicyImpactItem:
    """单个 document_file 在候选策略下的过期时间影响。"""

    file_id: str
    job_id: str | None
    file_type: str
    status: str
    storage_provider: str
    current_expires_at: datetime | None
    projected_expires_at: datetime
    currently_expired: bool
    would_be_expired: bool
    would_change_expires_at: bool


@dataclass(frozen=True, slots=True)
class FileRetentionPolicyImpactReport:
    """retention policy impact preview 汇总，不修改任何记录。"""

    generated_at: datetime
    policy: FileRetentionPolicyRecord
    totals: dict[str, int]
    items: list[FileRetentionPolicyImpactItem]


class FileRetentionPolicyService:
    """管理 document_files 保留策略，并为新文件解析保留天数。"""

    def __init__(
        self,
        settings: Settings,
        policy_repository: FileRetentionPolicyRepositoryProtocol,
        document_file_repository: DocumentFileRepositoryProtocol,
    ) -> None:
        self.settings = settings
        self.policy_repository = policy_repository
        self.document_file_repository = document_file_repository

    def list_policies(self) -> list[FileRetentionPolicyRecord]:
        """列出全部保留策略，按创建时间和 ID 稳定排序。"""

        return sorted(
            self.policy_repository.list_policies(),
            key=lambda policy: (policy.created_at, policy.policy_id),
        )

    def get_policy(self, policy_id: str) -> FileRetentionPolicyRecord:
        """读取单个保留策略；不存在时返回 404。"""

        record = self.policy_repository.get_policy(policy_id)
        if record is None:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", f"保留策略不存在: {policy_id}")
        return record

    def create_policy(
        self,
        *,
        name: str,
        scope_type: FileRetentionPolicyScopeType,
        file_type: str | None,
        retention_days: int,
        description: str | None,
        actor_id: str | None,
    ) -> FileRetentionPolicyRecord:
        """创建 draft 保留策略；不会影响新文件或历史文件。"""

        now = utc_now()
        record = self._build_policy_record(
            policy_id=f"retpol_{uuid4().hex[:12]}",
            name=name,
            status="draft",
            scope_type=scope_type,
            file_type=file_type,
            retention_days=retention_days,
            description=_normalize_optional_text(description),
            is_default=False,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        return self.policy_repository.create_policy(record)

    def update_policy(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        scope_type: FileRetentionPolicyScopeType | None = None,
        file_type: str | None = None,
        retention_days: int | None = None,
        description: str | None = None,
    ) -> FileRetentionPolicyRecord:
        """更新 draft 策略；published/disabled 策略只能通过治理动作改变状态。"""

        existing = self.get_policy(policy_id)
        if existing.status != "draft":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 draft 保留策略可以编辑。")
        patch: dict[str, Any] = {"updated_at": utc_now()}
        if name is not None:
            patch["name"] = name
        next_scope_type = scope_type or existing.scope_type
        patch["scope_type"] = next_scope_type
        if next_scope_type == "global":
            patch["file_type"] = None
        elif file_type is not None:
            patch["file_type"] = file_type
        else:
            patch["file_type"] = existing.file_type
        if retention_days is not None:
            patch["retention_days"] = retention_days
        if description is not None:
            patch["description"] = _normalize_optional_text(description)
        validated = self._build_policy_record(**existing.model_copy(update=patch).model_dump(mode="python"))
        validated_patch = validated.model_dump(mode="python")
        validated_patch.pop("policy_id", None)
        return self.policy_repository.update_policy(policy_id, **validated_patch)

    def publish_policy(
        self,
        policy_id: str,
        *,
        reason: str,
        actor_id: str | None,
    ) -> FileRetentionPolicyRecord:
        """发布 draft 策略，并将同 scope 的其他 published 策略置为非默认。"""

        existing = self.get_policy(policy_id)
        if existing.status != "draft":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 draft 保留策略可以发布。")
        normalized_reason = self._require_reason(reason)
        now = utc_now()
        published = self.policy_repository.update_policy(
            policy_id,
            status="published",
            is_default=True,
            published_by=actor_id,
            published_at=now,
            reason=normalized_reason,
            updated_at=now,
        )
        return self._set_default_for_scope(published, now=now, reason=normalized_reason, actor_id=actor_id)

    def set_default_policy(
        self,
        policy_id: str,
        *,
        reason: str,
        actor_id: str | None,
    ) -> FileRetentionPolicyRecord:
        """把已发布策略设为当前 scope 的默认策略，不修改历史文件。"""

        existing = self.get_policy(policy_id)
        if existing.status != "published":
            raise ApiError(status.HTTP_409_CONFLICT, "conflict", "只有 published 保留策略可以设为默认。")
        normalized_reason = self._require_reason(reason)
        return self._set_default_for_scope(existing, now=utc_now(), reason=normalized_reason, actor_id=actor_id)

    def disable_policy(
        self,
        policy_id: str,
        *,
        reason: str,
        actor_id: str | None,
    ) -> FileRetentionPolicyRecord:
        """禁用 draft 或 published 策略；不删除策略历史。"""

        existing = self.get_policy(policy_id)
        if existing.status == "disabled":
            return existing
        normalized_reason = self._require_reason(reason)
        now = utc_now()
        return self.policy_repository.update_policy(
            policy_id,
            status="disabled",
            is_default=False,
            disabled_by=actor_id,
            disabled_at=now,
            reason=normalized_reason,
            updated_at=now,
        )

    def resolve_effective_policy(self, file_type: str) -> EffectiveFileRetentionPolicy:
        """按 file_type -> global -> settings fallback 顺序解析有效策略。"""

        for scope_type, scoped_file_type in (("file_type", file_type), ("global", None)):
            candidates = [
                policy
                for policy in self.list_policies()
                if policy.status == "published"
                and policy.is_default
                and policy.scope_type == scope_type
                and policy.file_type == scoped_file_type
            ]
            if candidates:
                policy = sorted(candidates, key=lambda item: (item.published_at or item.updated_at, item.policy_id))[-1]
                return EffectiveFileRetentionPolicy(
                    retention_days=policy.retention_days,
                    source="published_policy",
                    policy_id=policy.policy_id,
                    scope_type=policy.scope_type,
                    file_type=policy.file_type,
                    reason=f"policy_id={policy.policy_id}",
                )
        return EffectiveFileRetentionPolicy(
            retention_days=self.settings.oss_file_retention_days,
            source="settings_fallback",
            policy_id=None,
            scope_type=None,
            file_type=None,
            reason="settings.oss_file_retention_days",
        )

    def resolve_retention_days(self, file_type: str) -> int:
        """返回新文件应使用的保留天数，供 FileUploadService 注入使用。"""

        return self.resolve_effective_policy(file_type).retention_days

    def preview_policy_impact(
        self,
        policy_id: str,
        *,
        now: datetime | None = None,
    ) -> FileRetentionPolicyImpactReport:
        """预览策略对现有 document_files 的 expires_at 影响，不做任何写入。"""

        generated_at = _normalize_datetime(now or utc_now())
        policy = self.get_policy(policy_id)
        items: list[FileRetentionPolicyImpactItem] = []
        totals = {
            "files_seen": 0,
            "matching_files": 0,
            "currently_expired": 0,
            "would_be_expired": 0,
            "would_change_expires_at": 0,
            "deleted_files": 0,
        }
        for record in self.document_file_repository.list_document_files():
            totals["files_seen"] += 1
            if not self._matches_policy(record, policy):
                continue
            totals["matching_files"] += 1
            if record.status == "deleted":
                totals["deleted_files"] += 1
            current_expires_at = _normalize_datetime(record.expires_at) if record.expires_at else None
            projected_expires_at = _normalize_datetime(record.created_at) + timedelta(days=policy.retention_days)
            currently_expired = bool(current_expires_at and current_expires_at <= generated_at and record.status != "deleted")
            would_be_expired = projected_expires_at <= generated_at and record.status != "deleted"
            would_change = current_expires_at is None or current_expires_at != projected_expires_at
            totals["currently_expired"] += int(currently_expired)
            totals["would_be_expired"] += int(would_be_expired)
            totals["would_change_expires_at"] += int(would_change)
            items.append(
                FileRetentionPolicyImpactItem(
                    file_id=record.id,
                    job_id=record.job_id,
                    file_type=record.file_type,
                    status=record.status,
                    storage_provider=record.storage_provider,
                    current_expires_at=current_expires_at,
                    projected_expires_at=projected_expires_at,
                    currently_expired=currently_expired,
                    would_be_expired=would_be_expired,
                    would_change_expires_at=would_change,
                )
            )
        return FileRetentionPolicyImpactReport(
            generated_at=generated_at,
            policy=policy,
            totals=totals,
            items=items,
        )

    def _set_default_for_scope(
        self,
        selected: FileRetentionPolicyRecord,
        *,
        now: datetime,
        reason: str,
        actor_id: str | None,
    ) -> FileRetentionPolicyRecord:
        """把 selected 设为同 scope 唯一默认 published policy。"""

        for policy in self.list_policies():
            if policy.policy_id == selected.policy_id:
                continue
            if policy.status == "published" and policy.is_default and self._same_scope(policy, selected):
                self.policy_repository.update_policy(policy.policy_id, is_default=False, updated_at=now)
        return self.policy_repository.update_policy(
            selected.policy_id,
            is_default=True,
            reason=reason,
            published_by=selected.published_by or actor_id,
            published_at=selected.published_at or now,
            updated_at=now,
        )

    def _matches_policy(self, record: DocumentFileRecord, policy: FileRetentionPolicyRecord) -> bool:
        """判断 document_file 是否落在策略 scope 内。"""

        if policy.scope_type == "global":
            return True
        return record.file_type == policy.file_type

    def _same_scope(self, left: FileRetentionPolicyRecord, right: FileRetentionPolicyRecord) -> bool:
        """判断两个策略是否竞争同一个 effective scope。"""

        return left.scope_type == right.scope_type and left.file_type == right.file_type

    def _require_reason(self, reason: str) -> str:
        """校验治理动作 reason，空白原因会导致审计不可追踪。"""

        normalized = " ".join(reason.strip().split())
        if not normalized:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能为空。")
        if len(normalized) > 500:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "reason 不能超过 500 个字符。")
        return normalized

    def _build_policy_record(self, **payload: Any) -> FileRetentionPolicyRecord:
        """构建并校验策略记录，把 Pydantic 错误转换为 API 400。"""

        try:
            return FileRetentionPolicyRecord(**payload)
        except (ValidationError, ValueError) as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc


def _normalize_optional_text(value: str | None) -> str | None:
    """清理可选文本字段，空白字符串视为 None。"""

    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _normalize_datetime(value: datetime) -> datetime:
    """把 naive datetime 视为 UTC，避免影响比较和投影计算。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
