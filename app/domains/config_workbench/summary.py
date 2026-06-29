from __future__ import annotations

# File: app/domains/config_workbench/summary.py
# Purpose: 聚合配置工作台只读总览，避免前端直接拼多个治理接口。

from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote

from app.core.runtime import AppRuntime
from app.domains.config_workbench.schemas import (
    ConfigWorkbenchDetailStatus,
    ConfigWorkbenchFinding,
    ConfigWorkbenchGroup,
    ConfigWorkbenchGroupId,
    ConfigWorkbenchReleaseGate,
    ConfigWorkbenchSeverity,
    ConfigWorkbenchStatus,
    ConfigWorkbenchSummaryResponse,
)
from app.domains.resources.models import ResourceType
from app.domains.term_rules.models import TermRuleProposalStatus


DRAFT_VERSION = "draft"
ConfigWorkbenchSummaryMode = Literal["overview", "full"]


def build_config_workbench_summary(
    runtime: AppRuntime,
    *,
    mode: ConfigWorkbenchSummaryMode = "full",
) -> ConfigWorkbenchSummaryResponse:
    checks = _build_dependency_checks(runtime)
    release_gate = _build_release_gate(checks)
    groups = [
        _build_runtime_readiness_group(checks),
        _build_templates_group(runtime),
        _build_term_rule_sets_group(runtime, include_deep=mode == "full"),
        _build_translation_profiles_group(runtime),
        _build_translation_term_sets_group(runtime, include_deep=mode == "full"),
    ]
    return ConfigWorkbenchSummaryResponse(
        generated_at=datetime.now(timezone.utc),
        overall_status=_overall_status(groups, release_gate),
        release_gate=release_gate,
        groups=groups,
    )


def build_config_workbench_group(
    runtime: AppRuntime,
    group_id: ConfigWorkbenchGroupId,
    *,
    mode: ConfigWorkbenchSummaryMode = "full",
) -> ConfigWorkbenchGroup:
    checks = _build_dependency_checks(runtime)
    if group_id == "runtime_readiness":
        return _build_runtime_readiness_group(checks)
    if group_id == "templates":
        return _build_templates_group(runtime)
    if group_id == "term_rule_sets":
        return _build_term_rule_sets_group(runtime, include_deep=mode == "full")
    if group_id == "translation_profiles":
        return _build_translation_profiles_group(runtime)
    if group_id == "translation_term_sets":
        return _build_translation_term_sets_group(runtime, include_deep=mode == "full")
    raise ValueError(f"unsupported config workbench group: {group_id}")


def _build_dependency_checks(runtime: AppRuntime) -> dict[str, Any]:
    health_service = getattr(runtime, "health_service", None)
    if health_service is None:
        return {
            "p0_document_jobs_required": False,
            "p0_document_jobs_ready": False,
            "p0_document_jobs_blockers": ["health_service_unavailable"],
            "p0_document_jobs_warnings": [],
            "readiness_blockers": ["health_service_unavailable"],
            "readiness_warnings": [],
        }
    return health_service.build_dependency_checks()


def _build_release_gate(checks: dict[str, Any]) -> ConfigWorkbenchReleaseGate:
    required = bool(checks.get("p0_document_jobs_required", False))
    ready = bool(checks.get("p0_document_jobs_ready", not required))
    blockers = _unique_strings(checks.get("p0_document_jobs_blockers", []))
    warnings = _unique_strings(checks.get("p0_document_jobs_warnings", []))
    if required and not ready and not blockers:
        blockers.append("p0_document_jobs_not_ready")
    return ConfigWorkbenchReleaseGate(
        p0_document_jobs_required=required,
        p0_document_jobs_ready=ready,
        blockers=blockers,
        warnings=warnings,
        blocker_findings=[
            _finding(
                code=f"p0.{code}",
                severity="critical",
                message=_readiness_code_message(code),
                route="/system-status",
            )
            for code in blockers
        ],
        warning_findings=[
            _finding(
                code=f"p0.{code}",
                severity="warning",
                message=_readiness_code_message(code),
                route="/system-status",
            )
            for code in warnings
        ],
    )


