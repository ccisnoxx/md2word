from __future__ import annotations

# app/domains/jobs/resource_snapshots.py: 解析和物化 job 创建时绑定的资源版本快照。

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.conversion.runtime import translation_runtime
from app.core.config import Settings
from app.domains.jobs.models import ConversionOptions, JobMineruSnapshot, JobRecord, JobResourceSnapshot
from app.domains.jobs.paths import JobPaths
from app.domains.resources.models import ResolvedResourceVersion, ResourceType, ResourceVersionRecord, ResourceVersionStatus
from app.domains.term_rules.models import TermRulesStore
from app.domains.translation.models import TranslationProfileSnapshot
from app.domains.resources.service import ResourceVersionService
from app.domains.term_rules.yaml_codec import TermRuleYamlCodec
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.translation.profiles_service import DEFAULT_TRANSLATION_PROFILE_ID


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
    subscript_config_path: Path | None
    translation_profile: TranslationProfileSnapshot | None


class JobResourceSnapshotService:
    """创建 job resource snapshot；无 resource service 时守住 legacy 兼容路径。"""

    def __init__(
        self,
        settings: Settings,
        resource_version_service: ResourceVersionService | None,
    ) -> None:
        self.settings = settings
        self.resource_version_service = resource_version_service
        self.term_rule_yaml_codec = TermRuleYamlCodec()

    def build_snapshot(
        self,
        *,
        options: ConversionOptions,
        source_kind: SourceKind,
        job_id: str,
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
        )
        term_rule_set_id = self._optional_text(options.term_rule_set_id) or DEFAULT_TERM_RULE_SET_ID
        term_rule_set = self._resolve_resource(
            resource_type="term_rule_set",
            resource_id=term_rule_set_id,
            version=options.term_rule_set_version,
            default_missing_status=409,
        )
        translation_profile = self._resolve_translation_profile(options)
        return JobResourceSnapshot(
            template=template,
            term_rule_set=term_rule_set,
            translation_profile=translation_profile,
            mineru=self._build_mineru_snapshot(source_kind=source_kind, job_id=job_id),
            artifact_ids={"source": "source_pdf" if source_kind == "source_pdf" else "source_package"},
        )

    def materialize(self, job: JobRecord, job_paths: JobPaths) -> MaterializedJobResources:
        snapshot = job.resource_snapshot
        if snapshot is None:
            return MaterializedJobResources(template_path=None, subscript_config_path=None, translation_profile=None)
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
        subscript_config_path = self._materialize_term_rule_set(snapshot.term_rule_set, job_paths)
        translation_profile = (
            self._materialize_translation_profile(snapshot.translation_profile)
            if job.translation_mode == "en2zh"
            else None
        )
        if job.translation_mode == "en2zh" and translation_profile is None:
            raise JobResourceSnapshotError(
                "en2zh 任务缺少 Translation Profile 快照。",
                status_code=409,
                code="resource_snapshot_missing_translation_profile",
            )
        return MaterializedJobResources(
            template_path=template_path,
            subscript_config_path=subscript_config_path,
            translation_profile=translation_profile,
        )

    def _resolve_translation_profile(self, options: ConversionOptions) -> ResolvedResourceVersion | None:
        has_translation_selection = any(
            self._optional_text(value)
            for value in (options.translation_profile_id, options.translation_profile_version)
        )
        if options.translation_mode != "en2zh":
            if has_translation_selection:
                raise JobResourceSnapshotError("direct 任务不能绑定 Translation Profile。", status_code=400)
            return None
        profile_id = self._optional_text(options.translation_profile_id) or DEFAULT_TRANSLATION_PROFILE_ID
        return self._resolve_resource(
            resource_type="translation_profile",
            resource_id=profile_id,
            version=options.translation_profile_version,
            default_missing_status=409,
        )

    def _resolve_resource(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
        version: str | None,
        default_missing_status: int,
    ) -> ResolvedResourceVersion:
        if self.resource_version_service is None:
            raise JobResourceSnapshotError("资源版本快照需要 JOBS_REPOSITORY_BACKEND=mysql。", status_code=503)
        normalized_version = self._optional_text(version)
        try:
            if normalized_version is not None:
                return self.resource_version_service.resolve_version(resource_type, resource_id, normalized_version)
            return self.resource_version_service.resolve_default(resource_type, resource_id)
        except FileNotFoundError as exc:
            status_code = 404 if normalized_version is not None else default_missing_status
            raise JobResourceSnapshotError(str(exc), status_code=status_code, code="resource_snapshot_not_found") from exc
        except ValueError as exc:
            raise JobResourceSnapshotError(str(exc), status_code=400) from exc

    def _build_mineru_snapshot(self, *, source_kind: SourceKind, job_id: str) -> JobMineruSnapshot:
        return JobMineruSnapshot(
            model_version=self.settings.mineru_model_version if source_kind == "source_pdf" else None,
            language=self.settings.mineru_language if source_kind == "source_pdf" else None,
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

    def _materialize_term_rule_set(
        self,
        snapshot: ResolvedResourceVersion | None,
        job_paths: JobPaths,
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
            self.term_rule_yaml_codec.dump_legacy_runtime_yaml(store),
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
            version=record.version,
            snapshot_hash=record.snapshot_hash,
            target_language=self._payload_text(payload, "target_language") or translation_runtime.DEFAULT_TARGET_LANGUAGE,
            domain=self._payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=self._payload_text(payload, "prompt_version") or translation_runtime.TRANSLATION_PROMPT_VERSION,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(payload, "max_pages_per_batch", self.settings.translation_max_pages),
            max_chars_per_batch=self._payload_int(payload, "max_chars_per_batch", self.settings.translation_max_chars),
        )

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
        if record.status == ResourceVersionStatus.DRAFT:
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
