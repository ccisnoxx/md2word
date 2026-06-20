from __future__ import annotations

# File: app/domains/terminology/service.py
# Purpose: Enforce terminology governance package release validation and lifecycle.

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import status as http_status

from app.core.errors import ApiError
from app.domains.resources.models import ResourceVersionStatus
from app.domains.resources.service import ResourceVersionService
from app.domains.terminology.models import (
    TerminologyGovernanceFinding,
    TerminologyGovernanceValidationReport,
    TerminologyGovernanceValidationSummary,
    TerminologyReleaseAssetRef,
    TerminologyReleaseRecord,
    TerminologyReleaseScope,
    TerminologyReleaseStatus,
    utc_now,
)
from app.domains.terminology.repository import TerminologyReleaseRepositoryProtocol
from app.domains.terminology.schemas import TerminologyReleaseCreateRequest, TerminologyReleaseScopeRequest
from app.domains.translation.models import TranslationTermEntry, normalize_translation_source_term
from app.domains.translation.repository import TranslationTermRepositoryProtocol


PUBLISHABLE_TERM_STATUSES = {"publishable", "active"}
BROAD_SCOPE_VALUES = {"*", "all", "global", "any", "全部"}


@dataclass(frozen=True, slots=True)
class _TermVersionContext:
    asset: TerminologyReleaseAssetRef | None
    entries: list[TranslationTermEntry]


