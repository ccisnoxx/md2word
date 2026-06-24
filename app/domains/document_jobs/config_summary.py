from __future__ import annotations

# app/domains/document_jobs/config_summary.py: 聚合 document_job 创建/重试需要的只读配置摘要。

from typing import Any

from app.core.runtime import AppRuntime
from app.domains.document_jobs.schemas import (
    DocumentJobConfigDefaults,
    DocumentJobConfigOptions,
    DocumentJobConfigReadiness,
    DocumentJobConfigSummaryResponse,
    DocumentJobConfigVersionOption,
    DocumentJobTranslationResourceDefaults,
)
from app.domains.term_rules.versioning_service import DEFAULT_TERM_RULE_SET_ID
from app.domains.translation.modes import TRANSLATION_LANGUAGE_PAIRS, derive_translation_term_set_id, spec_for_language_pair
from app.services.auth.models import AuthenticatedUser


def build_document_job_config_summary(
    runtime: AppRuntime,
    *,
    user: AuthenticatedUser,
) -> DocumentJobConfigSummaryResponse:
    """返回任务创建 UI 所需的默认资源摘要和可绑定的 published 版本。"""

    warnings: list[str] = []
    translation_defaults = _translation_defaults(runtime, warnings)
    en2zh_defaults = translation_defaults.get("en2zh", DocumentJobTranslationResourceDefaults())
    defaults = DocumentJobConfigDefaults(
        template=_default_template(runtime, warnings),
        term_rule_set=_default_term_rule_set(runtime, warnings),
        translation_term_set=en2zh_defaults.translation_term_set,
        translation_profile=en2zh_defaults.translation_profile,
    )
    translation_modes = _translation_mode_readiness(translation_defaults)
    options = DocumentJobConfigOptions(
        templates=_template_options(runtime, warnings),
        term_rule_sets=_term_rule_set_options(runtime, warnings),
        translation_term_sets=_translation_term_set_options(runtime, warnings),
        translation_profiles=_translation_profile_options(runtime, warnings),
    )
    dependency_checks = runtime.health_service.build_dependency_checks()
    return DocumentJobConfigSummaryResponse(
        role=user.role,
        resource_mode="versioned" if runtime.resource_version_service is not None else "legacy",
        defaults=defaults,
        translation_defaults=translation_defaults,
        options=options,
        readiness=DocumentJobConfigReadiness(
            en2zh_available=translation_modes.get("en2zh", False),
            ru2zh_available=translation_modes.get("ru2zh", False),
            translation_modes=translation_modes,
            p0_document_jobs_required=bool(dependency_checks.get("p0_document_jobs_required")),
            p0_document_jobs_ready=bool(dependency_checks.get("p0_document_jobs_ready", True)),
            document_jobs_worker_backend=str(dependency_checks.get("document_jobs_worker_backend") or "disabled"),
            document_jobs_automatic_execution_enabled=bool(
                dependency_checks.get("document_jobs_automatic_execution_enabled")
            ),
            blockers=_string_list(dependency_checks.get("p0_document_jobs_blockers")),
            warnings=sorted(set([*warnings, *_string_list(dependency_checks.get("p0_document_jobs_warnings"))])),
        ),
    )


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _default_template(runtime: AppRuntime, warnings: list[str]) -> DocumentJobConfigVersionOption | None:
    try:
        template_id = runtime.template_read_service.get_default_template_id()
        selection = runtime.template_read_service.resolve_template_version(None)
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"template_default_unavailable:{exc}")
        return None
    return DocumentJobConfigVersionOption(
        resource_id=template_id,
        version=str(selection.version),
        label=selection.template_version_id,
        is_default=True,
    )


