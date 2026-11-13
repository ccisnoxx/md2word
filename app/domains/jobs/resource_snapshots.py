from __future__ import annotations

# app/domains/jobs/resource_snapshots.py: 解析和物化 job 创建时绑定的资源版本快照。

import os
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from app.core.config import Settings
from app.core.errors import ApplicationErrorCode
from app.domains.jobs.models import (
    ConversionOptions,
    JobMineruSnapshot,
    JobRecord,
    JobResourceSnapshot,
    ResolvedTranslationTermVersion,
)
from app.domains.jobs.paths import JobPaths
from app.domains.resources.integrity import content_sha256, resource_payload_sha256
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
from app.domains.translation.profiles_service import (
    translation_profile_snapshot_from_record,
)


SourceKind = Literal["mineru_package", "source_pdf"]


class JobResourceSnapshotError(RuntimeError):
    """资源快照解析或物化失败，可映射为 API 错误或 stage failure。

    code 是对外稳定的具体错误码；category 是语义类别，HTTP 状态由 app/core/errors 的中央映射决定，
    本领域不选择 HTTP 状态。
    """

    def __init__(self, message: str, *, category: ApplicationErrorCode = "invalid_request",
                 code: str = "resource_snapshot_invalid") -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.code = code


@dataclass(frozen=True, slots=True)
class MaterializedJobResources:
    template_path: Path | None
    layout_config_path: Path | None
    subscript_config_path: Path | None
    translation_profile: TranslationProfileSnapshot | None
    translation_term_version: TermVersionSnapshot | None


@dataclass(frozen=True, slots=True)
class MaterializedRenderResources:
    """本次从任务目录回读并验证的实物及其原版式资产目录。"""

    template_path: Path
    layout_config_path: Path | None
    subscript_config_path: Path
    layout_asset_dir: Path | None
    template_content: bytes = field(repr=False)
    layout_config_content: bytes | None = field(repr=False)
    subscript_content: bytes = field(repr=False)
    publishable: bool


# 发布追加审计字段，原 draft 验证任务仍以自己的 payload 身份核验实物。
_TEMPLATE_PUBLICATION_FIELDS = frozenset({
    "verification_job_id", "verification_note", "verified_by", "verified_at",
    "publish_reason", "published_by", "published_at",
})


def _verify_resource_bytes(content: bytes, expected_sha256: str, code: str) -> None:
    if content_sha256(content) != expected_sha256:
        raise JobResourceSnapshotError("任务资源的内容 SHA-256 不匹配。", category="conflict", code=code)