class TerminologyReleaseService:
    """Publish and inspect terminology governance packages."""

    def __init__(
        self,
        repository: TerminologyReleaseRepositoryProtocol,
        *,
        translation_term_repository: TranslationTermRepositoryProtocol | None,
        resource_version_service: ResourceVersionService | None,
    ) -> None:
        self.repository = repository
        self.translation_term_repository = translation_term_repository
        self.resource_version_service = resource_version_service

    def list_releases(
        self,
        *,
        status: TerminologyReleaseStatus | None = None,
        project: str | None = None,
        language_pair: str | None = None,
        content_type: str | None = None,
    ) -> list[TerminologyReleaseRecord]:
        """List releases with optional scope filters."""

        return self.repository.list_releases(
            status=status,
            project=self._normalize_optional_filter(project),
            language_pair=self._normalize_optional_filter(language_pair),
            content_type=self._normalize_optional_filter(content_type),
        )

    def get_release(self, release_id: str, version: str | None = None) -> TerminologyReleaseRecord:
        """Return one release version or raise a public not-found error."""

        record = self.repository.get_release(release_id.strip(), version.strip() if version else None)
        if record is None:
            raise ApiError(http_status.HTTP_404_NOT_FOUND, "not_found", "术语治理包发布不存在。")
        return record

    def preflight(self, request: TerminologyReleaseCreateRequest) -> TerminologyGovernanceValidationReport:
        """Run read-only release validation without persisting a release."""

        scope = self._normalize_scope(request.scope.project, request.scope.language_pair, request.scope.content_type)
        errors: list[TerminologyGovernanceFinding] = []
        warnings: list[TerminologyGovernanceFinding] = []
        conflicts: list[TerminologyGovernanceFinding] = []

        term_context = self._resolve_translation_terms(request, errors)
        rule_asset = self._resolve_rule_asset(request, errors)

        publishable_terms = [entry for entry in term_context.entries if self._is_publishable_entry(entry)]
        if term_context.asset is not None and not publishable_terms:
            errors.append(
                self._finding(
                    "error",
                    "no_publishable_terms",
                    "所选翻译术语集版本没有可发布词条，不能进入治理包。",
                    "translation_term_set",
                )
            )

        active_releases = self.repository.list_releases(status="active")
        overlapping = [record for record in active_releases if self._scopes_overlap(scope, record.scope)]
        exact_duplicates = [record for record in overlapping if record.scope == scope]
        if exact_duplicates:
            errors.append(
                self._finding(
                    "error",
                    "duplicate_scope",
                    "同一项目、语言对、内容类型下已存在生效治理包发布。",
                    "scope",
                    {"release_ids": [f"{item.id}@{item.version}" for item in exact_duplicates]},
                )
            )

        for record in overlapping:
            if record.scope == scope:
                continue
            warnings.append(
                self._finding(
                    "warning",
                    "scope_overlap",
                    "适用范围与已生效治理包存在包含或交叉关系，需要确认发布影响。",
                    "scope",
                    {"release_id": record.id, "version": record.version, "scope": record.scope.model_dump()},
                )
            )

        if term_context.entries:
            conflicts.extend(self._term_conflicts(term_context.entries, overlapping))
        if rule_asset is not None:
            conflicts.extend(self._rule_conflicts(rule_asset, overlapping))

        summary = TerminologyGovernanceValidationSummary(
            error_count=len(errors),
            warning_count=len(warnings),
            conflict_count=len(conflicts),
            publishable_term_count=len(publishable_terms),
            overlapping_release_count=len(overlapping),
        )
        blocking = bool(errors or conflicts)
        return TerminologyGovernanceValidationReport(
            valid=not blocking,
            blocking=blocking,
            summary=summary,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
        )

    def publish(self, request: TerminologyReleaseCreateRequest, *, actor_id: str | None) -> TerminologyReleaseRecord:
        """Create an active terminology governance package after blocking preflight passes."""

        report = self.preflight(request)
        if report.blocking:
            status_code = http_status.HTTP_409_CONFLICT if any(item.code == "duplicate_scope" for item in report.errors) else http_status.HTTP_400_BAD_REQUEST
            raise ApiError(status_code, "conflict" if status_code == http_status.HTTP_409_CONFLICT else "invalid_request", "术语治理包发布前校验未通过。")

        scope = self._normalize_scope(request.scope.project, request.scope.language_pair, request.scope.content_type)
        term_context = self._resolve_translation_terms(request, [])
        rule_asset = self._resolve_rule_asset(request, [])
        if term_context.asset is None or rule_asset is None:
            raise ApiError(http_status.HTTP_400_BAD_REQUEST, "invalid_request", "术语治理包引用不完整。")

        release_id = self._release_id(scope)
        now = utc_now()
        record = TerminologyReleaseRecord(
            id=release_id,
            version=self._next_version(release_id, now),
            status="active",
            scope=scope,
            translation_term_set=term_context.asset,
            term_rule_set=rule_asset,
            validation_report=report,
            release_note=self._normalize_optional_filter(request.release_note),
            source_release_id=self._normalize_optional_filter(request.source_release_id),
            source_release_version=self._normalize_optional_filter(request.source_release_version),
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            published_at=now,
        )
        return self.repository.save_release(record)

    def rollback(self, release_id: str, *, actor_id: str | None) -> TerminologyReleaseRecord:
        """Mark the latest release version as rolled back without mutating historical payloads."""

        record = self.get_release(release_id)
        if record.status != "active":
            raise ApiError(http_status.HTTP_409_CONFLICT, "conflict", "只有生效中的术语治理包可以回滚。")
        now = utc_now()
        return self.repository.save_release(
            record.model_copy(
                update={
                    "status": "rolled_back",
                    "updated_at": now,
                    "rolled_back_by": actor_id,
                    "rolled_back_at": now,
                }
            )
        )

    def copy_request(self, release_id: str, version: str | None = None) -> TerminologyReleaseCreateRequest:
        """Build a new release request prefilled from an existing release."""

        record = self.get_release(release_id, version)
        return TerminologyReleaseCreateRequest(
            translation_term_set_id=record.translation_term_set.resource_id,
            translation_term_version=record.translation_term_set.version,
            term_rule_set_id=record.term_rule_set.resource_id,
            term_rule_set_version=record.term_rule_set.version,
            scope=TerminologyReleaseScopeRequest(**record.scope.model_dump()),
            release_note=record.release_note,
            source_release_id=record.id,
            source_release_version=record.version,
        )

    def _resolve_translation_terms(
        self,
        request: TerminologyReleaseCreateRequest,
        errors: list[TerminologyGovernanceFinding],
    ) -> _TermVersionContext:
        if self.translation_term_repository is None:
            errors.append(
                self._finding("error", "translation_term_repository_unavailable", "翻译术语集版本服务不可用。", "translation_term_set")
            )
            return _TermVersionContext(None, [])

        set_id = request.translation_term_set_id.strip()
        version = request.translation_term_version.strip()
        version_record = self.translation_term_repository.get_version(set_id, version)
        if version_record is None:
            errors.append(
                self._finding("error", "invalid_translation_term_reference", "翻译术语集版本不存在。", "translation_term_set")
            )
            return _TermVersionContext(None, [])
        if version_record.status != "published":
            errors.append(
                self._finding("error", "translation_term_version_not_published", "治理包只能引用已发布的翻译术语集版本。", "translation_term_set")
            )
            return _TermVersionContext(None, [])

        entries = self.translation_term_repository.load_version(version_record.language_pair, version_record.version)
        return _TermVersionContext(
            TerminologyReleaseAssetRef(
                resource_id=version_record.set_id,
                version=version_record.version,
                snapshot_hash=version_record.snapshot_hash,
                item_count=version_record.term_count,
            ),
            entries,
        )

    def _resolve_rule_asset(
        self,
        request: TerminologyReleaseCreateRequest,
        errors: list[TerminologyGovernanceFinding],
    ) -> TerminologyReleaseAssetRef | None:
        set_id = request.term_rule_set_id.strip()
        version = request.term_rule_set_version.strip()
        if not set_id or not version:
            errors.append(self._finding("error", "missing_rule_configuration", "规则配置缺失。", "term_rule_set"))
            return None
        if self.resource_version_service is None:
            errors.append(self._finding("error", "term_rule_version_service_unavailable", "术语规则版本服务不可用。", "term_rule_set"))
            return None
        record = self.resource_version_service.repository.get_resource_version("term_rule_set", set_id, version)
        if record is None:
            errors.append(self._finding("error", "invalid_term_rule_reference", "术语规则配置版本不存在。", "term_rule_set"))
            return None
        if record.status != ResourceVersionStatus.PUBLISHED:
            errors.append(
                self._finding("error", "term_rule_version_not_published", "治理包只能引用已发布的术语规则配置。", "term_rule_set")
            )
            return None
        payload = record.payload or {}
        rule_count = payload.get("rule_count") if isinstance(payload.get("rule_count"), int) else None
        return TerminologyReleaseAssetRef(
            resource_id=record.resource_id,
            version=record.version,
            snapshot_hash=record.snapshot_hash,
            item_count=rule_count,
        )

    def _term_conflicts(
        self,
        entries: list[TranslationTermEntry],
        overlapping: list[TerminologyReleaseRecord],
    ) -> list[TerminologyGovernanceFinding]:
        conflicts: list[TerminologyGovernanceFinding] = []
        current_by_key = {self._entry_key(entry): entry for entry in entries if self._is_publishable_entry(entry)}
        if not current_by_key or self.translation_term_repository is None:
            return conflicts
        for release in overlapping:
            existing_entries = self._load_release_terms(release)
            existing_by_key = {
                self._entry_key(entry): entry
                for entry in existing_entries
                if self._is_publishable_entry(entry)
            }
            for key, current in current_by_key.items():
                existing = existing_by_key.get(key)
                if existing is None:
                    continue
                current_recommended = set(self._recommended_translations(current))
                existing_recommended = set(self._recommended_translations(existing))
                if current_recommended and existing_recommended and current_recommended != existing_recommended:
                    conflicts.append(
                        self._finding(
                            "conflict",
                            "recommended_translation_conflict",
                            "同一术语在交叉范围内存在不同推荐译法。",
                            "translation_term_set",
                            {
                                "normalized_source_term": key,
                                "release_id": release.id,
                                "release_version": release.version,
                                "current_recommended": sorted(current_recommended),
                                "existing_recommended": sorted(existing_recommended),
                            },
                        )
                    )
                current_forbidden = set(self._forbidden_translations(current))
                existing_forbidden = set(self._forbidden_translations(existing))
                if current_forbidden.intersection(existing_recommended) or existing_forbidden.intersection(current_recommended):
                    conflicts.append(
                        self._finding(
                            "conflict",
                            "forbidden_term_conflict",
                            "交叉范围内的推荐译法命中了另一治理包的禁用译法。",
                            "translation_term_set",
                            {
                                "normalized_source_term": key,
                                "release_id": release.id,
                                "release_version": release.version,
                            },
                        )
                    )
        return conflicts

    def _rule_conflicts(
        self,
        rule_asset: TerminologyReleaseAssetRef,
        overlapping: list[TerminologyReleaseRecord],
    ) -> list[TerminologyGovernanceFinding]:
        conflicts: list[TerminologyGovernanceFinding] = []
        for release in overlapping:
            if (
                release.term_rule_set.resource_id == rule_asset.resource_id
                and release.term_rule_set.version == rule_asset.version
            ):
                continue
            conflicts.append(
                self._finding(
                    "conflict",
                    "rule_configuration_overlap",
                    "交叉范围内已有不同术语规则配置，需处理规则互斥风险。",
                    "term_rule_set",
                    {
                        "release_id": release.id,
                        "release_version": release.version,
                        "existing_rule_set": release.term_rule_set.model_dump(),
                        "current_rule_set": rule_asset.model_dump(),
                    },
                )
            )
        return conflicts

    def _load_release_terms(self, release: TerminologyReleaseRecord) -> list[TranslationTermEntry]:
        if self.translation_term_repository is None:
            return []
        term_set = self.translation_term_repository.get_set(release.translation_term_set.resource_id)
        if term_set is None:
            return []
        return self.translation_term_repository.load_version(term_set.language_pair, release.translation_term_set.version)

    @staticmethod
    def _is_publishable_entry(entry: TranslationTermEntry) -> bool:
        return str(entry.status).strip().lower() in PUBLISHABLE_TERM_STATUSES

    @staticmethod
    def _entry_key(entry: TranslationTermEntry) -> str:
        return entry.normalized_source_term or normalize_translation_source_term(entry.source_term)

    @staticmethod
    def _recommended_translations(entry: TranslationTermEntry) -> list[str]:
        raw = getattr(entry, "recommended_translations", None)
        if isinstance(raw, (list, tuple)):
            values = [str(item).strip() for item in raw]
        else:
            values = [str(entry.target_term).strip()]
        normalized = sorted({value for value in values if value})
        if normalized:
            return normalized
        return [str(entry.target_term).strip()] if str(entry.target_term).strip() else []

    @staticmethod
    def _forbidden_translations(entry: TranslationTermEntry) -> list[str]:
        raw = getattr(entry, "forbidden_translations", None)
        if not isinstance(raw, (list, tuple)):
            return []
        return sorted({str(item).strip() for item in raw if str(item).strip()})

    def _next_version(self, release_id: str, now: datetime) -> str:
        prefix = now.strftime("%Y.%m.%d")
        existing = [
            record.version
            for record in self.repository.list_releases()
            if record.id == release_id and record.version.startswith(prefix)
        ]
        suffixes: list[int] = []
        for version in existing:
            _, _, suffix = version.partition("-")
            if suffix.isdigit():
                suffixes.append(int(suffix))
        return f"{prefix}-{max(suffixes, default=0) + 1}"

    @staticmethod
    def _release_id(scope: TerminologyReleaseScope) -> str:
        raw = f"{scope.project}-{scope.language_pair}-{scope.content_type}".lower()
        slug = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-")
        return f"term-governance-{slug or 'global'}"

    @staticmethod
    def _normalize_scope(project: str, language_pair: str, content_type: str) -> TerminologyReleaseScope:
        return TerminologyReleaseScope(
            project=TerminologyReleaseService._normalize_scope_value(project),
            language_pair=TerminologyReleaseService._normalize_scope_value(language_pair),
            content_type=TerminologyReleaseService._normalize_scope_value(content_type),
        )

    @staticmethod
    def _normalize_scope_value(value: str) -> str:
        normalized = " ".join(value.strip().split())
        if normalized.lower() in BROAD_SCOPE_VALUES:
            return "*"
        return normalized

    @staticmethod
    def _normalize_optional_filter(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _scopes_overlap(left: TerminologyReleaseScope, right: TerminologyReleaseScope) -> bool:
        return all(
            TerminologyReleaseService._scope_part_overlaps(left_value, right_value)
            for left_value, right_value in (
                (left.project, right.project),
                (left.language_pair, right.language_pair),
                (left.content_type, right.content_type),
            )
        )

    @staticmethod
    def _scope_part_overlaps(left: str, right: str) -> bool:
        return left == right or left == "*" or right == "*"

    @staticmethod
    def _finding(
        severity: str,
        code: str,
        message: str,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TerminologyGovernanceFinding:
        return TerminologyGovernanceFinding(
            severity=severity,  # type: ignore[arg-type]
            code=code,
            message=message,
            path=path,
            metadata=metadata or {},
        )