def _template_options(runtime: AppRuntime, warnings: list[str]) -> list[DocumentJobConfigVersionOption]:
    try:
        templates = runtime.template_read_service.list_templates(url_for=None)
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"template_options_unavailable:{exc}")
        return []
    options: list[DocumentJobConfigVersionOption] = []
    for template in templates:
        try:
            versions = runtime.template_read_service.list_template_versions(template.id)
        except (FileNotFoundError, ValueError) as exc:
            warnings.append(f"template_versions_unavailable:{template.id}:{exc}")
            continue
        for version in versions:
            if version.status != "published" or version.template_version_id is None:
                continue
            options.append(
                DocumentJobConfigVersionOption(
                    resource_id=version.template_id or template.id,
                    version=str(version.version),
                    label=version.template_version_id,
                    status=version.status,
                    is_default=version.is_default,
                    snapshot_hash=version.snapshot_hash,
                    summary={
                        "name": template.name,
                        "description": template.description,
                    },
                )
            )
    return options


def _default_term_rule_set(runtime: AppRuntime, warnings: list[str]) -> DocumentJobConfigVersionOption | None:
    service = runtime.term_rule_set_version_service
    if service is None:
        warnings.append("term_rule_set_version_service_unavailable")
        return None
    try:
        detail = service.get_set_detail(DEFAULT_TERM_RULE_SET_ID)
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"term_rule_set_default_unavailable:{exc}")
        return None
    default_version = detail.default_version
    if default_version is None:
        warnings.append("term_rule_set_default_missing")
        return None
    return _term_rule_set_option(detail.id, next((item for item in detail.versions if item.version == default_version), None), default_version)


def _term_rule_set_options(runtime: AppRuntime, warnings: list[str]) -> list[DocumentJobConfigVersionOption]:
    service = runtime.term_rule_set_version_service
    if service is None:
        warnings.append("term_rule_set_version_service_unavailable")
        return []
    try:
        sets = service.list_sets()
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"term_rule_set_options_unavailable:{exc}")
        return []
    options: list[DocumentJobConfigVersionOption] = []
    for item in sets.items:
        try:
            detail = service.get_set_detail(item.id)
        except (FileNotFoundError, ValueError) as exc:
            warnings.append(f"term_rule_set_versions_unavailable:{item.id}:{exc}")
            continue
        options.extend(
            _term_rule_set_option(detail.id, version, detail.default_version)
            for version in detail.versions
            if version.status == "published"
        )
    return options


def _term_rule_set_option(
    set_id: str,
    version_record: Any | None,
    default_version: str | None,
) -> DocumentJobConfigVersionOption:
    version = version_record.version if version_record is not None else default_version or ""
    return DocumentJobConfigVersionOption(
        resource_id=set_id,
        version=version,
        label=f"{set_id}@{version}" if version else set_id,
        status=version_record.status if version_record is not None else "published",
        is_default=version == default_version,
        snapshot_hash=version_record.snapshot_hash if version_record is not None else None,
        summary={
            "rule_count": version_record.rule_count if version_record is not None else None,
            "enabled_rule_count": version_record.enabled_rule_count if version_record is not None else None,
        },
    )


def _translation_defaults(
    runtime: AppRuntime,
    warnings: list[str],
) -> dict[str, DocumentJobTranslationResourceDefaults]:
    defaults: dict[str, DocumentJobTranslationResourceDefaults] = {}
    for language_pair in TRANSLATION_LANGUAGE_PAIRS:
        defaults[language_pair] = DocumentJobTranslationResourceDefaults(
            translation_term_set=_default_translation_term_set(runtime, warnings, language_pair=language_pair),
            translation_profile=_default_translation_profile(runtime, warnings, language_pair=language_pair),
        )
    return defaults


def _translation_mode_readiness(
    translation_defaults: dict[str, DocumentJobTranslationResourceDefaults],
) -> dict[str, bool]:
    readiness: dict[str, bool] = {}
    for language_pair in TRANSLATION_LANGUAGE_PAIRS:
        defaults = translation_defaults.get(language_pair)
        readiness[language_pair] = (
            defaults is not None
            and defaults.translation_term_set is not None
            and defaults.translation_profile is not None
        )
    return readiness


def _default_translation_term_set(
    runtime: AppRuntime,
    warnings: list[str],
    *,
    language_pair: str,
) -> DocumentJobConfigVersionOption | None:
    repository = runtime.persistence_adapters.translation_term_repository
    if repository is None:
        warnings.append("translation_term_repository_unavailable")
        return None
    set_id = derive_translation_term_set_id(language_pair)
    term_set = repository.get_set(set_id)
    if term_set is None or term_set.default_version is None:
        warnings.append(f"translation_term_set_default_missing:{language_pair}")
        return None
    record = repository.get_version(term_set.set_id, term_set.default_version)
    if record is None or record.status != "published":
        warnings.append(f"translation_term_set_default_unavailable:{language_pair}")
        return None
    return _translation_term_set_option(record, default_version=term_set.default_version)


