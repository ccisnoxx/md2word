from __future__ import annotations

# app/domains/jobs/resource_snapshots.py: 解析和物化 job 创建时绑定的资源版本快照。

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.conversion.runtime import translation_runtime
from app.core.config import Settings
from app.domains.jobs.models import (
    ConversionOptions,
    JobMineruSnapshot,
    JobRecord,
    JobResourceSnapshot,
    ResolvedTranslationTermVersion,
)
from app.domains.jobs.paths import JobPaths
from app.domains.resources.models import ResolvedResourceVersion, ResourceType, ResourceVersionRecord, ResourceVersionStatus
from app.domains.term_rules.models import TermRulesStore
from app.domains.translation.models import TermVersionSnapshot, TranslationProfileSnapshot
from app.domains.translation.modes import (
    TRANSLATION_MODE_SPECS,
    derive_translation_term_set_id,
    is_translation_mode,
    spec_for_language_pair,
    spec_for_translation_mode,
)
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.yaml_codec import TermRuleYamlCodec
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.translation.repository import TranslationTermRepositoryProtocol


SourceKind = Literal["mineru_package", "source_pdf"]


class JobResourceSnapshotError(RuntimeError):
    """资源快照解析或物化失败，可映射为 HTTP 或 stage failure。"""

    def __init__(self, message: str, *, status_code: int = 400, code: str = "resource_snapshot_invalid") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True, slots=True)
class MaterializedJobResources:
    template_path: Path | None
    layout_config_path: Path | None
    subscript_config_path: Path | None
    translation_profile: TranslationProfileSnapshot | None
    translation_term_version: TermVersionSnapshot | None


