"""管理 Translation Profile 版本及其内嵌的命名 Prompt 方案。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta, timezone
from typing import Any
from uuid import uuid4

from app.conversion.runtime import llm_client, translation_runtime
from app.core.config import Settings
from app.domains.audit.models import ActorContext
from app.domains.resources.models import ResourceVersionRecord, ResourceVersionStatus, utc_now
from app.domains.resources.service import ResourceVersionService
from app.domains.translation.models import TranslationProfileSnapshot, TranslationPromptSnapshot
from app.domains.translation.modes import (
    TRANSLATION_MODE_SPECS,
    TRANSLATION_PROFILE_IDS,
    spec_for_language_pair,
    translation_prompt_path,
)
from app.domains.translation.schemas import (
    PROMPT_MARKDOWN_MAX_LENGTH,
    PROMPT_NAME_MAX_LENGTH,
    TranslationProfileDetailResponse,
    TranslationProfileDraftResponse,
    TranslationProfileDraftUpdateRequest,
    TranslationProfileListItemResponse,
    TranslationProfileListResponse,
    TranslationProfilePromptSchemeResponse,
    TranslationProfileVersionResponse,
)


DEFAULT_TRANSLATION_PROFILE_ID = "electronics-en2zh"
DEFAULT_TRANSLATION_PROFILE_IDS = {
    spec.language_pair: spec.default_profile_id
    for spec in TRANSLATION_MODE_SPECS.values()
    if spec.language_pair is not None and spec.default_profile_id is not None
}
DRAFT_VERSION = "draft"
DEFAULT_SEED_PROFILE_VERSION = "seed"
TRANSLATION_PROFILE_SCHEMA_VERSION = 2
TRANSLATION_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
PROMPT_ID_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")
SHANGHAI_TZ = timezone(timedelta(hours=8))
PROFILE_LANGUAGE_PAIRS = {
    spec.default_profile_id: spec.language_pair
    for spec in TRANSLATION_MODE_SPECS.values()
    if spec.language_pair is not None and spec.default_profile_id is not None
}
DEFAULT_PROMPT_VERSIONS = {
    "en2zh": translation_runtime.TRANSLATION_PROMPT_VERSION,
    "ru2zh": "ru2zh@v1",
    "zh2en": "zh2en@v1",
    "zh2ru": "zh2ru@v1",
}
DEFAULT_PROMPT_NAMES = {
    "en2zh": "内置英译中 Prompt",
    "ru2zh": "内置俄译中 Prompt",
    "zh2en": "内置中译英 Prompt",
    "zh2ru": "内置中译俄 Prompt",
}


class TranslationProfileDraftSnapshotConflictError(RuntimeError):
    """客户端基于过期 Profile draft 提交了修改。"""

    def __init__(self, *, expected_snapshot_hash: str, actual_snapshot_hash: str) -> None:
        self.expected_snapshot_hash = expected_snapshot_hash
        self.actual_snapshot_hash = actual_snapshot_hash
        super().__init__("Translation Profile draft 已被其他管理员更新，请刷新后重试。")


def prompt_content_hash(markdown: str) -> str:
    """计算 Prompt 正文的稳定 sha256。"""

    return f"sha256:{hashlib.sha256(markdown.encode('utf-8')).hexdigest()}"


def translation_profile_snapshot_from_record(
    settings: Settings,
    record: ResourceVersionRecord,
) -> TranslationProfileSnapshot:
    """从已绑定资源记录解析执行快照；新格式损坏时禁止回退固定文件。"""

    payload = record.payload
    if payload is None:
        raise ValueError(
            f"Translation Profile payload 缺失: {record.resource_id}@{record.version}"
        )
    language_pair = _profile_language_pair(record.resource_id, payload)
    prompts, active_prompt = _parse_prompt_schemes(
        settings,
        language_pair=language_pair,
        payload=payload,
    )
    del prompts
    return TranslationProfileSnapshot(
        translation_profile_id=record.resource_id,
        language_pair=language_pair,
        version=record.version,
        snapshot_hash=record.snapshot_hash,
        target_language=_payload_text(payload, "target_language") or _default_target_language(language_pair),
        domain=_payload_text(payload, "domain") or translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
        prompt_version=active_prompt.id,
        model=_payload_text(payload, "model"),
        max_pages_per_batch=_payload_int(
            payload,
            "max_pages_per_batch",
            settings.translation_max_pages,
        ),
        max_chars_per_batch=_payload_int(
            payload,
            "max_chars_per_batch",
            settings.translation_max_chars,
        ),
        prompt=active_prompt,
    )


def _profile_language_pair(
    translation_profile_id: str,
    payload: dict[str, Any] | None,
) -> str:
    payload_language_pair = _payload_text(payload, "language_pair")
    if payload_language_pair is not None:
        spec_for_language_pair(payload_language_pair)
        expected = PROFILE_LANGUAGE_PAIRS.get(translation_profile_id)
        if expected is not None and payload_language_pair != expected:
            raise ValueError(
                "Translation Profile language_pair 不匹配: "
                f"expected={expected} actual={payload_language_pair}"
            )
        return payload_language_pair
    language_pair = PROFILE_LANGUAGE_PAIRS.get(translation_profile_id)
    if language_pair is None:
        raise FileNotFoundError(f"Translation Profile 不存在: {translation_profile_id}")
    return language_pair


def _parse_prompt_schemes(
    settings: Settings,
    *,
    language_pair: str,
    payload: dict[str, Any],
) -> tuple[list[TranslationPromptSnapshot], TranslationPromptSnapshot]:
    raw_schemes = payload.get("prompt_schemes")
    schema_version = payload.get("schema_version")
    if raw_schemes is None and schema_version in {None, 1}:
        # 旧发布版本只记录 Prompt ID；固定文件仅在此兼容分支中物化正文。
        prompt_id = _payload_text(payload, "prompt_version") or DEFAULT_PROMPT_VERSIONS[language_pair]
        markdown = _read_seed_prompt(settings, language_pair)
        prompt = TranslationPromptSnapshot(
            id=_normalize_prompt_id(prompt_id),
            name=DEFAULT_PROMPT_NAMES[language_pair],
            markdown=markdown,
            content_hash=prompt_content_hash(markdown),
            built_in=True,
        )
        return [prompt], prompt
    if schema_version != TRANSLATION_PROFILE_SCHEMA_VERSION:
        raise ValueError(
            "不支持的 Translation Profile schema_version: "
            f"{schema_version!r}"
        )
    if not isinstance(raw_schemes, list) or not raw_schemes:
        raise ValueError("Translation Profile prompt_schemes 必须是非空数组。")

    prompts: list[TranslationPromptSnapshot] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for raw_scheme in raw_schemes:
        if not isinstance(raw_scheme, dict):
            raise ValueError("Translation Profile prompt_schemes 包含非法条目。")
        prompt_id = _normalize_prompt_id(_required_text(raw_scheme.get("id"), "Prompt id"))
        name = _normalize_prompt_name(_required_text(raw_scheme.get("name"), "Prompt name"))
        raw_markdown = raw_scheme.get("markdown")
        if not isinstance(raw_markdown, str):
            raise ValueError("Prompt markdown 必须是字符串。")
        markdown = _normalize_prompt_markdown(raw_markdown)
        content_hash = _required_text(raw_scheme.get("content_hash"), "Prompt content_hash")
        built_in = raw_scheme.get("built_in")
        if not isinstance(built_in, bool):
            raise ValueError("Prompt built_in 必须是布尔值。")
        if prompt_id in seen_ids:
            raise ValueError(f"Translation Profile Prompt ID 重复: {prompt_id}")
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            raise ValueError(f"Translation Profile Prompt 名称重复: {name}")
        expected_hash = prompt_content_hash(markdown)
        if content_hash != expected_hash:
            raise ValueError(f"Translation Profile Prompt 正文 hash 不匹配: {prompt_id}")
        seen_ids.add(prompt_id)
        seen_names.add(normalized_name)
        prompts.append(
            TranslationPromptSnapshot(
                id=prompt_id,
                name=name,
                markdown=markdown,
                content_hash=content_hash,
                built_in=built_in,
            )
        )

    active_prompt_id = _normalize_prompt_id(
        _required_text(payload.get("prompt_version"), "prompt_version")
    )
    if not any(prompt.built_in for prompt in prompts):
        raise ValueError("Translation Profile 至少需要一个内置 Prompt。")
    active_prompt = next(
        (prompt for prompt in prompts if prompt.id == active_prompt_id),
        None,
    )
    if active_prompt is None:
        raise ValueError(
            "Translation Profile prompt_version 未指向 prompt_schemes 中的真实方案。"
        )
    return prompts, active_prompt


def _prompt_payload(prompt: TranslationPromptSnapshot) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "name": prompt.name,
        "markdown": prompt.markdown,
        "content_hash": prompt.content_hash,
        "built_in": prompt.built_in,
    }


def _read_seed_prompt(settings: Settings, language_pair: str) -> str:
    path = translation_prompt_path(settings.root_dir, language_pair)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Translation Profile 内置 Prompt 文件不存在: {path}")
    return _normalize_prompt_markdown(path.read_text(encoding="utf-8"))


def _default_target_language(language_pair: str) -> str:
    spec = spec_for_language_pair(language_pair)
    if spec.target_language == "zh":
        return translation_runtime.DEFAULT_TARGET_LANGUAGE
    if spec.target_language is None:
        raise ValueError(f"Translation Profile 缺少目标语言: {language_pair}")
    return spec.target_language


def _normalize_prompt_id(value: str) -> str:
    normalized = value.strip()
    if not PROMPT_ID_RE.fullmatch(normalized):
        raise ValueError(
            "Prompt ID 只能包含大小写字母、数字、下划线、短横线、@ 和英文句点，"
            "长度不超过 128。"
        )
    return normalized


def _normalize_prompt_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Prompt 名称不能为空。")
    if len(normalized) > PROMPT_NAME_MAX_LENGTH:
        raise ValueError(f"Prompt 名称长度不能超过 {PROMPT_NAME_MAX_LENGTH}。")
    return normalized


def _normalize_prompt_markdown(value: str) -> str:
    if not value.strip():
        raise ValueError("Prompt Markdown 不能为空。")
    if len(value) > PROMPT_MARKDOWN_MAX_LENGTH:
        raise ValueError(
            f"Prompt Markdown 长度不能超过 {PROMPT_MARKDOWN_MAX_LENGTH}。"
        )
    return value


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 不能为空。")
    return value.strip()


def _payload_text(payload: dict[str, Any] | None, key: str) -> str | None:
    value = payload.get(key) if payload is not None else None
    return value if isinstance(value, str) and value else None


def _payload_int(payload: dict[str, Any] | None, key: str, default: int) -> int:
    value = payload.get(key) if payload is not None else None
    return (
        int(value)
        if isinstance(value, (int, str)) and not isinstance(value, bool) and str(value).isdigit()
        else max(int(default), 1)
    )


class TranslationProfileVersionService:
    """按语言方向管理内置 Translation Profile。"""

    def __init__(
        self,
        settings: Settings,
        resource_version_service: ResourceVersionService,
        audit_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.resource_version_service = resource_version_service
        self.audit_service = audit_service

    def list_profiles(self) -> TranslationProfileListResponse:
        """列出支持的 Profile 及其默认发布版本。"""

        items: list[TranslationProfileListItemResponse] = []
        for profile_id in TRANSLATION_PROFILE_IDS:
            default_record = self._default_record(profile_id)
            version_records = self._version_records(profile_id)
            record = default_record or self._default_record_from_payload(profile_id)
            snapshot = translation_profile_snapshot_from_record(self.settings, record)
            items.append(
                TranslationProfileListItemResponse(
                    id=profile_id,
                    language_pair=snapshot.language_pair,
                    default_version=default_record.version if default_record is not None else None,
                    version_count=len(version_records),
                    target_language=snapshot.target_language,
                    domain=snapshot.domain,
                    prompt_version=snapshot.prompt_version,
                    prompt_content_hash=snapshot.prompt.content_hash,
                    model=snapshot.model,
                    max_pages_per_batch=snapshot.max_pages_per_batch,
                    max_chars_per_batch=snapshot.max_chars_per_batch,
                )
            )
        return TranslationProfileListResponse(items=items)

    def get_profile_detail(
        self,
        translation_profile_id: str,
    ) -> TranslationProfileDetailResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        default_record = self._default_record(normalized_id)
        return TranslationProfileDetailResponse(
            id=normalized_id,
            default_version=default_record.version if default_record is not None else None,
            versions=[
                self._version_response(record, default_record=default_record)
                for record in self._version_records(normalized_id)
            ],
        )

    def get_draft(
        self,
        translation_profile_id: str,
    ) -> TranslationProfileDraftResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        return self._draft_response(self._ensure_draft_record(normalized_id))

    def update_draft(
        self,
        translation_profile_id: str,
        request: TranslationProfileDraftUpdateRequest,
    ) -> TranslationProfileDraftResponse:
        """更新基础字段，Prompt 列表和当前指针始终沿用同一份草稿。"""

        normalized_id = self._require_known_profile_id(translation_profile_id)
        existing = self._ensure_draft_record(normalized_id)
        existing_payload = existing.payload or {}
        prompts, active_prompt = _parse_prompt_schemes(
            self.settings,
            language_pair=self._profile_language_pair(normalized_id, existing_payload),
            payload=existing_payload,
        )
        base_version = self._payload_text(existing_payload, "base_version")
        if base_version is None:
            default_record = self._default_record(normalized_id)
            base_version = default_record.version if default_record is not None else None
        payload = self._build_payload(
            translation_profile_id=normalized_id,
            version=DRAFT_VERSION,
            base_version=base_version,
            language_pair=self._request_language_pair(
                normalized_id,
                request.language_pair,
            ),
            target_language=request.target_language,
            domain=request.domain,
            prompt_version=active_prompt.id,
            prompt_schemes=prompts,
            model=request.model,
            max_pages_per_batch=request.max_pages_per_batch,
            max_chars_per_batch=request.max_chars_per_batch,
        )
        record = self._save_draft_payload(
            normalized_id,
            payload,
            expected_snapshot_hash=request.expected_snapshot_hash,
        )
        return self._draft_response(record)

    def create_prompt(
        self,
        translation_profile_id: str,
        *,
        name: str,
        source_prompt_id: str,
        expected_snapshot_hash: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileDraftResponse:
        """复制现有方案创建未启用的自定义 Prompt。"""

        profile_id, draft, payload, prompts, active_prompt = self._load_prompt_draft(
            translation_profile_id,
            expected_snapshot_hash,
        )
        normalized_name = _normalize_prompt_name(name)
        self._ensure_unique_prompt_name(prompts, normalized_name)
        normalized_source_id = _normalize_prompt_id(source_prompt_id)
        source = self._require_prompt(prompts, normalized_source_id)
        created = TranslationPromptSnapshot(
            id=f"prompt_{uuid4().hex}",
            name=normalized_name,
            markdown=source.markdown,
            content_hash=source.content_hash,
            built_in=False,
        )
        updated = [*prompts, created]
        record = self._save_prompt_draft(
            profile_id,
            draft,
            payload,
            prompts=updated,
            active_prompt_id=active_prompt.id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
        self._record_prompt_audit(
            actor=actor,
            action="translation_profile.prompt_create",
            profile_id=profile_id,
            prompt=created,
            trace_id=trace_id,
        )
        return self._draft_response(record)

    def update_prompt(
        self,
        translation_profile_id: str,
        prompt_id: str,
        *,
        name: str,
        markdown: str,
        expected_snapshot_hash: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileDraftResponse:
        """保存 Prompt 名称和 Markdown，ID 与 built_in 状态不可由客户端修改。"""

        profile_id, draft, payload, prompts, active_prompt = self._load_prompt_draft(
            translation_profile_id,
            expected_snapshot_hash,
        )
        normalized_prompt_id = _normalize_prompt_id(prompt_id)
        current = self._require_prompt(prompts, normalized_prompt_id)
        normalized_name = _normalize_prompt_name(name)
        self._ensure_unique_prompt_name(
            prompts,
            normalized_name,
            exclude_prompt_id=normalized_prompt_id,
        )
        normalized_markdown = _normalize_prompt_markdown(markdown)
        updated_prompt = TranslationPromptSnapshot(
            id=current.id,
            name=normalized_name,
            markdown=normalized_markdown,
            content_hash=prompt_content_hash(normalized_markdown),
            built_in=current.built_in,
        )
        updated = [
            updated_prompt if prompt.id == normalized_prompt_id else prompt
            for prompt in prompts
        ]
        record = self._save_prompt_draft(
            profile_id,
            draft,
            payload,
            prompts=updated,
            active_prompt_id=active_prompt.id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
        self._record_prompt_audit(
            actor=actor,
            action="translation_profile.prompt_update",
            profile_id=profile_id,
            prompt=updated_prompt,
            trace_id=trace_id,
        )
        return self._draft_response(record)

    def activate_prompt(
        self,
        translation_profile_id: str,
        prompt_id: str,
        *,
        expected_snapshot_hash: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileDraftResponse:
        """仅切换草稿当前 Prompt，不改变线上默认发布版本。"""

        profile_id, draft, payload, prompts, _active_prompt = self._load_prompt_draft(
            translation_profile_id,
            expected_snapshot_hash,
        )
        selected = self._require_prompt(prompts, _normalize_prompt_id(prompt_id))
        record = self._save_prompt_draft(
            profile_id,
            draft,
            payload,
            prompts=prompts,
            active_prompt_id=selected.id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
        self._record_prompt_audit(
            actor=actor,
            action="translation_profile.prompt_activate",
            profile_id=profile_id,
            prompt=selected,
            trace_id=trace_id,
        )
        return self._draft_response(record)

    def delete_prompt(
        self,
        translation_profile_id: str,
        prompt_id: str,
        *,
        expected_snapshot_hash: str,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileDraftResponse:
        """删除从未发布且未启用的自定义 Prompt。"""

        profile_id, draft, payload, prompts, active_prompt = self._load_prompt_draft(
            translation_profile_id,
            expected_snapshot_hash,
        )
        selected = self._require_prompt(prompts, _normalize_prompt_id(prompt_id))
        reason = self._prompt_delete_disabled_reason(
            profile_id,
            selected,
            active_prompt_id=active_prompt.id,
        )
        if reason is not None:
            raise ValueError(reason)
        record = self._save_prompt_draft(
            profile_id,
            draft,
            payload,
            prompts=[prompt for prompt in prompts if prompt.id != selected.id],
            active_prompt_id=active_prompt.id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
        self._record_prompt_audit(
            actor=actor,
            action="translation_profile.prompt_delete",
            profile_id=profile_id,
            prompt=selected,
            trace_id=trace_id,
        )
        return self._draft_response(record)

    def publish_draft(
        self,
        translation_profile_id: str,
        *,
        make_default: bool,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        draft = self._ensure_draft_record(normalized_id)
        version = self._next_version(normalized_id)
        payload = self._build_payload_from_record(
            draft,
            version=version,
            published_at=utc_now(),
        )
        self.resource_version_service.create_draft(
            resource_type="translation_profile",
            resource_id=normalized_id,
            version=version,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"translation_profile:{normalized_id}@{version}",
            payload=payload,
        )
        record = self.resource_version_service.publish(
            "translation_profile",
            normalized_id,
            version,
            make_default=make_default,
        )
        self._record_audit(
            actor=actor,
            action="translation_profile.publish",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def set_default_version(
        self,
        translation_profile_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        record = self._require_version_record(normalized_id, version)
        translation_profile_snapshot_from_record(self.settings, record)
        self.resource_version_service.set_default(
            "translation_profile",
            normalized_id,
            version,
        )
        self._record_audit(
            actor=actor,
            action="translation_profile.set_default",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def rollback(
        self,
        translation_profile_id: str,
        version: str,
        *,
        actor: ActorContext | None = None,
        trace_id: str | None = None,
    ) -> TranslationProfileVersionResponse:
        normalized_id = self._require_known_profile_id(translation_profile_id)
        record = self._require_version_record(normalized_id, version)
        translation_profile_snapshot_from_record(self.settings, record)
        self.resource_version_service.rollback_default(
            "translation_profile",
            normalized_id,
            version,
        )
        self._record_audit(
            actor=actor,
            action="translation_profile.rollback",
            target_id=f"{normalized_id}@{version}",
            trace_id=trace_id,
        )
        return self._version_response(record)

    def resolve_default_snapshot(
        self,
        language_pair: str = "en2zh",
    ) -> TranslationProfileSnapshot | None:
        """解析指定语言方向的默认已发布 Profile。"""

        record = self._default_record(
            self._default_profile_id_for_language_pair(language_pair)
        )
        if record is None:
            return None
        return translation_profile_snapshot_from_record(self.settings, record)

    def bootstrap_default_profiles_if_missing(
        self,
    ) -> list[TranslationProfileVersionResponse]:
        """幂等补齐各语言方向的默认 Profile，不覆盖已有默认指针。"""

        bootstrapped: list[TranslationProfileVersionResponse] = []
        for profile_id in TRANSLATION_PROFILE_IDS:
            if self._default_record(profile_id) is not None:
                continue
            record = self.resource_version_service.repository.get_resource_version(
                "translation_profile",
                profile_id,
                DEFAULT_SEED_PROFILE_VERSION,
            )
            if record is None:
                payload = self._default_payload(
                    profile_id,
                    version=DEFAULT_SEED_PROFILE_VERSION,
                    published_at=utc_now(),
                )
                draft = self.resource_version_service.create_draft(
                    resource_type="translation_profile",
                    resource_id=profile_id,
                    version=DEFAULT_SEED_PROFILE_VERSION,
                    snapshot_hash=self._snapshot_hash(payload),
                    payload_ref=(
                        f"translation_profile:{profile_id}@"
                        f"{DEFAULT_SEED_PROFILE_VERSION}"
                    ),
                    payload=payload,
                )
                record = self.resource_version_service.publish(
                    draft.resource_type,
                    draft.resource_id,
                    draft.version,
                    make_default=True,
                )
            elif record.status == ResourceVersionStatus.DRAFT:
                translation_profile_snapshot_from_record(self.settings, record)
                record = self.resource_version_service.publish(
                    record.resource_type,
                    record.resource_id,
                    record.version,
                    make_default=True,
                )
            elif record.status == ResourceVersionStatus.PUBLISHED:
                translation_profile_snapshot_from_record(self.settings, record)
                self.resource_version_service.set_default(
                    record.resource_type,
                    record.resource_id,
                    record.version,
                )
            else:
                raise ValueError(
                    "Translation Profile seed 版本不可作为默认版本: "
                    f"{profile_id}@{DEFAULT_SEED_PROFILE_VERSION}"
                )
            bootstrapped.append(
                self._version_response(record, default_record=record)
            )
        return bootstrapped

    def _load_prompt_draft(
        self,
        translation_profile_id: str,
        expected_snapshot_hash: str,
    ) -> tuple[
        str,
        ResourceVersionRecord,
        dict[str, Any],
        list[TranslationPromptSnapshot],
        TranslationPromptSnapshot,
    ]:
        profile_id = self._require_known_profile_id(translation_profile_id)
        draft = self._ensure_draft_record(profile_id)
        expected = expected_snapshot_hash.strip()
        if not expected:
            raise ValueError("expected_snapshot_hash 不能为空。")
        if draft.snapshot_hash != expected:
            raise TranslationProfileDraftSnapshotConflictError(
                expected_snapshot_hash=expected,
                actual_snapshot_hash=draft.snapshot_hash,
            )
        payload = draft.payload or {}
        prompts, active_prompt = _parse_prompt_schemes(
            self.settings,
            language_pair=self._profile_language_pair(profile_id, payload),
            payload=payload,
        )
        return profile_id, draft, payload, prompts, active_prompt

    def _save_prompt_draft(
        self,
        profile_id: str,
        draft: ResourceVersionRecord,
        payload: dict[str, Any],
        *,
        prompts: list[TranslationPromptSnapshot],
        active_prompt_id: str,
        expected_snapshot_hash: str,
    ) -> ResourceVersionRecord:
        next_payload = self._build_payload(
            translation_profile_id=profile_id,
            version=DRAFT_VERSION,
            base_version=self._payload_text(payload, "base_version"),
            language_pair=self._profile_language_pair(profile_id, payload),
            target_language=(
                self._payload_text(payload, "target_language")
                or _default_target_language(self._profile_language_pair(profile_id, payload))
            ),
            domain=(
                self._payload_text(payload, "domain")
                or translation_runtime.DEFAULT_TRANSLATION_DOMAIN
            ),
            prompt_version=active_prompt_id,
            prompt_schemes=prompts,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(
                payload,
                "max_pages_per_batch",
                self.settings.translation_max_pages,
            ),
            max_chars_per_batch=self._payload_int(
                payload,
                "max_chars_per_batch",
                self.settings.translation_max_chars,
            ),
        )
        return self._save_draft_payload(
            profile_id,
            next_payload,
            expected_snapshot_hash=expected_snapshot_hash,
            existing=draft,
        )

    def _save_draft_payload(
        self,
        profile_id: str,
        payload: dict[str, Any],
        *,
        expected_snapshot_hash: str | None,
        existing: ResourceVersionRecord | None = None,
    ) -> ResourceVersionRecord:
        current = existing or self._ensure_draft_record(profile_id)
        expected = (
            expected_snapshot_hash.strip()
            if expected_snapshot_hash is not None
            else current.snapshot_hash
        )
        if not expected:
            raise ValueError("expected_snapshot_hash 不能为空。")
        if current.snapshot_hash != expected:
            raise TranslationProfileDraftSnapshotConflictError(
                expected_snapshot_hash=expected,
                actual_snapshot_hash=current.snapshot_hash,
            )
        record = self.resource_version_service.update_draft_if_current(
            resource_type="translation_profile",
            resource_id=profile_id,
            version=DRAFT_VERSION,
            expected_snapshot_hash=expected,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=f"translation_profile:{profile_id}@{DRAFT_VERSION}",
            payload=payload,
        )
        if record is None:
            actual = self.resource_version_service.repository.get_resource_version(
                "translation_profile",
                profile_id,
                DRAFT_VERSION,
            )
            raise TranslationProfileDraftSnapshotConflictError(
                expected_snapshot_hash=expected,
                actual_snapshot_hash=(
                    actual.snapshot_hash if actual is not None else "missing"
                ),
            )
        return record

    def _ensure_draft_record(
        self,
        translation_profile_id: str,
    ) -> ResourceVersionRecord:
        existing = self.resource_version_service.repository.get_resource_version(
            "translation_profile",
            translation_profile_id,
            DRAFT_VERSION,
        )
        if existing is not None:
            if existing.status != ResourceVersionStatus.DRAFT:
                raise ValueError("Translation Profile draft 指针指向了非 draft 版本。")
            payload = existing.payload or {}
            if (
                payload.get("schema_version") == TRANSLATION_PROFILE_SCHEMA_VERSION
                and isinstance(payload.get("prompt_schemes"), list)
            ):
                translation_profile_snapshot_from_record(self.settings, existing)
                return existing
            # 旧草稿在首次读取时物化内置 Prompt 并持久化为 schema v2。
            upgraded_payload = self._build_payload_from_record(
                existing,
                version=DRAFT_VERSION,
            )
            upgraded = self.resource_version_service.update_draft_if_current(
                resource_type="translation_profile",
                resource_id=translation_profile_id,
                version=DRAFT_VERSION,
                expected_snapshot_hash=existing.snapshot_hash,
                snapshot_hash=self._snapshot_hash(upgraded_payload),
                payload_ref=(
                    f"translation_profile:{translation_profile_id}@"
                    f"{DRAFT_VERSION}"
                ),
                payload=upgraded_payload,
            )
            if upgraded is None:
                refreshed = self.resource_version_service.repository.get_resource_version(
                    "translation_profile",
                    translation_profile_id,
                    DRAFT_VERSION,
                )
                if refreshed is None:
                    raise RuntimeError("Translation Profile draft 兼容升级失败。")
                return refreshed
            return upgraded

        default_record = self._default_record(translation_profile_id)
        payload = (
            self._build_payload_from_record(
                default_record,
                version=DRAFT_VERSION,
                base_version=default_record.version,
            )
            if default_record is not None
            else self._default_payload(translation_profile_id)
        )
        return self.resource_version_service.create_draft(
            resource_type="translation_profile",
            resource_id=translation_profile_id,
            version=DRAFT_VERSION,
            snapshot_hash=self._snapshot_hash(payload),
            payload_ref=(
                f"translation_profile:{translation_profile_id}@{DRAFT_VERSION}"
            ),
            payload=payload,
        )

    def _default_payload(
        self,
        translation_profile_id: str,
        *,
        version: str = DRAFT_VERSION,
        base_version: str | None = None,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        language_pair = self._profile_language_pair(
            translation_profile_id,
            None,
        )
        markdown = _read_seed_prompt(self.settings, language_pair)
        prompt = TranslationPromptSnapshot(
            id=DEFAULT_PROMPT_VERSIONS[language_pair],
            name=DEFAULT_PROMPT_NAMES[language_pair],
            markdown=markdown,
            content_hash=prompt_content_hash(markdown),
            built_in=True,
        )
        return self._build_payload(
            translation_profile_id=translation_profile_id,
            version=version,
            base_version=base_version,
            language_pair=language_pair,
            target_language=_default_target_language(language_pair),
            domain=translation_runtime.DEFAULT_TRANSLATION_DOMAIN,
            prompt_version=prompt.id,
            prompt_schemes=[prompt],
            model=self.settings.openai_model or llm_client.DEFAULT_MODEL,
            max_pages_per_batch=self.settings.translation_max_pages,
            max_chars_per_batch=self.settings.translation_max_chars,
            published_at=published_at,
        )

    def _default_record_from_payload(
        self,
        translation_profile_id: str,
    ) -> ResourceVersionRecord:
        payload = self._default_payload(translation_profile_id)
        return ResourceVersionRecord(
            resource_type="translation_profile",
            resource_id=translation_profile_id,
            version=DRAFT_VERSION,
            status=ResourceVersionStatus.DRAFT,
            snapshot_hash=self._snapshot_hash(payload),
            payload=payload,
        )

    def _version_records(
        self,
        translation_profile_id: str,
    ) -> list[ResourceVersionRecord]:
        return [
            record
            for record in self.resource_version_service.repository.list_resource_versions(
                "translation_profile",
                translation_profile_id,
            )
            if record.version != DRAFT_VERSION
        ]

    def _default_record(
        self,
        translation_profile_id: str,
    ) -> ResourceVersionRecord | None:
        return self.resource_version_service.repository.get_default_resource_version(
            "translation_profile",
            translation_profile_id,
        )

    def _require_version_record(
        self,
        translation_profile_id: str,
        version: str,
    ) -> ResourceVersionRecord:
        record = self.resource_version_service.repository.get_resource_version(
            "translation_profile",
            translation_profile_id,
            version,
        )
        if record is None:
            raise FileNotFoundError(
                "Translation Profile 版本不存在: "
                f"{translation_profile_id}@{version}"
            )
        return record

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        target_id: str,
        trace_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if actor is None or self.audit_service is None:
            return
        self.audit_service.record(
            actor=actor,
            action=action,
            target_type="translation_profile",
            target_id=target_id,
            trace_id=trace_id or "",
            details=details,
        )

    def _record_prompt_audit(
        self,
        *,
        actor: ActorContext | None,
        action: str,
        profile_id: str,
        prompt: TranslationPromptSnapshot,
        trace_id: str | None,
    ) -> None:
        self._record_audit(
            actor=actor,
            action=action,
            target_id=f"{profile_id}/{prompt.id}",
            trace_id=trace_id,
            details={
                "profile_id": profile_id,
                "prompt_id": prompt.id,
                "prompt_content_hash": prompt.content_hash,
                "prompt_char_count": len(prompt.markdown),
                "built_in": prompt.built_in,
            },
        )

    def _build_payload_from_record(
        self,
        record: ResourceVersionRecord,
        *,
        version: str,
        base_version: str | None = None,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        payload = record.payload or {}
        language_pair = self._profile_language_pair(record.resource_id, payload)
        prompts, active_prompt = _parse_prompt_schemes(
            self.settings,
            language_pair=language_pair,
            payload=payload,
        )
        return self._build_payload(
            translation_profile_id=record.resource_id,
            version=version,
            base_version=(
                base_version
                if base_version is not None
                else self._payload_text(payload, "base_version")
            ),
            language_pair=language_pair,
            target_language=(
                self._payload_text(payload, "target_language")
                or _default_target_language(language_pair)
            ),
            domain=(
                self._payload_text(payload, "domain")
                or translation_runtime.DEFAULT_TRANSLATION_DOMAIN
            ),
            prompt_version=active_prompt.id,
            prompt_schemes=prompts,
            model=self._payload_text(payload, "model"),
            max_pages_per_batch=self._payload_int(
                payload,
                "max_pages_per_batch",
                self.settings.translation_max_pages,
            ),
            max_chars_per_batch=self._payload_int(
                payload,
                "max_chars_per_batch",
                self.settings.translation_max_chars,
            ),
            published_at=published_at,
        )

    def _build_payload(
        self,
        *,
        translation_profile_id: str,
        version: str,
        base_version: str | None,
        language_pair: str,
        target_language: str,
        domain: str,
        prompt_version: str,
        prompt_schemes: list[TranslationPromptSnapshot],
        model: str | None,
        max_pages_per_batch: int,
        max_chars_per_batch: int,
        published_at: Any | None = None,
    ) -> dict[str, Any]:
        payload = {
            "schema_version": TRANSLATION_PROFILE_SCHEMA_VERSION,
            "translation_profile_id": translation_profile_id,
            "language_pair": self._normalize_required_text(
                language_pair,
                "language_pair",
            ),
            "version": version,
            "base_version": base_version,
            "target_language": self._normalize_required_text(
                target_language,
                "target_language",
            ),
            "domain": self._normalize_required_text(domain, "domain"),
            "prompt_version": _normalize_prompt_id(prompt_version),
            "prompt_schemes": [_prompt_payload(prompt) for prompt in prompt_schemes],
            "model": self._normalize_optional_text(model),
            "max_pages_per_batch": max(int(max_pages_per_batch), 1),
            "max_chars_per_batch": max(int(max_chars_per_batch), 1),
            "published_at": (
                published_at.isoformat()
                if hasattr(published_at, "isoformat")
                else published_at
            ),
        }
        _parse_prompt_schemes(
            self.settings,
            language_pair=language_pair,
            payload=payload,
        )
        return payload

    def _draft_response(
        self,
        record: ResourceVersionRecord,
    ) -> TranslationProfileDraftResponse:
        snapshot = translation_profile_snapshot_from_record(self.settings, record)
        payload = record.payload or {}
        prompts, active_prompt = _parse_prompt_schemes(
            self.settings,
            language_pair=snapshot.language_pair,
            payload=payload,
        )
        return TranslationProfileDraftResponse(
            translation_profile_id=record.resource_id,
            language_pair=snapshot.language_pair,
            base_version=self._payload_text(payload, "base_version"),
            target_language=snapshot.target_language,
            domain=snapshot.domain,
            prompt_version=active_prompt.id,
            prompt_schemes=[
                self._prompt_response(
                    record.resource_id,
                    prompt,
                    active_prompt_id=active_prompt.id,
                )
                for prompt in prompts
            ],
            model=snapshot.model,
            max_pages_per_batch=snapshot.max_pages_per_batch,
            max_chars_per_batch=snapshot.max_chars_per_batch,
            snapshot_hash=record.snapshot_hash,
        )

    def _prompt_response(
        self,
        profile_id: str,
        prompt: TranslationPromptSnapshot,
        *,
        active_prompt_id: str,
    ) -> TranslationProfilePromptSchemeResponse:
        reason = self._prompt_delete_disabled_reason(
            profile_id,
            prompt,
            active_prompt_id=active_prompt_id,
        )
        return TranslationProfilePromptSchemeResponse(
            id=prompt.id,
            name=prompt.name,
            markdown=prompt.markdown,
            content_hash=prompt.content_hash,
            built_in=prompt.built_in,
            is_active=prompt.id == active_prompt_id,
            deletable=reason is None,
            delete_disabled_reason=reason,
        )

    def _version_response(
        self,
        record: ResourceVersionRecord,
        *,
        default_record: ResourceVersionRecord | None = None,
    ) -> TranslationProfileVersionResponse:
        snapshot = translation_profile_snapshot_from_record(self.settings, record)
        payload = record.payload or {}
        default = (
            default_record
            if default_record is not None
            else self._default_record(record.resource_id)
        )
        return TranslationProfileVersionResponse(
            translation_profile_id=record.resource_id,
            language_pair=snapshot.language_pair,
            version=record.version,
            status=record.status.value,
            snapshot_hash=record.snapshot_hash,
            is_default=default is not None and default.version == record.version,
            target_language=snapshot.target_language,
            domain=snapshot.domain,
            prompt_version=snapshot.prompt_version,
            prompt_content_hash=snapshot.prompt.content_hash,
            model=snapshot.model,
            max_pages_per_batch=snapshot.max_pages_per_batch,
            max_chars_per_batch=snapshot.max_chars_per_batch,
            published_at=self._payload_text(payload, "published_at"),
        )

    def _prompt_delete_disabled_reason(
        self,
        profile_id: str,
        prompt: TranslationPromptSnapshot,
        *,
        active_prompt_id: str,
    ) -> str | None:
        if prompt.built_in:
            return "内置 Prompt 不能删除。"
        if prompt.id == active_prompt_id:
            return "当前启用 Prompt 不能删除，请先切换当前方案。"
        for record in self._version_records(profile_id):
            payload = record.payload or {}
            if self._published_payload_references_prompt(payload, prompt.id):
                return "该 Prompt 已随历史 Profile 版本发布，不能物理删除。"
        return None

    def _published_payload_references_prompt(
        self,
        payload: dict[str, Any],
        prompt_id: str,
    ) -> bool:
        raw_schemes = payload.get("prompt_schemes")
        if isinstance(raw_schemes, list):
            return any(
                isinstance(item, dict) and item.get("id") == prompt_id
                for item in raw_schemes
            )
        return self._payload_text(payload, "prompt_version") == prompt_id

    def _next_version(self, translation_profile_id: str) -> str:
        prefix = utc_now().astimezone(SHANGHAI_TZ).strftime("%Y.%m.%d-")
        max_suffix = 0
        for record in self.resource_version_service.repository.list_resource_versions(
            "translation_profile",
            translation_profile_id,
        ):
            if not record.version.startswith(prefix):
                continue
            suffix = record.version.removeprefix(prefix)
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
        return f"{prefix}{max_suffix + 1}"

    def _request_language_pair(
        self,
        translation_profile_id: str,
        requested_language_pair: str | None,
    ) -> str:
        expected = self._profile_language_pair(translation_profile_id, None)
        normalized = self._normalize_optional_text(requested_language_pair)
        if normalized is None:
            return expected
        if normalized != expected:
            raise ValueError(
                "Translation Profile language_pair 不匹配: "
                f"expected={expected} actual={normalized}"
            )
        return normalized

    def _profile_language_pair(
        self,
        translation_profile_id: str,
        payload: dict[str, Any] | None,
    ) -> str:
        return _profile_language_pair(translation_profile_id, payload)

    def _default_profile_id_for_language_pair(self, language_pair: str) -> str:
        spec = spec_for_language_pair(language_pair)
        if spec.default_profile_id is None:
            raise FileNotFoundError(
                f"Translation Profile 不存在: {language_pair}"
            )
        return spec.default_profile_id

    @staticmethod
    def _snapshot_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    @staticmethod
    def _payload_text(
        payload: dict[str, Any] | None,
        key: str,
    ) -> str | None:
        return _payload_text(payload, key)

    @staticmethod
    def _payload_int(
        payload: dict[str, Any] | None,
        key: str,
        default: int,
    ) -> int:
        return _payload_int(payload, key, default)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} 不能为空。")
        return normalized

    @staticmethod
    def _require_prompt(
        prompts: list[TranslationPromptSnapshot],
        prompt_id: str,
    ) -> TranslationPromptSnapshot:
        prompt = next((item for item in prompts if item.id == prompt_id), None)
        if prompt is None:
            raise FileNotFoundError(f"Translation Profile Prompt 不存在: {prompt_id}")
        return prompt

    @staticmethod
    def _ensure_unique_prompt_name(
        prompts: list[TranslationPromptSnapshot],
        name: str,
        *,
        exclude_prompt_id: str | None = None,
    ) -> None:
        normalized_name = name.casefold()
        if any(
            prompt.id != exclude_prompt_id
            and prompt.name.casefold() == normalized_name
            for prompt in prompts
        ):
            raise ValueError(f"Translation Profile Prompt 名称重复: {name}")

    @staticmethod
    def _require_known_profile_id(translation_profile_id: str) -> str:
        normalized = translation_profile_id.strip()
        if not TRANSLATION_PROFILE_ID_RE.match(normalized):
            raise ValueError(
                "translation_profile_id 只能包含大小写字母、数字、下划线、"
                "短横线和英文句点，长度不超过 128。"
            )
        if normalized not in TRANSLATION_PROFILE_IDS:
            raise FileNotFoundError(f"Translation Profile 不存在: {normalized}")
        return normalized