def _translation_term_set_options(runtime: AppRuntime, warnings: list[str]) -> list[DocumentJobConfigVersionOption]:
    repository = runtime.persistence_adapters.translation_term_repository
    if repository is None:
        warnings.append("translation_term_repository_unavailable")
        return []
    options: list[DocumentJobConfigVersionOption] = []
    for term_set in repository.list_sets():
        options.extend(
            _translation_term_set_option(record, default_version=term_set.default_version)
            for record in repository.list_versions(term_set.set_id)
            if record.status == "published"
        )
    return options


def _translation_term_set_option(record: Any, *, default_version: str | None) -> DocumentJobConfigVersionOption:
    return DocumentJobConfigVersionOption(
        resource_id=record.set_id,
        version=record.version,
        label=f"{record.set_id}@{record.version}",
        status=record.status,
        is_default=record.version == default_version,
        snapshot_hash=record.snapshot_hash,
        summary={
            "language_pair": record.language_pair,
            "term_count": record.term_count,
        },
    )


def _default_translation_profile(
    runtime: AppRuntime,
    warnings: list[str],
    *,
    language_pair: str,
) -> DocumentJobConfigVersionOption | None:
    service = runtime.translation_profile_service
    if service is None:
        warnings.append("translation_profile_service_unavailable")
        return None
    spec = spec_for_language_pair(language_pair)
    profile_id = spec.default_profile_id
    if profile_id is None:
        warnings.append(f"translation_profile_default_missing:{language_pair}")
        return None
    try:
        detail = service.get_profile_detail(profile_id)
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"translation_profile_default_unavailable:{language_pair}:{exc}")
        return None
    default_version = detail.default_version
    if default_version is None:
        warnings.append(f"translation_profile_default_missing:{language_pair}")
        return None
    return _translation_profile_option(
        profile_id,
        next((item for item in detail.versions if item.version == default_version), None),
        default_version,
    )


def _translation_profile_options(runtime: AppRuntime, warnings: list[str]) -> list[DocumentJobConfigVersionOption]:
    service = runtime.translation_profile_service
    if service is None:
        warnings.append("translation_profile_service_unavailable")
        return []
    try:
        profiles = service.list_profiles()
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(f"translation_profile_options_unavailable:{exc}")
        return []
    options: list[DocumentJobConfigVersionOption] = []
    for item in profiles.items:
        try:
            detail = service.get_profile_detail(item.id)
        except (FileNotFoundError, ValueError) as exc:
            warnings.append(f"translation_profile_versions_unavailable:{item.id}:{exc}")
            continue
        options.extend(
            _translation_profile_option(item.id, version, detail.default_version)
            for version in detail.versions
            if version.status == "published"
        )
    return options


def _translation_profile_option(
    profile_id: str,
    version_record: Any | None,
    default_version: str | None,
) -> DocumentJobConfigVersionOption:
    version = version_record.version if version_record is not None else default_version or ""
    return DocumentJobConfigVersionOption(
        resource_id=profile_id,
        version=version,
        label=f"{profile_id}@{version}" if version else profile_id,
        status=version_record.status if version_record is not None else "published",
        is_default=version == default_version,
        snapshot_hash=version_record.snapshot_hash if version_record is not None else None,
        summary=_translation_profile_summary(version_record),
    )


def _translation_profile_summary(version_record: Any | None) -> dict[str, Any]:
    if version_record is None:
        return {}
    return {
        "target_language": version_record.target_language,
        "language_pair": version_record.language_pair,
        "domain": version_record.domain,
        "prompt_version": version_record.prompt_version,
        "model": version_record.model,
        "max_pages_per_batch": version_record.max_pages_per_batch,
        "max_chars_per_batch": version_record.max_chars_per_batch,
    }
