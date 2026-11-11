from __future__ import annotations

# app/domains/document_jobs/use_cases/request_snapshot.py: 创建、克隆、重试共用的请求快照、资源快照与模式/模板/术语版本解析。

from typing import Any

from fastapi import status

from app.core.config import Settings
from app.core.errors import ApiError
from app.domains.document_jobs.models import DocumentJobMode, DocumentJobRecord
from app.domains.document_jobs.use_cases.access import DocumentJobAccess
from app.domains.files.models import DocumentFileRecord
from app.domains.jobs.models import ConversionOptions
from app.domains.jobs.resource_snapshots import JobResourceSnapshotError
from app.domains.translation.modes import (
    TranslationMode,
    document_job_mode_for_translation_mode,
    is_translation_document_job_mode,
    normalize_translation_mode,
    spec_for_document_job_mode,
    translation_mode_for_document_job_mode,
)
from app.services.auth.models import AuthenticatedUser


class DocumentJobRequestSnapshots:
    """创建、克隆、重试共用的请求快照、资源快照与模式/模板/术语版本解析。"""

    def __init__(
        self,
        *,
        settings: Settings,
        template_read_service: Any | None,
        term_version_service: Any | None,
        job_resource_snapshot_service: Any | None,
        access: DocumentJobAccess,
    ) -> None:
        self.settings = settings
        self.template_read_service = template_read_service
        self.term_version_service = term_version_service
        self.job_resource_snapshot_service = job_resource_snapshot_service
        self.access = access

    def build_request_snapshot(
        self,
        source_file: DocumentFileRecord,
        *,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str,
        term_version_id: str | None,
        debug_full_text_enabled: bool,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        resource_snapshot: dict | None = None,
    ) -> dict:
        return {
            "source_file": {
                "id": source_file.id,
                "object_key": source_file.object_key,
                "original_filename": source_file.original_filename,
                "mime_type": source_file.mime_type,
                "size_bytes": source_file.size_bytes,
                "checksum_sha256": source_file.checksum_sha256,
            },
            "mode": mode,
            "translation_mode": translation_mode_for_document_job_mode(mode),
            "document_language": document_language,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_assets": {
                "term_rule_set_id": self.access.normalize_optional_text(term_rule_set_id),
                "term_rule_set_version": self.access.normalize_optional_text(term_rule_set_version),
                "translation_term_set_id": self.access.normalize_optional_text(translation_term_set_id),
                "translation_term_version": self.access.normalize_optional_text(translation_term_version),
            },
            "translation_profile": {
                "translation_profile_id": self.access.normalize_optional_text(translation_profile_id),
                "translation_profile_version": self.access.normalize_optional_text(translation_profile_version),
            },
            "resources": resource_snapshot,
            "debug_full_text_enabled": debug_full_text_enabled,
            "word_preview": self.settings.word_preview_policy().model_dump(mode="json"),
            "page_quality": self.settings.page_quality_policy().model_dump(mode="json"),
        }

    def resolve_clone_config(
        self,
        source_job: DocumentJobRecord,
        source_file: DocumentFileRecord,
        *,
        new_job_id: str,
        config_strategy: str,
        document_language: str,
        template_version_id: str | None,
        term_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        debug_full_text: bool | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if config_strategy == "keep_source_snapshot":
            source_assets = self.read_snapshot_record(source_job.request_snapshot, "term_assets")
            source_profile = self.read_snapshot_record(source_job.request_snapshot, "translation_profile")
            resolved_debug = self.resolve_debug_full_text_enabled(
                source_job.mode,
                source_job.debug_full_text_enabled if debug_full_text is None else debug_full_text,
            )
            request_snapshot = self.build_request_snapshot(
                source_file,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=source_job.template_version_id,
                term_version_id=source_job.term_version_id,
                debug_full_text_enabled=resolved_debug,
                term_rule_set_id=self.read_snapshot_string(source_assets, "term_rule_set_id"),
                term_rule_set_version=self.read_snapshot_string(source_assets, "term_rule_set_version"),
                translation_term_set_id=self.read_snapshot_string(source_assets, "translation_term_set_id"),
                translation_term_version=self.read_snapshot_string(source_assets, "translation_term_version"),
                translation_profile_id=self.read_snapshot_string(source_profile, "translation_profile_id"),
                translation_profile_version=self.read_snapshot_string(source_profile, "translation_profile_version"),
                resource_snapshot=self.read_snapshot_record(source_job.request_snapshot, "resources"),
            )
            if "word_preview" in source_job.request_snapshot:
                request_snapshot["word_preview"] = source_job.request_snapshot["word_preview"]
            else:
                request_snapshot.pop("word_preview", None)
            if "page_quality" in source_job.request_snapshot:
                request_snapshot["page_quality"] = source_job.request_snapshot["page_quality"]
            else:
                request_snapshot.pop("page_quality", None)
            request_snapshot["clone"] = self.build_clone_snapshot(source_job, config_strategy, reason)
            return {
                "template_version_id": source_job.template_version_id,
                "term_version_id": source_job.term_version_id,
                "debug_full_text_enabled": resolved_debug,
                "request_snapshot": request_snapshot,
            }

        selected_template_version_id = template_version_id if config_strategy == "select_published_versions" else None
        selected_term_version_id = term_version_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_id = term_rule_set_id if config_strategy == "select_published_versions" else None
        selected_term_rule_set_version = term_rule_set_version if config_strategy == "select_published_versions" else None
        selected_translation_term_set_id = translation_term_set_id if config_strategy == "select_published_versions" else None
        selected_translation_term_version = translation_term_version if config_strategy == "select_published_versions" else None
        selected_translation_profile_id = translation_profile_id if config_strategy == "select_published_versions" else None
        selected_translation_profile_version = translation_profile_version if config_strategy == "select_published_versions" else None
        resolved_template_version_id = self.resolve_template_version_id(selected_template_version_id)
        resolved_term_version_id = self.resolve_term_version_id(
            source_job.mode,
            self.legacy_translation_term_version_id(
                source_job.mode,
                selected_term_version_id,
                selected_translation_term_version,
            ),
        )
        resolved_debug = self.resolve_debug_full_text_enabled(source_job.mode, bool(debug_full_text))
        request_snapshot = self.build_request_snapshot(
            source_file,
            mode=source_job.mode,
            document_language=document_language,
            template_version_id=resolved_template_version_id,
            term_version_id=resolved_term_version_id,
            debug_full_text_enabled=resolved_debug,
            term_rule_set_id=selected_term_rule_set_id,
            term_rule_set_version=selected_term_rule_set_version,
            translation_term_set_id=selected_translation_term_set_id,
            translation_term_version=selected_translation_term_version,
            translation_profile_id=selected_translation_profile_id,
            translation_profile_version=selected_translation_profile_version,
            resource_snapshot=self.build_resource_snapshot(
                job_id=new_job_id,
                mode=source_job.mode,
                document_language=document_language,
                template_version_id=resolved_template_version_id if self.access.normalize_optional_text(selected_template_version_id) else None,
                term_rule_set_id=selected_term_rule_set_id,
                term_rule_set_version=selected_term_rule_set_version,
                translation_term_set_id=selected_translation_term_set_id,
                translation_term_version=selected_translation_term_version,
                translation_profile_id=selected_translation_profile_id,
                translation_profile_version=selected_translation_profile_version,
            ),
        )
        request_snapshot["clone"] = self.build_clone_snapshot(source_job, config_strategy, reason)
        return {
            "template_version_id": resolved_template_version_id,
            "term_version_id": resolved_term_version_id,
            "debug_full_text_enabled": resolved_debug,
            "request_snapshot": request_snapshot,
        }

    def build_clone_snapshot(self, source_job: DocumentJobRecord, config_strategy: str, reason: str | None) -> dict[str, Any]:
        return {
            "source_job_id": source_job.id,
            "config_strategy": config_strategy,
            "reason": self.access.normalize_optional_text(reason),
            "source_status": source_job.status,
            "source_stage": source_job.stage,
            "source_template_version_id": source_job.template_version_id,
            "source_term_version_id": source_job.term_version_id,
        }

    def read_snapshot_record(self, snapshot: dict, key: str) -> dict[str, Any] | None:
        value = snapshot.get(key)
        return value if isinstance(value, dict) else None

    def read_snapshot_string(self, snapshot: dict[str, Any] | None, key: str) -> str | None:
        if snapshot is None:
            return None
        value = snapshot.get(key)
        return value if isinstance(value, str) else None

    def build_retry_request_snapshot(
        self,
        job: DocumentJobRecord,
        *,
        use_latest_term_assets: bool,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
    ) -> dict | None:
        has_selection = any(
            self.access.normalize_optional_text(value)
            for value in (term_rule_set_id, term_rule_set_version, translation_term_set_id, translation_term_version)
        )
        if not use_latest_term_assets and not has_selection:
            return None
        snapshot = dict(job.request_snapshot)
        resource_snapshot = self.build_resource_snapshot(
            job_id=job.id,
            mode=job.mode,
            document_language=job.document_language,
            template_version_id=None,
            term_rule_set_id=term_rule_set_id,
            term_rule_set_version=None if use_latest_term_assets else term_rule_set_version,
            translation_term_set_id=translation_term_set_id,
            translation_term_version=None if use_latest_term_assets else translation_term_version,
            translation_profile_id=None,
            translation_profile_version=None,
        )
        resource_snapshot = self.preserve_retry_template_and_profile(job.request_snapshot, resource_snapshot)
        snapshot["term_assets"] = {
            "use_latest_term_assets": use_latest_term_assets,
            "term_rule_set_id": self.access.normalize_optional_text(term_rule_set_id),
            "term_rule_set_version": self.access.normalize_optional_text(term_rule_set_version),
            "translation_term_set_id": self.access.normalize_optional_text(translation_term_set_id),
            "translation_term_version": self.access.normalize_optional_text(translation_term_version),
        }
        snapshot["resources"] = resource_snapshot
        return snapshot

    def build_resource_snapshot(
        self,
        *,
        job_id: str,
        mode: DocumentJobMode,
        document_language: str,
        template_version_id: str | None,
        term_rule_set_id: str | None,
        term_rule_set_version: str | None,
        translation_term_set_id: str | None,
        translation_term_version: str | None,
        translation_profile_id: str | None,
        translation_profile_version: str | None,
        term_rule_department_id: str | None = None,
        allow_draft_template: bool = False,
    ) -> dict | None:
        if self.job_resource_snapshot_service is None:
            return None
        has_explicit_selection = any(
            self.access.normalize_optional_text(value)
            for value in (
                template_version_id,
                term_rule_set_id,
                term_rule_set_version,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        template_id, template_version = self.split_template_version_id(template_version_id)
        options = ConversionOptions(
            template_id=template_id,
            template_version=template_version,
            term_rule_set_id=self.access.normalize_optional_text(term_rule_set_id),
            term_rule_set_version=self.access.normalize_optional_text(term_rule_set_version),
            term_rule_department_id=self.access.normalize_optional_text(term_rule_department_id),
            translation_term_set_id=self.access.normalize_optional_text(translation_term_set_id),
            translation_term_version=self.access.normalize_optional_text(translation_term_version),
            translation_profile_id=self.access.normalize_optional_text(translation_profile_id),
            translation_profile_version=self.access.normalize_optional_text(translation_profile_version),
            translation_mode=translation_mode_for_document_job_mode(mode),
            document_language=document_language,
        )
        try:
            snapshot = self.job_resource_snapshot_service.build_snapshot(
                options=options,
                source_kind="source_pdf",
                job_id=job_id,
                allow_draft_template=allow_draft_template,
            )
        except JobResourceSnapshotError as exc:
            if not has_explicit_selection:
                return None
            raise ApiError(exc.status_code, exc.code, exc.message) from exc
        if snapshot is None:
            return None
        return snapshot.model_dump(mode="json")

    def ensure_resource_selection_allowed(
        self,
        *,
        user: AuthenticatedUser,
        use_latest_term_assets: bool = False,
        template_version_id: str | None = None,
        term_version_id: str | None = None,
        term_rule_set_id: str | None = None,
        term_rule_set_version: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
    ) -> None:
        if user.role == "admin":
            return
        selected: list[str] = []
        for name, value in {
            "use_latest_term_assets": use_latest_term_assets,
            "template_version_id": template_version_id,
            "term_version_id": term_version_id,
            "term_rule_set_id": term_rule_set_id,
            "term_rule_set_version": term_rule_set_version,
            "translation_term_set_id": translation_term_set_id,
            "translation_term_version": translation_term_version,
            "translation_profile_id": translation_profile_id,
            "translation_profile_version": translation_profile_version,
        }.items():
            if isinstance(value, bool):
                if value:
                    selected.append(name)
                continue
            if self.access.normalize_optional_text(value):
                selected.append(name)
        if selected:
            raise ApiError(
                status.HTTP_403_FORBIDDEN,
                "forbidden",
                f"operator 不能选择任务资源版本: {', '.join(selected)}。",
            )

    def split_template_version_id(self, template_version_id: str | None) -> tuple[str | None, str | None]:
        normalized = self.access.normalize_optional_text(template_version_id)
        if normalized is None:
            return None, None
        template_id, separator, version = normalized.partition("@")
        if not separator:
            return normalized, None
        return template_id or None, version or None

    def preserve_retry_template_and_profile(self, request_snapshot: dict, resource_snapshot: dict | None) -> dict | None:
        if resource_snapshot is None:
            return None
        previous_resources = request_snapshot.get("resources")
        if not isinstance(previous_resources, dict):
            return resource_snapshot
        preserved = dict(resource_snapshot)
        if isinstance(previous_resources.get("template"), dict):
            preserved["template"] = previous_resources["template"]
        if isinstance(previous_resources.get("translation_profile"), dict):
            preserved["translation_profile"] = previous_resources["translation_profile"]
            for key in (
                "translation_prompt_id",
                "translation_prompt_content_hash",
            ):
                if key in previous_resources:
                    preserved[key] = previous_resources[key]
                else:
                    preserved.pop(key, None)
        return preserved

    def resolve_document_job_mode(
        self,
        *,
        mode: DocumentJobMode | None,
        translation_mode: TranslationMode | None,
    ) -> DocumentJobMode:
        if translation_mode is not None:
            try:
                translation_mode = normalize_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if mode is None and translation_mode is None:
            return "direct_pdf_to_word"
        if mode is None:
            try:
                return document_job_mode_for_translation_mode(translation_mode)
            except ValueError as exc:
                raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        try:
            resolved_translation_mode = translation_mode_for_document_job_mode(mode)
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        if translation_mode is not None and translation_mode != resolved_translation_mode:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                f"translation_mode 与 mode 不一致: translation_mode={translation_mode} mode={mode}。",
            )
        return mode

    def ensure_direct_translation_selection_absent(
        self,
        mode: DocumentJobMode,
        *,
        term_version_id: str | None = None,
        translation_term_set_id: str | None = None,
        translation_term_version: str | None = None,
        translation_profile_id: str | None = None,
        translation_profile_version: str | None = None,
        debug_full_text: bool = False,
    ) -> None:
        """只校验新写入意图；历史 direct 快照的惰性字段不参与资源选择。"""

        if is_translation_document_job_mode(mode):
            return
        has_translation_selection = any(
            self.access.normalize_optional_text(value)
            for value in (
                term_version_id,
                translation_term_set_id,
                translation_term_version,
                translation_profile_id,
                translation_profile_version,
            )
        )
        if has_translation_selection or debug_full_text:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "原文转换（direct）不能绑定翻译资源或开启翻译全文调试。",
            )

    def ensure_document_language_allowed(self, mode: DocumentJobMode, document_language: str) -> None:
        spec = spec_for_document_job_mode(mode)
        if not spec.is_translation:
            return
        allowed = {"auto", spec.default_document_language}
        if document_language not in allowed:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                (
                    f"{spec.translation_mode} 只支持 "
                    f"document_language=auto 或 {spec.default_document_language}。"
                ),
            )

    def legacy_translation_term_version_id(
        self,
        mode: DocumentJobMode,
        term_version_id: str | None,
        translation_term_version: str | None,
    ) -> str | None:
        if not is_translation_document_job_mode(mode):
            return term_version_id
        normalized_translation_term_version = self.access.normalize_optional_text(translation_term_version)
        if normalized_translation_term_version is None:
            return term_version_id
        if "@" in normalized_translation_term_version:
            return normalized_translation_term_version
        spec = spec_for_document_job_mode(mode)
        return f"{spec.language_pair}@{normalized_translation_term_version}"

    def resolve_template_version_id(self, template_version_id: str | None, *, allow_draft: bool = False) -> str:
        if self.template_read_service is None:
            return template_version_id or self.settings.default_template_id
        try:
            return self.template_read_service.resolve_template_version(
                template_version_id,
                allow_draft=allow_draft,
            ).template_version_id
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc

    def resolve_term_version_id(self, mode: DocumentJobMode, term_version_id: str | None) -> str | None:
        """direct 在调用术语服务前返回，历史字段不能触发翻译资源加载。"""

        language_pair = spec_for_document_job_mode(mode).language_pair
        if language_pair is None:
            return None
        if self.term_version_service is None:
            return term_version_id
        try:
            snapshot = self.term_version_service.resolve_for_job(term_version_id, language_pair=language_pair)
        except FileNotFoundError as exc:
            raise ApiError(status.HTTP_404_NOT_FOUND, "not_found", str(exc)) from exc
        except ValueError as exc:
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", str(exc)) from exc
        return snapshot.term_version_id if snapshot is not None else None

    def resolve_debug_full_text_enabled(self, mode: DocumentJobMode, debug_full_text: bool) -> bool:
        if not debug_full_text:
            return False
        if not is_translation_document_job_mode(mode):
            raise ApiError(status.HTTP_400_BAD_REQUEST, "invalid_request", "debug_full_text 仅支持翻译任务。")
        if not self.settings.translation_debug_archive_enabled:
            raise ApiError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_request",
                "TRANSLATION_DEBUG_ARCHIVE_ENABLED 未开启，不能保存翻译全文调试归档。",
            )
        return True

    def ensure_debug_full_text_allowed(self, user: AuthenticatedUser, debug_full_text: bool) -> None:
        if debug_full_text and user.role != "admin":
            raise ApiError(status.HTTP_403_FORBIDDEN, "role_forbidden", "只有 admin 可以开启翻译全文调试归档。")