def _materialize_verified_file(
    destination: Path, *, expected_sha256: str, hash_error: str,
    source: Path | None = None, content: bytes | None = None,
) -> bytes:
    """已存在的副本先认证；相同资源的并发发布只会写入同一份已认证内容。"""

    try:
        try:
            cached = destination.read_bytes()
        except FileNotFoundError:
            cached = None
        if cached is not None:
            _verify_resource_bytes(cached, expected_sha256, hash_error)
            return cached
        if source is not None:
            try:
                content = source.read_bytes()
            except OSError:
                raise JobResourceSnapshotError(
                    "任务绑定的资源文件不可读取。", category="conflict", code="resource_snapshot_file_unavailable",
                ) from None
        assert content is not None
        _verify_resource_bytes(content, expected_sha256, hash_error)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=destination.parent, prefix=".resource-", delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                handle.close()
                try:
                    cached = destination.read_bytes()
                except FileNotFoundError:
                    temporary.replace(destination)
                    cached = destination.read_bytes()
            finally:
                temporary.unlink(missing_ok=True)
    except OSError:
        raise JobResourceSnapshotError(
            "任务资源副本无法物化或读取。", category="conflict", code="resource_snapshot_materialization_failed",
        ) from None
    _verify_resource_bytes(cached, expected_sha256, hash_error)
    return cached


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
        bound_template: ResolvedResourceVersion | None = None,
    ) -> JobResourceSnapshot | None:
        if self.resource_version_service is None:
            self._ensure_no_versioned_selection(options)
            return None

        template_id = self._optional_text(options.template_id) or self.settings.default_template_id
        template = bound_template or self._resolve_resource(
            resource_type="template",
            resource_id=template_id,
            version=options.template_version,
            default_missing_category="conflict",
            allow_draft=allow_draft_template,
        )
        term_rule_set_id = self._optional_text(options.term_rule_set_id) or DEFAULT_TERM_RULE_SET_ID
        term_rule_set = self._resolve_resource(
            resource_type="term_rule_set",
            resource_id=term_rule_set_id,
            version=options.term_rule_set_version,
            default_missing_category="conflict",
        )
        translation_term_set = self._resolve_translation_term_set(options)
        translation_profile = self._resolve_translation_profile(options)
        translation_profile_snapshot = self._materialize_translation_profile(
            translation_profile
        )
        return JobResourceSnapshot(
            template=template,
            term_rule_set=term_rule_set,
            term_rule_department_id=self._optional_text(options.term_rule_department_id),
            translation_term_set=translation_term_set,
            translation_profile=translation_profile,
            translation_prompt_id=(
                translation_profile_snapshot.prompt.id
                if translation_profile_snapshot is not None
                else None
            ),
            translation_prompt_content_hash=(
                translation_profile_snapshot.prompt.content_hash
                if translation_profile_snapshot is not None
                else None
            ),
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
                default_missing_category="conflict",
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
        render_resources = self.materialize_render_resources(snapshot, job_paths)
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
                category="conflict",
                code="resource_snapshot_missing_translation_profile",
            )
        if is_translation_mode(job.translation_mode) and translation_term_version is None:
            raise JobResourceSnapshotError(
                "翻译任务缺少 Translation Term Set 快照。",
                category="conflict",
                code="resource_snapshot_missing_translation_term_set",
            )
        if spec.language_pair is not None and translation_profile is not None and translation_profile.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Profile language_pair 不匹配: expected={spec.language_pair} actual={translation_profile.language_pair}",
                category="invalid_request",
                code="translation_profile_language_pair_mismatch",
            )
        if translation_profile is not None and any(
            value is not None
            for value in (
                snapshot.translation_prompt_id,
                snapshot.translation_prompt_content_hash,
            )
        ):
            if (
                snapshot.translation_prompt_id != translation_profile.prompt.id
                or snapshot.translation_prompt_content_hash
                != translation_profile.prompt.content_hash
            ):
                raise JobResourceSnapshotError(
                    "Translation Profile Prompt 快照元数据不匹配。",
                    category="conflict",
                    code="translation_profile_prompt_snapshot_mismatch",
                )
        if spec.language_pair is not None and translation_term_version is not None and translation_term_version.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Term Set language_pair 不匹配: expected={spec.language_pair} actual={translation_term_version.language_pair}",
                category="invalid_request",
                code="translation_term_set_language_pair_mismatch",
            )
        return MaterializedJobResources(
            template_path=render_resources.template_path,
            layout_config_path=render_resources.layout_config_path,
            subscript_config_path=render_resources.subscript_config_path,
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
                raise JobResourceSnapshotError("direct 任务不能绑定 Translation Profile。", category="invalid_request")
            return None
        profile_id = self._optional_text(options.translation_profile_id) or spec.default_profile_id
        if profile_id is None:
            raise JobResourceSnapshotError(
                f"{options.translation_mode} 缺少默认 Translation Profile。",
                category="conflict",
                code="translation_profile_default_missing",
            )
        resolved = self._resolve_resource(
            resource_type="translation_profile",
            resource_id=profile_id,
            version=options.translation_profile_version,
            default_missing_category="conflict",
        )
        if spec.language_pair is not None:
            record = self.load_snapshot_record(resolved)
            actual_language_pair = self._profile_language_pair(record.resource_id, record.payload or {})
            if actual_language_pair != spec.language_pair:
                raise JobResourceSnapshotError(
                    f"Translation Profile language_pair 不匹配: expected={spec.language_pair} actual={actual_language_pair}",
                    category="invalid_request",
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
                raise JobResourceSnapshotError("direct 任务不能绑定 Translation Term Set。", category="invalid_request")
            return None
        set_id = self._optional_text(options.translation_term_set_id) or spec.default_term_set_id
        if set_id is None:
            raise JobResourceSnapshotError(
                f"{options.translation_mode} 缺少默认 Translation Term Set。",
                category="conflict",
                code="translation_term_set_default_missing",
            )
        version = None if use_default_version else self._optional_text(options.translation_term_version)
        resolved = self._resolve_translation_term_version(
            set_id=set_id,
            version=version,
            default_missing_category="conflict",
        )
        if spec.language_pair is not None and resolved.language_pair != spec.language_pair:
            raise JobResourceSnapshotError(
                f"Translation Term Set language_pair 不匹配: expected={spec.language_pair} actual={resolved.language_pair}",
                category="invalid_request",
                code="translation_term_set_language_pair_mismatch",
            )
        return resolved

    def _resolve_translation_term_version(
        self,
        *,
        set_id: str,
        version: str | None,
        default_missing_category: ApplicationErrorCode,
    ) -> ResolvedTranslationTermVersion:
        if self.translation_term_repository is None:
            raise JobResourceSnapshotError(
                "Translation Term Set 绑定需要 JOBS_REPOSITORY_BACKEND=mysql。",
                category="service_unavailable",
                code="translation_term_set_unavailable",
            )
        term_set = self.translation_term_repository.get_set(set_id)
        if term_set is None:
            category = "not_found" if version is not None else default_missing_category
            raise JobResourceSnapshotError(
                f"Translation Term Set 不存在: {set_id}",
                category=category,
                code="translation_term_set_not_found",
            )
        resolved_version = version or term_set.default_version
        if not resolved_version:
            raise JobResourceSnapshotError(
                f"Translation Term Set 缺少默认版本: {set_id}",
                category=default_missing_category,
                code="translation_term_set_default_missing",
            )
        version_record = self.translation_term_repository.get_version(term_set.set_id, resolved_version)
        if version_record is None:
            category = "not_found" if version is not None else default_missing_category
            raise JobResourceSnapshotError(
                f"Translation Term Set 版本不存在: {term_set.set_id}@{resolved_version}",
                category=category,
                code="translation_term_version_not_found",
            )
        if version_record.status != "published":
            raise JobResourceSnapshotError(
                "只能绑定 published Translation Term Set 版本。",
                category="invalid_request",
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
        default_missing_category: ApplicationErrorCode,
        allow_draft: bool = False,
    ) -> ResolvedResourceVersion:
        if self.resource_version_service is None:
            raise JobResourceSnapshotError("资源版本快照需要 JOBS_REPOSITORY_BACKEND=mysql。", category="service_unavailable")
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
            category = "not_found" if normalized_version is not None else default_missing_category
            raise JobResourceSnapshotError(str(exc), category=category, code="resource_snapshot_not_found") from exc
        except ValueError as exc:
            raise JobResourceSnapshotError(str(exc), category="invalid_request") from exc

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

    def materialize_render_resources(
        self, snapshot: JobResourceSnapshot, job_paths: JobPaths,
    ) -> MaterializedRenderResources:
        """认证任务绑定的 DOCX、YAML 和格式规则，返回随后渲染消费的同一份字节。"""

        template = snapshot.template
        rules = snapshot.term_rule_set
        if template is None:
            raise JobResourceSnapshotError(
                "任务资源快照缺少模板版本。", category="conflict", code="resource_snapshot_missing_template",
            )
        if rules is None:
            raise JobResourceSnapshotError(
                "任务资源快照缺少格式规则版本。", category="conflict", code="resource_snapshot_missing_term_rule_set",
            )
        template_record = self.authenticate_render_binding(template, "template")
        rules_record = self.authenticate_render_binding(rules, "term_rule_set")
        template_payload = template_record.payload
        rules_payload = rules_record.payload
        assert template_payload is not None and rules_payload is not None
        template_source = self._payload_text(template_payload, "docx_path")
        if template_source is None:
            raise JobResourceSnapshotError(
                "模板版本未声明 DOCX 文件。", category="conflict", code="resource_snapshot_payload_missing",
            )

        # 模板和规则独立定位，显式重绑规则仍可复用原模板副本。
        template_key = resource_payload_sha256({
            "id": template.resource_id, "version": template.version, "snapshot_hash": template.snapshot_hash,
        })
        template_dir = job_paths.resources_dir / template_key.removeprefix("sha256:")
        template_path = template_dir / "template.docx"
        template_content = self._materialize_template_file(
            template_path, template_source, template_payload.get("docx_sha256"), "template_docx_hash_mismatch",
        )
        layout_source = self._payload_text(template_payload, "layout_config_path")
        layout_config_path = None
        layout_config_content = None
        layout_asset_dir = None
        if layout_source is not None:
            layout_config_path = template_dir / "layout.yaml"
            layout_config_content = self._materialize_template_file(
                layout_config_path, layout_source, template_payload.get("layout_config_sha256"),
                "template_layout_config_hash_mismatch",
            )
            layout_asset_dir = self._resolve_payload_path(layout_source).parent
        elif template_payload.get("layout_config_path") is not None or template_payload.get("layout_config_sha256") is not None:
            raise JobResourceSnapshotError(
                "模板版式配置绑定不完整。", category="conflict", code="resource_snapshot_payload_missing",
            )

        department_id = snapshot.term_rule_department_id
        rules_key = resource_payload_sha256({
            "id": rules.resource_id, "version": rules.version, "snapshot_hash": rules.snapshot_hash,
            "department_id": department_id,
        })
        rules_path = job_paths.resources_dir / rules_key.removeprefix("sha256:") / job_paths.resource_subscript_config.name
        try:
            store = TermRulesStore.model_validate(rules_payload["store"])
            rules_content = self.term_rule_yaml_codec.dump_legacy_runtime_yaml(store, department_id=department_id).encode("utf-8")
        except (KeyError, ValueError):
            raise JobResourceSnapshotError(
                "格式规则版本内容非法。", category="conflict", code="term_rule_payload_invalid",
            ) from None
        rules_content = _materialize_verified_file(
            rules_path, content=rules_content, expected_sha256=content_sha256(rules_content), hash_error="term_rule_hash_mismatch",
        )
        return MaterializedRenderResources(
            template_path=template_path, layout_config_path=layout_config_path,
            subscript_config_path=rules_path, layout_asset_dir=layout_asset_dir,
            template_content=template_content, layout_config_content=layout_config_content,
            subscript_content=rules_content,
            publishable=(
                template.status == "published"
                and template_record.status == rules_record.status == ResourceVersionStatus.PUBLISHED
            ),
        )

    def _materialize_template_file(
        self, destination: Path, source: str, expected_sha256: object, hash_error: str,
    ) -> bytes:
        if not isinstance(expected_sha256, str) or not expected_sha256.startswith("sha256:"):
            raise JobResourceSnapshotError("模板版本缺少有效的内容 SHA-256。", category="conflict", code=hash_error)
        return _materialize_verified_file(
            destination, source=self._resolve_payload_path(source), expected_sha256=expected_sha256, hash_error=hash_error,
        )

    def authenticate_render_binding(
        self, snapshot: ResolvedResourceVersion, expected_type: ResourceType,
    ) -> ResourceVersionRecord:
        """校验渲染所需的绑定身份与版本记录，供 Worker 和继承快照的克隆共用。"""

        if snapshot.resource_type != expected_type:
            raise JobResourceSnapshotError("任务资源快照类型不匹配。", category="conflict")
        record = self.load_snapshot_record(snapshot)
        if (record.resource_type, record.resource_id, record.version) != (
            snapshot.resource_type, snapshot.resource_id, snapshot.version,
        ):
            raise JobResourceSnapshotError("任务资源记录的版本身份不匹配。", category="conflict")
        if record.payload is None or resource_payload_sha256(record.payload) != record.snapshot_hash:
            raise JobResourceSnapshotError(
                "任务资源版本的 payload SHA-256 不匹配。", category="conflict",
                code="resource_snapshot_payload_hash_mismatch",
            )
        return record

    def _materialize_translation_profile(
        self,
        snapshot: ResolvedResourceVersion | None,
    ) -> TranslationProfileSnapshot | None:
        if snapshot is None:
            return None
        record = self.load_snapshot_record(snapshot)
        try:
            return translation_profile_snapshot_from_record(self.settings, record)
        except (FileNotFoundError, ValueError) as exc:
            raise JobResourceSnapshotError(
                f"Translation Profile payload 非法: {exc}",
                category="conflict",
                code="translation_profile_payload_invalid",
            ) from exc

    def materialize_translation_profile(
        self,
        snapshot: ResolvedResourceVersion,
    ) -> TranslationProfileSnapshot:
        """按任务绑定的资源 ID/version/hash 读取不可变 Profile Prompt。"""

        materialized = self._materialize_translation_profile(snapshot)
        if materialized is None:
            raise JobResourceSnapshotError(
                "任务绑定的 Translation Profile 为空。",
                category="conflict",
                code="resource_snapshot_missing_translation_profile",
            )
        return materialized

    def _materialize_translation_term_set(
        self,
        snapshot: ResolvedTranslationTermVersion | None,
    ) -> TermVersionSnapshot | None:
        if snapshot is None:
            return None
        if self.translation_term_repository is None:
            raise JobResourceSnapshotError(
                "当前 stage runtime 缺少 Translation Term Set repository。",
                category="service_unavailable",
                code="translation_term_set_unavailable",
            )
        record = self.translation_term_repository.get_version(snapshot.set_id, snapshot.version)
        if record is None:
            raise JobResourceSnapshotError(
                f"资源快照指向的 Translation Term Set 版本不存在: {snapshot.set_id}@{snapshot.version}",
                category="conflict",
                code="translation_term_version_not_found",
            )
        if record.status != "published":
            raise JobResourceSnapshotError(
                f"资源快照指向了非 published Translation Term Set 版本: {snapshot.set_id}@{snapshot.version}",
                category="conflict",
                code="translation_term_version_invalid_status",
            )
        if record.snapshot_hash != snapshot.snapshot_hash:
            raise JobResourceSnapshotError(
                f"Translation Term Set 快照 hash 不匹配: {snapshot.set_id}@{snapshot.version}",
                category="conflict",
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
        raise JobResourceSnapshotError(
            f"Translation Profile language_pair 无法从绑定资源推断: {translation_profile_id}",
            category="conflict",
            code="translation_profile_language_pair_missing",
        )

    def load_snapshot_record(self, snapshot: ResolvedResourceVersion) -> ResourceVersionRecord:
        """按绑定版本读取记录，允许以原身份重验已发布的模板草稿。"""

        if self.resource_version_service is None:
            raise JobResourceSnapshotError("资源版本服务不可用。", category="service_unavailable", code="resource_snapshot_unavailable")
        record = self.resource_version_service.repository.get_resource_version(
            snapshot.resource_type,
            snapshot.resource_id,
            snapshot.version,
        )
        if record is None:
            raise JobResourceSnapshotError(
                f"资源快照指向的版本不存在: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                category="conflict",
                code="resource_snapshot_not_found",
            )
        if snapshot.resource_type == "template" and record.status not in {
            ResourceVersionStatus.PUBLISHED,
            ResourceVersionStatus.DRAFT,
        }:
            raise JobResourceSnapshotError(
                "任务绑定的模板版本状态不可用于生成。", category="conflict", code="resource_snapshot_invalid_status",
            )
        draft_template_is_authorized = (
            record.status == ResourceVersionStatus.DRAFT
            and snapshot.resource_type == "template"
            and snapshot.status == "draft"
        )
        if record.status == ResourceVersionStatus.DRAFT and not draft_template_is_authorized:
            raise JobResourceSnapshotError(
                f"资源快照指向了 draft 版本: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                category="conflict",
                code="resource_snapshot_invalid_status",
            )
        if record.snapshot_hash != snapshot.snapshot_hash and not (
            snapshot.resource_type == "template" and snapshot.status == "draft"
            and record.status == ResourceVersionStatus.PUBLISHED
            and record.payload is not None and resource_payload_sha256({
                key: value for key, value in record.payload.items()
                if key not in _TEMPLATE_PUBLICATION_FIELDS
            }) == snapshot.snapshot_hash
        ):
            raise JobResourceSnapshotError(
                f"资源快照 hash 不匹配: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                category="conflict",
                code="resource_snapshot_hash_mismatch",
            )
        if record.payload is None:
            raise JobResourceSnapshotError(
                f"资源版本 payload 缺失: {snapshot.resource_type}/{snapshot.resource_id}@{snapshot.version}",
                category="conflict",
                code="resource_snapshot_payload_missing",
            )
        return record

    def _resolve_payload_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        try:
            return (self.settings.root_dir / path).resolve()
        except (OSError, RuntimeError):
            raise JobResourceSnapshotError(
                "任务绑定的资源文件不可读取。", category="conflict", code="resource_snapshot_file_unavailable",
            ) from None

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
                category="service_unavailable",
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