def _build_runtime_readiness_group(checks: dict[str, Any]) -> ConfigWorkbenchGroup:
    findings: list[ConfigWorkbenchFinding] = []
    for code in _unique_strings(checks.get("readiness_blockers", [])):
        findings.append(
            _finding(
                code=f"runtime.{code}",
                severity="critical",
                message=f"运行就绪检查阻断：{_readiness_code_message(code)}",
                route="/system-status",
            )
        )
    for code in _unique_strings(checks.get("readiness_warnings", [])):
        findings.append(
            _finding(
                code=f"runtime.{code}",
                severity="warning",
                message=f"运行就绪检查告警：{_readiness_code_message(code)}",
                route="/system-status",
            )
        )
    default_label = ", ".join(
        item
        for item in [
            (
                f"元数据存储={checks.get('effective_repository_backend')}"
                if checks.get("effective_repository_backend")
                else ""
            ),
            (
                f"任务执行器={checks.get('document_jobs_worker_backend')}"
                if checks.get("document_jobs_worker_backend")
                else ""
            ),
        ]
        if item
    )
    return _group(
        group_id="runtime_readiness",
        label="运行门禁",
        route="/system-status",
        findings=findings,
        default_label=default_label or None,
    )


def _build_templates_group(runtime: AppRuntime) -> ConfigWorkbenchGroup:
    findings: list[ConfigWorkbenchFinding] = []
    draft_count = 0
    default_label: str | None = None
    route = "/settings/templates"
    try:
        templates = runtime.template_read_service.list_templates(url_for=None)
        default_template = next((item for item in templates if item.is_default), None)
        if default_template is None:
            findings.append(
                _finding(
                    code="templates.default_missing",
                    severity="critical",
                    message="模板缺少默认版本。",
                    route=route,
                )
            )
        else:
            default_label = f"{default_template.id}@{default_template.version}"
            missing_assets = [
                label
                for label, asset in [
                    ("template", default_template.template),
                    ("layout_config", default_template.layout_config),
                    ("subscript_config", default_template.subscript_config),
                ]
                if not asset.exists
            ]
            if missing_assets:
                findings.append(
                    _finding(
                        code="templates.default_asset_missing",
                        severity="critical",
                        message=f"默认模板资产缺失：{', '.join(missing_assets)}。",
                        route=_template_route(default_template.id),
                        target_id=default_template.id,
                    )
                )

        for template in templates:
            versions = runtime.template_read_service.list_template_versions(template.id)
            drafts = [version for version in versions if str(version.status) == DRAFT_VERSION]
            draft_count += len(drafts)
            unverified = [
                version
                for version in drafts
                if not version.verification_job_id or not version.verification_note
            ]
            if drafts:
                findings.append(
                    _finding(
                        code="templates.draft_versions_present",
                        severity="warning",
                        message=f"{template.id} 存在 {len(drafts)} 个草稿版本。",
                        route=_template_route(template.id),
                        target_id=template.id,
                    )
                )
            if unverified:
                findings.append(
                    _finding(
                        code="templates.unverified_draft_versions",
                        severity="warning",
                        message=f"{template.id} 有 {len(unverified)} 个草稿缺少验证证据。",
                        route=_template_route(template.id),
                        target_id=template.id,
                    )
                )
    except (FileNotFoundError, RuntimeError, ValueError):
        findings.append(
            _finding(
                code="templates.read_failed",
                severity="critical",
                message="模板配置读取失败，请进入 Word 模板文档或页面样式配置页排查。",
                route=route,
            )
        )

    return _group(
        group_id="templates",
        label="模板文档与页面样式",
        route=route,
        findings=findings,
        default_label=default_label,
        draft_count=draft_count,
    )