class JobResourceSnapshotService:
    """创建 job resource snapshot；无 resource service 时守住 legacy 兼容路径。"""

    def __init__(
        self,
        settings: Settings,
        resource_version_service: ResourceVersionService | None,
        translation_term_repository: TranslationTermRepositoryProtocol | None = None,
    ) -> None:
        self.settings = settings
        self.resource_version_service = resource_version_service
        self.translation_term_repository = translation_term_repository
        self.term_rule_yaml_codec = TermRuleYamlCodec()

    def build_snapshot(
        self,
        *,
        options: ConversionOptions,
        source_kind: SourceKind,
        job_id: str,
        allow_draft_template: bool = False,
    ) -> JobResourceSnapshot | None:
        if self.resource_version_service is None:
            self._ensure_no_versioned_selection(options)
            return None

        template_id = self._optional_text(options.template_id) or self.settings.default_template_id
        template = self._resolve_resource(
            resource_type="template",
            resource_id=template_id,
            version=options.template_version,
            default_missing_status=409,
            allow_draft=allow_draft_template,
        )
        term_rule_set_id = self._optional_text(options.term_rule_set_id) or DEFAULT_TERM_RULE_SET_ID
        term_rule_set = self._resolve_resource(
            resource_type="term_rule_set",
            resource_id=term_rule_set_id,
            version=options.term_rule_set_version,
            default_missing_status=409,
        )
        translation_term_set = self._resolve_translation_term_set(options)
        translation_profile = self._resolve_translation_profile(options)
        return JobResourceSnapshot(
            template=template,
            term_rule_set=term_rule_set,
            term_rule_department_id=self._optional_text(options.term_rule_department_id),
            translation_term_set=translation_term_set,
            translation_profile=translation_profile,
            mineru=self._build_mineru_snapshot(source_kind=source_kind, job_id=job_id, options=options),
            artifact_ids={"source": "source_pdf" if source_kind == "source_pdf" else "source_package"},
        )

    def rebind_term_assets(
        self,
        *,
        job: JobRecord,
        options: ConversionOptions,
        use_latest_defaults: bool,
    ) -> JobResourceSnapshot | None:
        """为 retry 重绑术语资产；默认路径保留原 job snapshot。"""

        if not use_latest_defaults and not self._has_term_asset_selection(options):
            return job.resource_snapshot
        if job.resource_snapshot is None:
            return self.build_snapshot(options=options, source_kind=job.source_kind, job_id=job.id)
        if self.resource_version_service is None:
            self._ensure_no_versioned_selection(options)
            return job.resource_snapshot

        next_term_rule_set = job.resource_snapshot.term_rule_set
        if use_latest_defaults or self._has_term_rule_selection(options):
            term_rule_set_id = (
                self._optional_text(options.term_rule_set_id)
                or (job.resource_snapshot.term_rule_set.resource_id if job.resource_snapshot.term_rule_set is not None else None)
                or DEFAULT_TERM_RULE_SET_ID
            )
            next_term_rule_set = self._resolve_resource(
                resource_type="term_rule_set",
                resource_id=term_rule_set_id,
                version=self._optional_text(options.term_rule_set_version) if not use_latest_defaults else None,
                default_missing_status=409,
            )

        next_translation_term_set = job.resource_snapshot.translation_term_set
        if use_latest_defaults or self._has_translation_term_selection(options):
            next_translation_term_set = self._resolve_translation_term_set(options, use_default_version=use_latest_defaults)

        return job.resource_snapshot.model_copy(
            update={
                "term_rule_set": next_term_rule_set,
                "term_rule_department_id": self._optional_text(options.term_rule_department_id) or job.resource_snapshot.term_rule_department_id,
                "translation_term_set": next_translation_term_set,
            }
        )

    def materialize(self, job: JobRecord, job_paths: JobPaths) -> MaterializedJobResources:
        snapshot = job.resource_snapshot
        if snapshot is None:
            return MaterializedJobResources(
                template_path=None,
                layout_config_path=None,
                subscript_config_path=None,
                translation_profile=None,
                translation_term_version=None,
            )
        if self.resource_version_service is None:
            raise JobResourceSnapshotError(
                "当前 runtime 缺少 resource version service，无法物化 job resource snapshot。",
                status_code=503,
                code="resource_snapshot_unavailable",
            )
        if snapshot.template is None:
            raise JobResourceSnapshotError(
                "job resource snapshot 缺少 Template Version。",
                status_code=409,
                code="resource_snapshot_missing_template",
            )
        if snapshot.term_rule_set is None:
            raise JobResourceSnapshotError(
                "job resource snapshot 缺少 Term Rule Version。",
                status_code=409,
                code="resource_snapshot_missing_term_rule_set",
            )
        template_path = self._materialize_template(snapshot.template)
        layout_config_path = self._materialize_template_layout_config(snapshot.template)
        subscript_config_path = self._materialize_term_rule_set(
            snapshot.term_rule_set,
            job_paths,
            department_id=snapshot.term_rule_department_id,
        )
        translation_profile = (
            self._materialize_translation_profile(snapshot.translation_profile)
            if is_translation_mode(job.translation_mode)
            else None
        )
        translation_term_version = (
            self._materialize_translation_term_set(snapshot.translation_term_set)
            if is_translation_mode(job.translation_mode)
            else None
        )
        spec = spec_for_translation_mode(job.translation_mode)
        if is_translation_mode(job.translation_mode) and translation_profile is None:
            raise JobResourceSnapshotError(
                "翻译任务缺少 Translation Profile 快照。",
                status_code=409,
                code="resource_snapshot_missing_translation_profile",
            )
        if is_translation_mode(job.translation_mode) and translation_term_version is None:
            raise JobResourceSnapshotError(
                "翻译任务缺少 Translation Term Set 快照。",
                status_code=409,
                code="resource_snapshot_missing_translation_term_set",
            )
        if spec.language_pair is not None and translation_profile is not None and translation_profile.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Profile language_pair 不匹配: expected={spec.language_pair} actual={translation_profile.language_pair}",
                status_code=400,
                code="translation_profile_language_pair_mismatch",
            )
        if spec.language_pair is not None and translation_term_version is not None and translation_term_version.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Term Set language_pair 不匹配: expected={spec.language_pair} actual={translation_term_version.language_pair}",
                status_code=400,
                code="translation_term_set_language_pair_mismatch",
            )
        return MaterializedJobResources(
            template_path=template_path,
            layout_config_path=layout_config_path,
            subscript_config_path=subscript_config_path,
            translation_profile=translation_profile,
            translation_term_version=translation_term_version,
        )

    def _resolve_translation_profile(self, options: ConversionOptions) -> ResolvedResourceVersion | None:
        has_translation_selection = any(
            self._optional_text(value)
            for value in (options.translation_profile_id, options.translation_profile_version)
        )
        spec = spec_for_translation_mode(options.translation_mode)
        if not spec.is_translation:
            if has_translation_selection:
                raise JobResourceSnapshotError("direct 任务不能绑定 Translation Profile。", status_code=400)
            return None
        profile_id = self._optional_text(options.translation_profile_id) or spec.default_profile_id
        if profile_id is None:
            raise JobResourceSnapshotError(
                f"{options.translation_mode} 缺少默认 Translation Profile。",
                status_code=409,
                code="translation_profile_default_missing",
            )
        resolved = self._resolve_resource(
            resource_type="translation_profile",
            resource_id=profile_id,
            version=options.translation_profile_version,
            default_missing_status=409,
        )
        if spec.language_pair is not None:
            record = self._load_snapshot_record(resolved)
            actual_language_pair = self._profile_language_pair(record.resource_id, record.payload or {})
            if actual_language_pair != spec.language_pair:
                raise JobResourceSnapshotError(
                    f"Translation Profile language_pair 不匹配: expected={spec.language_pair} actual={actual_language_pair}",
                    status_code=400,
                    code="translation_profile_language_pair_mismatch",
                )
        return resolved

    def _resolve_translation_term_set(
        self,
        options: ConversionOptions,
        *,
        use_default_version: bool = False,
    ) -> ResolvedTranslationTermVersion | None:
        has_translation_term_selection = self._has_translation_term_selection(options)
        spec = spec_for_translation_mode(options.translation_mode)
        if not spec.is_translation:
            if has_translation_term_selection:
                raise JobResourceSnapshotError("direct 任务不能绑定 Translation Term Set。", status_code=400)
            return None
        set_id = self._optional_text(options.translation_term_set_id) or spec.default_term_set_id
        if set_id is None:
            raise JobResourceSnapshotError(
                f"{options.translation_mode} 缺少默认 Translation Term Set。",
                status_code=409,
                code="translation_term_set_default_missing",
            )
        version = None if use_default_version else self._optional_text(options.translation_term_version)
        resolved = self._resolve_translation_term_version(
            set_id=set_id,
            version=version,
            default_missing_status=409,
        )
        if spec.language_pair is not None and resolved.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Term Set language_pair 不匹配: expected={spec.language_pair} actual={resolved.language_pair}",
                status_code=400,
                code="translation_term_set_language_pair_mismatch",
            )
        return resolved

    def _resolve_translation_term_version(
        self,
        *,
        set_id: str,
        version: str | None,
        default_missing_status: int,
    ) -> ResolvedTranslationTermVersion:
        if self.translation_term_repository is None:
            raise JobResourceSnapshotError(
                "Translation Term Set 绑定需要 JOBS_REPOSITORY_BACKEND=mysql。",
                status_code=503,
                code="translation_term_set_unavailable",
            )
        term_set = self.translation_term_repository.get_set(set_id)
        if term_set is None:
            status_code = 404 if version is not None else default_missing_status
            raise JobResourceSnapshotError(
                f"Translation Term Set 不存在: {set_id}",
                status_code=status_code,
                code="translation_term_set_not_found",
            )
        resolved_version = version or term_set.default_version
        if not resolved_version:
            raise JobResourceSnapshotError(
                f"Translation Term Set 缺少默认版本: {set_id}",
                status_code=default_missing_status,
                code="translation_term_set_default_missing",
            )
        version_record = self.translation_term_repository.get_version(term_set.set_id, resolved_version)
        if version_record is None:
            status_code = 404 if version is not None else default_missing_status
            raise JobResourceSnapshotError(
                f"Translation Term Set 版本不存在: {term_set.set_id}@{resolved_version}",
                status_code=status_code,
                code="translation_term_version_not_found",
            )
        if version_record.status != "published":
            raise JobResourceSnapshotError(
                "只能绑定 published Translation Term Set 版本。",
                status_code=400,
                code="translation_term_version_not_published",
            )
        return ResolvedTranslationTermVersion(
            set_id=version_record.set_id,
            language_pair=version_record.language_pair,
            version=version_record.version,
            snapshot_hash=version_record.snapshot_hash,
            term_count=version_record.term_count,
        )

    def _resolve_resource(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
        version: str | None,
        default_missing_status: int,
        allow_draft: bool = False,
    ) -> ResolvedResourceVersion:
        if self.resource_version_service is None:
            raise JobResourceSnapshotError("资源版本快照需要 JOBS_REPOSITORY_BACKEND=mysql。", status_code=503)
        normalized_version = self._optional_text(version)
        try:
            if normalized_version is not None:
                return self.resource_version_service.resolve_version(
                    resource_type,
                    resource_id,
                    normalized_version,
                    allow_draft=allow_draft,
                )
            return self.resource_version_service.resolve_default(resource_type, resource_id)
        except FileNotFoundError as exc:
            status_code = 404 if normalized_version is not None else default_missing_status
            raise JobResourceSnapshotError(str(exc), status_code=status_code, code="resource_snapshot_not_found") from exc
        except ValueError as exc:
            raise JobResourceSnapshotError(str(exc), status_code=400) from exc

    def _build_mineru_snapshot(
        self,
        *,
        source_kind: SourceKind,
        job_id: str,
        options: ConversionOptions,
    ) -> JobMineruSnapshot:
        spec = spec_for_translation_mode(options.translation_mode)
        return JobMineruSnapshot(
            model_version=self.settings.mineru_model_version if source_kind == "source_pdf" else None,
            language=(spec.mineru_language or self.settings.mineru_language) if source_kind == "source_pdf" else None,
            enable_formula=self.settings.mineru_enable_formula if source_kind == "source_pdf" else None,
            enable_table=self.settings.mineru_enable_table if source_kind == "source_pdf" else None,
            callback_enabled=source_kind == "source_pdf" and bool(self.settings.mineru_callback_url),
            data_id=job_id if source_kind == "source_pdf" else None,
        )

    def _materialize_template(self, snapshot: ResolvedResourceVersion | None) -> Path | None:
        if snapshot is None:
            return None
        record = self._load_snapshot_record(snapshot)
        payload = record.payload or {}
        docx_path = self._payload_text(payload, "docx_path")
        if docx_path is None:
            raise JobResourceSnapshotError("Template Version payload 缺少 docx_path。", status_code=409)
        resolved = self._resolve_payload_path(docx_path)
        if not resolved.exists() or not resolved.is_file():
            raise JobResourceSnapshotError(f"Template Version 文件不存在: {docx_path}", status_code=409)
        return resolved

    def _materialize_template_layout_config(self, snapshot: ResolvedResourceVersion | None) -> Path | None:
        """返回 Template Version 绑定的版式 YAML；缺省时交给全局默认配置兜底。"""

        if snapshot is None:
            return None
        record = self._load_snapshot_record(snapshot)
        payload = record.payload or {}
        layout_config_path = self._payload_text(payload, "layout_config_path")
        if layout_config_path is None:
            return None
        resolved = self._resolve_payload_path(layout_config_path)
        if not resolved.exists() or not resolved.is_file():
            raise JobResourceSnapshotError(f"Template Version 版式配置不存在: {layout_config_path}", status_code=409)
        return resolved

    def _materialize_term_rule_set(
        self,
        snapshot: ResolvedResourceVersion | None,
        job_paths: JobPaths,
        *,
        department_id: str | None,
    ) -> Path | None:
        if snapshot is None:
            return None
        record = self._load_snapshot_record(snapshot)
        payload = record.payload or {}
        store_payload = payload.get("store")
        if not isinstance(store_payload, dict):
            raise JobResourceSnapshotError("Term Rule Version payload 缺少 store。", status_code=409)
        store = TermRulesStore.model_validate(store_payload)
        job_paths.resource_subscript_config.parent.mkdir(parents=True, exist_ok=True)
        job_paths.resource_subscript_config.write_text(
            self.term_rule_yaml_codec.dump_legacy_runtime_yaml(store, department_id=department_id),
            encoding="utf-8",
        )
        return job_paths.resource_subscript_config

    def _materialize_translation_profile(
        self,
        snapshot: ResolvedResourceVersion | None,
    ) -> TranslationProfileSnapshot | None:
        if snapshot is None:
            return None
        record = self._load_snapshot_record(snapshot)
        payload = record.payload or {}
        return TranslationProfileSnapshot(
            translation_profile_id=record.resource_id,
            language_pair=self._profile_language_pair(record.resource_id, payload),
            version=record.version,
            snapshot_hash=record.snapshot_hash,
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
        )

    def _materialize_translation_term_set(
        self,
        snapshot: ResolvedTranslationTermVersion | None,
    ) -> TermVersionSnapshot | None:
        if snapshot is None:
            return None
        if self.translation_term_repository is None:
            raise JobResourceSnapshotError(
                "当前 stage runtime 缺少 Translation Term Set repository。",
                status_code=503,
                code="translation_term_set_unavailable",
            )
        record = self.translation_term_repository.get_version(snapshot.set_id, snapshot.version)
        if record is None:
            raise JobResourceSnapshotError(
                f"资源快照指向的 Translation Term Set 版本不存在: {snapshot.set_id}@{snapshot.version}",
                status_code=409,
                code="translation_term_version_not_found",
            )
        if record.status != "published":
            raise JobResourceSnapshotError(
                f"资源快照指向了非 published Translation Term Set 版本: {snapshot.set_id}@{snapshot.version}",
                status_code=409,
                code="translation_term_version_invalid_status",
            )
        if record.snapshot_hash != snapshot.snapshot_hash:
            raise JobResourceSnapshotError(
                f"Translation Term Set 快照 hash 不匹配: {snapshot.set_id}@{snapshot.version}",
                status_code=409,
                code="translation_term_snapshot_hash_mismatch",
            )
        entries = self.translation_term_repository.load_version(snapshot.language_pair, snapshot.version)
        return TermVersionSnapshot(
            term_version_id=f"{snapshot.language_pair}@{snapshot.version}",
            language_pair=snapshot.language_pair,
            version=snapshot.version,
            snapshot_hash=snapshot.snapshot_hash,
            entries=tuple(entries),
        )

    def _profile_language_pair(self, translation_profile_id: str, payload: dict[str, object]) -> str:
        payload_language_pair = self._payload_text(payload, "language_pair")
        if payload_language_pair is not None:
            spec_for_language_pair(payload_language_pair)
            return payload_language_pair
        for spec in TRANSLATION_MODE_SPECS.values():
            if spec.default_profile_id == translation_profile_id and spec.language_pair is not None:
                return spec.language_pair
        return "en2zh"

    def _load_snapshot_record(self, snapshot: ResolvedResourceVersion) -> ResourceVersionRecord:
        if self.resource_version_service is None:
            raise JobResourceSnapshotError("资源版本服务不可用。", status_code=503, code="resource_snapshot_unavailable")
        record = self.resource_version_service.repository.get_resource_version(
            snapshot.resource_type,
            snapshot.resource_id,
            snapshot.version,
        )
        if record is None:
            raise JobResourceSnapshotError(
                f"资源快照指向的版本不存在: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                status_code=409,
                code="resource_snapshot_not_found",
            )
        draft_template_is_authorized = (
            record.status == ResourceVersionStatus.DRAFT
            and snapshot.resource_type == "template"
            and snapshot.status == "draft"
        )
        if record.status == ResourceVersionStatus.DRAFT and not draft_template_is_authorized:
            raise JobResourceSnapshotError(
                f"资源快照指向了 draft 版本: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                status_code=409,
                code="resource_snapshot_invalid_status",
            )
        if record.snapshot_hash != snapshot.snapshot_hash:
            raise JobResourceSnapshotError(
                f"资源快照 hash 不匹配: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                status_code=409,
                code="resource_snapshot_hash_mismatch",
            )
        if record.payload is None:
            raise JobResourceSnapshotError(
                f"资源版本 payload 缺失: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                status_code=409,
                code="resource_snapshot_payload_missing",
            )
        return record

    def _resolve_payload_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path.resolve()
        return (self.settings.root_dir / path).resolve()

    def _ensure_no_versioned_selection(self, options: ConversionOptions) -> None:
        forbidden = {
            "template_version": options.template_version,
            "term_rule_set_id": options.term_rule_set_id,
            "term_rule_set_version": options.term_rule_set_version,
            "translation_term_set_id": options.translation_term_set_id,
            "translation_term_version": options.translation_term_version,
            "translation_profile_id": options.translation_profile_id,
            "translation_profile_version": options.translation_profile_version,
        }
        selected = [name for name, value in forbidden.items() if self._optional_text(value)]
        if selected:
            joined = ", ".join(selected)
            raise JobResourceSnapshotError(
                f"{joined} 需要 JOBS_REPOSITORY_BACKEND=mysql 才能绑定资源版本快照。",
                status_code=503,
                code="resource_snapshot_unavailable",
            )

    @staticmethod
    def _has_term_asset_selection(options: ConversionOptions) -> bool:
        return JobResourceSnapshotService._has_term_rule_selection(options) or JobResourceSnapshotService._has_translation_term_selection(options)

    @staticmethod
    def _has_term_rule_selection(options: ConversionOptions) -> bool:
        return any(
            JobResourceSnapshotService._optional_text(value)
            for value in (options.term_rule_set_id, options.term_rule_set_version, options.term_rule_department_id)
        )

    @staticmethod
    def _has_translation_term_selection(options: ConversionOptions) -> bool:
        return any(
            JobResourceSnapshotService._optional_text(value)
            for value in (options.translation_term_set_id, options.translation_term_version)
        )

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _payload_text(payload: dict, key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _payload_int(payload: dict, key: str, default: int) -> int:
        value = payload.get(key)
        return int(value) if isinstance(value, (int, str)) and str(value).isdigit() else max(int(default), 1)