def _build_term_rule_sets_group(runtime: AppRuntime, *, include_deep: bool = True) -> ConfigWorkbenchGroup:
    route = "/settings/term-rule-sets"
    service = getattr(runtime, "term_rule_set_version_service", None)
    if service is None:
        return _group(
            group_id="term_rule_sets",
            label="术语规则集",
            route=route,
            findings=[
                _finding(
                    code="term_rule_sets.unavailable",
                    severity="info",
                    message="当前部署未启用 MySQL 资源版本服务，术语规则集版本治理不可用。",
                    route=route,
                )
            ],
            unavailable=True,
        )

    findings: list[ConfigWorkbenchFinding] = []
    draft_count = 0
    pending_count = 0
    default_label: str | None = None
    try:
        sets = service.list_sets().items
        if not sets:
            findings.append(
                _finding(
                    code="term_rule_sets.empty",
                    severity="critical",
                    message="没有可用的术语规则集。",
                    route=route,
                )
            )

        approved_unpublished_by_set = _approved_unpublished_counts(runtime, [item.id for item in sets])
        pending_review_count = _pending_term_rule_proposal_count(runtime)
        pending_count += pending_review_count + sum(approved_unpublished_by_set.values())
        if pending_review_count:
            findings.append(
                _finding(
                    code="term_rule_sets.pending_review_proposals",
                    severity="warning",
                    message=f"有 {pending_review_count} 条术语建议待审核。",
                    route="/term-proposals?tab=review",
                )
            )

        for item in sets:
            item_route = _settings_route("/settings/term-rule-sets", set_id=item.id)
            if item.default_version and default_label is None:
                default_label = f"{item.id}@{item.default_version}"
            if not item.default_version:
                findings.append(
                    _finding(
                        code="term_rule_sets.default_missing",
                        severity="critical",
                        message=f"{item.id} 缺少默认发布版本。",
                        route=item_route,
                        target_id=item.id,
                    )
                )

            approved_unpublished_count = approved_unpublished_by_set.get(item.id, 0)
            if approved_unpublished_count:
                findings.append(
                    _finding(
                        code="term_rule_sets.approved_unpublished_proposals",
                        severity="warning",
                        message=f"{item.id} 有 {approved_unpublished_count} 条已审核建议尚未随规则集发布。",
                        route=item_route,
                        target_id=item.id,
                    )
                )

            if _resource_record(runtime, "term_rule_set", item.id, DRAFT_VERSION) is None:
                continue
            if not include_deep:
                continue
            preflight = service.build_preflight(
                item.id,
                approved_unpublished_proposal_count=approved_unpublished_count,
            )
            changed_total = (
                preflight.diff_summary.added
                + preflight.diff_summary.updated
                + preflight.diff_summary.disabled
                + preflight.diff_summary.removed
            )
            if changed_total > 0:
                draft_count += 1
                findings.append(
                    _finding(
                        code="term_rule_sets.draft_changes_present",
                        severity="warning",
                        message=f"{item.id} 存在 {changed_total} 条草稿变更。",
                        route=item_route,
                        target_id=item.id,
                    )
                )
            if preflight.blocking:
                findings.append(
                    _finding(
                        code="term_rule_sets.preflight_blocking",
                        severity="critical",
                        message=(
                            f"{item.id} 发布前检查阻断："
                            f"错误 {preflight.summary.error_count} 条，冲突 {preflight.summary.conflict_count} 条。"
                        ),
                        route=item_route,
                        target_id=item.id,
                    )
                )
            elif preflight.summary.warning_count > 0:
                findings.append(
                    _finding(
                        code="term_rule_sets.preflight_warnings",
                        severity="warning",
                        message=f"{item.id} 发布前检查有 {preflight.summary.warning_count} 条告警。",
                        route=item_route,
                        target_id=item.id,
                    )
                )
    except (FileNotFoundError, RuntimeError, ValueError):
        findings.append(
            _finding(
                code="term_rule_sets.read_failed",
                severity="critical",
                message="术语规则集治理数据读取失败。",
                route=route,
            )
        )

    return _group(
        group_id="term_rule_sets",
        label="术语规则集",
        route=route,
        findings=findings,
        default_label=default_label,
        draft_count=draft_count,
        pending_count=pending_count,
        detail_status="complete" if include_deep else "deferred",
    )


def _build_translation_profiles_group(runtime: AppRuntime) -> ConfigWorkbenchGroup:
    route = "/settings/translation-profiles"
    service = getattr(runtime, "translation_profile_service", None)
    if service is None:
        return _group(
            group_id="translation_profiles",
            label="翻译配置",
            route=route,
            findings=[
                _finding(
                    code="translation_profiles.unavailable",
                    severity="info",
                    message="当前部署未启用 MySQL 资源版本服务，翻译配置版本治理不可用。",
                    route=route,
                )
            ],
            unavailable=True,
        )

    findings: list[ConfigWorkbenchFinding] = []
    draft_count = 0
    default_label: str | None = None
    try:
        profiles = service.list_profiles().items
        if not profiles:
            findings.append(
                _finding(
                    code="translation_profiles.empty",
                    severity="warning",
                    message="没有可用的翻译配置。",
                    route=route,
                )
            )
        for profile in profiles:
            profile_route = _settings_route("/settings/translation-profiles", profile_id=profile.id)
            default_record = _resource_record(runtime, "translation_profile", profile.id, profile.default_version or "")
            if profile.default_version and default_label is None:
                default_label = f"{profile.id}@{profile.default_version}"
            if not profile.default_version:
                findings.append(
                    _finding(
                        code="translation_profiles.default_missing",
                        severity="warning",
                        message=f"{profile.id} 缺少默认发布版本，将使用运行环境配置兜底。",
                        route=profile_route,
                        target_id=profile.id,
                    )
                )

            draft_record = _resource_record(runtime, "translation_profile", profile.id, DRAFT_VERSION)
            if draft_record is None:
                continue
            default_snapshot = default_record.snapshot_hash if default_record is not None else None
            if draft_record.snapshot_hash != default_snapshot:
                draft_count += 1
                findings.append(
                    _finding(
                        code="translation_profiles.draft_changes_present",
                        severity="warning",
                        message=f"{profile.id} 存在未发布草稿。",
                        route=profile_route,
                        target_id=profile.id,
                    )
                )
    except (FileNotFoundError, RuntimeError, ValueError):
        findings.append(
            _finding(
                code="translation_profiles.read_failed",
                severity="critical",
                message="翻译配置治理数据读取失败。",
                route=route,
            )
        )

    return _group(
        group_id="translation_profiles",
        label="翻译配置",
        route=route,
        findings=findings,
        default_label=default_label,
        draft_count=draft_count,
    )


def _build_translation_term_sets_group(runtime: AppRuntime, *, include_deep: bool = True) -> ConfigWorkbenchGroup:
    route = "/settings/translation-term-sets"
    service = getattr(runtime, "translation_term_set_version_service", None)
    if service is None:
        return _group(
            group_id="translation_term_sets",
            label="翻译术语集",
            route=route,
            findings=[
                _finding(
                    code="translation_term_sets.unavailable",
                    severity="info",
                    message="当前部署未启用 MySQL 资源版本服务，翻译术语集版本治理不可用。",
                    route=route,
                )
            ],
            unavailable=True,
        )

    findings: list[ConfigWorkbenchFinding] = []
    draft_count = 0
    pending_count = 0
    default_label: str | None = None
    try:
        sets = service.list_sets().items
        if not sets:
            findings.append(
                _finding(
                    code="translation_term_sets.empty",
                    severity="warning",
                    message="没有可用的翻译术语集。",
                    route=route,
                )
            )
        for item in sets:
            item_route = _settings_route("/settings/translation-term-sets", set_id=item.set_id)
            if item.default_version and default_label is None:
                default_label = f"{item.set_id}@{item.default_version}"
            if not item.default_version:
                findings.append(
                    _finding(
                        code="translation_term_sets.default_missing",
                        severity="warning",
                        message=f"{item.set_id} 缺少默认发布版本。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )
            if not include_deep:
                continue

            preflight = service.get_preflight_response(item.set_id)
            changed_total = preflight.diff_summary.added + preflight.diff_summary.removed + preflight.diff_summary.changed
            if item.draft_version and changed_total > 0:
                draft_count += 1
                findings.append(
                    _finding(
                        code="translation_term_sets.draft_changes_present",
                        severity="warning",
                        message=f"{item.set_id} 存在 {changed_total} 条草稿变更。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )
            if preflight.publish_blocked:
                findings.append(
                    _finding(
                        code="translation_term_sets.preflight_blocking",
                        severity="critical",
                        message=f"{item.set_id} 发布前检查阻断发布：{len(preflight.blocking_reasons)} 条原因。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )
            if preflight.validation.warnings:
                findings.append(
                    _finding(
                        code="translation_term_sets.preflight_warnings",
                        severity="warning",
                        message=f"{item.set_id} 发布前检查有 {len(preflight.validation.warnings)} 条告警。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )

            compatibility = service.get_proposal_compatibility_response(item.set_id)
            pending_count += compatibility.summary.total
            if compatibility.summary.conflict > 0:
                findings.append(
                    _finding(
                        code="translation_term_sets.proposal_conflicts",
                        severity="warning",
                        message=f"{item.set_id} 有 {compatibility.summary.conflict} 条待审核建议存在冲突。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )
            if compatibility.summary.warning > 0:
                findings.append(
                    _finding(
                        code="translation_term_sets.proposal_warnings",
                        severity="warning",
                        message=f"{item.set_id} 有 {compatibility.summary.warning} 条待审核建议需要确认。",
                        route=item_route,
                        target_id=item.set_id,
                    )
                )
    except (FileNotFoundError, RuntimeError, ValueError):
        findings.append(
            _finding(
                code="translation_term_sets.read_failed",
                severity="critical",
                message="翻译术语集治理数据读取失败。",
                route=route,
            )
        )

    return _group(
        group_id="translation_term_sets",
        label="翻译术语集",
        route=route,
        findings=findings,
        default_label=default_label,
        draft_count=draft_count,
        pending_count=pending_count,
        detail_status="complete" if include_deep else "deferred",
    )


def _approved_unpublished_counts(runtime: AppRuntime, set_ids: list[str]) -> dict[str, int]:
    service = getattr(runtime, "term_rule_proposal_service", None)
    if service is None:
        return {set_id: 0 for set_id in set_ids}
    return {
        set_id: len(service.list_approved_unpublished_proposals(set_id))
        for set_id in set_ids
    }


def _pending_term_rule_proposal_count(runtime: AppRuntime) -> int:
    service = getattr(runtime, "term_rule_proposal_service", None)
    if service is None:
        return 0
    return len(service.list_proposals(status=TermRuleProposalStatus.PENDING_REVIEW))


def _resource_record(runtime: AppRuntime, resource_type: ResourceType, resource_id: str, version: str):
    if not resource_id or not version:
        return None
    service = getattr(runtime, "resource_version_service", None)
    repository = getattr(service, "repository", None)
    if repository is None:
        return None
    return repository.get_resource_version(resource_type, resource_id, version)


def _group(
    *,
    group_id: ConfigWorkbenchGroupId,
    label: str,
    route: str,
    findings: list[ConfigWorkbenchFinding],
    default_label: str | None = None,
    draft_count: int | None = None,
    pending_count: int | None = None,
    unavailable: bool = False,
    detail_status: ConfigWorkbenchDetailStatus = "complete",
) -> ConfigWorkbenchGroup:
    blocker_count = sum(1 for item in findings if item.severity == "critical")
    warning_count = sum(1 for item in findings if item.severity == "warning")
    if unavailable:
        status: ConfigWorkbenchStatus = "unavailable"
    elif blocker_count:
        status = "blocked"
    elif warning_count:
        status = "warning"
    else:
        status = "ready"
    return ConfigWorkbenchGroup(
        id=group_id,
        label=label,
        status=status,
        detail_status="failed" if any(item.code.endswith(".read_failed") for item in findings) else detail_status,
        route=route,
        default_label=default_label,
        draft_count=draft_count,
        pending_count=pending_count,
        warning_count=warning_count,
        blocker_count=blocker_count,
        findings=findings,
    )


def _finding(
    *,
    code: str,
    severity: ConfigWorkbenchSeverity,
    message: str,
    route: str | None = None,
    target_id: str | None = None,
) -> ConfigWorkbenchFinding:
    return ConfigWorkbenchFinding(
        code=code,
        severity=severity,
        message=message,
        route=route,
        target_id=target_id,
    )


def _overall_status(
    groups: list[ConfigWorkbenchGroup],
    release_gate: ConfigWorkbenchReleaseGate,
) -> ConfigWorkbenchStatus:
    if release_gate.blockers or any(group.status == "blocked" for group in groups):
        return "blocked"
    if release_gate.warnings or any(group.status in {"warning", "unavailable"} for group in groups):
        return "warning"
    return "ready"


def _settings_route(base: str, **query: str) -> str:
    pairs = [
        f"{quote(key, safe='')}={quote(str(value), safe='')}"
        for key, value in query.items()
        if value
    ]
    if not pairs:
        return base
    return f"{base}?{'&'.join(pairs)}"


def _template_route(template_id: str) -> str:
    return f"/settings/templates/{quote(template_id, safe='')}"


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))


READINESS_CODE_MESSAGES: dict[str, str] = {
    "ai_provider_config_invalid": "AI provider 配置文件不可读取或不是合法 JSON。",
    "auth_internal_users_source_missing": "内部账号来源未配置。",
    "auth_jwt_secret_key_missing": "认证签名密钥未配置。",
    "data_dir_not_writable": "数据目录不可写。",
    "default_template_missing": "默认模板文件缺失。",
    "default_translation_unavailable": "默认翻译模式依赖不可用。",
    "document_jobs_celery_broker_url_missing": "文档任务 Celery broker 未配置。",
    "document_jobs_celery_queue_missing": "文档任务 Celery 队列未配置。",
    "document_jobs_translation_batch_celery_queue_missing": "文档翻译批次 Celery 队列未配置。",
    "document_jobs_metadata_store_not_mysql": "生产门禁下文档任务元数据存储必须使用 MySQL。",
    "document_jobs_stale_running_present": "存在长时间未更新的文档任务。",
    "document_jobs_timed_out_present": "存在已超时的文档任务。",
    "document_jobs_worker_backend_disabled": "文档任务执行器被禁用。",
    "document_jobs_worker_backend_eager_in_production": "生产门禁下仍使用 eager 文档任务执行器。",
    "health_service_unavailable": "健康检查服务不可用。",
    "layout_config_missing": "版式配置文件缺失。",
    "mineru_api_token_missing": "MinerU API token 未配置。",
    "mineru_callback_url_missing": "MinerU callback URL 未配置。",
    "mineru_uid_missing": "MinerU UID 未配置。",
    "p0_document_jobs_not_ready": "P0 文档任务执行链路未就绪。",
    "stage_spool_dir_missing": "阶段消息目录缺失。",
    "stage_spool_failed_messages_present": "存在失败的阶段消息。",
    "stage_spool_replayable_messages_present": "存在可继续处理的阶段消息。",
    "stage_spool_stale_running_messages_present": "存在过期运行中的阶段消息。",
    "subscript_config_missing": "下标配置文件缺失。",
    "tmp_dir_missing": "临时目录缺失。",
    "translation_unavailable": "翻译能力不可用。",
}


def _readiness_code_message(code: str) -> str:
    return READINESS_CODE_MESSAGES.get(code, f"未识别的就绪检查项：{code}。")
