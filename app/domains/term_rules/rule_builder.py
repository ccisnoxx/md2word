"""Shared construction helpers for persisted term rule records."""

from __future__ import annotations

# File: app/domains/term_rules/rule_builder.py
# Purpose: Build persisted term rule records from API-facing mutation payloads.

from typing import Any

from app.domains.term_rules.models import (
    RuleApplyScope,
    RuleMode,
    RuleRenderType,
    TermRuleRecord,
    TermRuleScopeType,
    TermRuleSegmentRecord,
    normalize_term_key,
)
from app.domains.term_rules.yaml_codec import render_segments_html, render_segments_markdown


def build_term_rule_record(
    *,
    rule_id: str,
    category_id: str,
    source_term: str,
    apply_scope: str,
    case_sensitive: bool,
    enabled: bool,
    priority: int,
    segments: list[dict[str, Any]],
    custom_html: str | None,
    custom_markdown: str | None,
    notes: str,
    scope_type: TermRuleScopeType | None = TermRuleScopeType.GLOBAL,
    scope_id: str | None = None,
    active: bool = True,
    current_version: int = 1,
    created_at: Any | None = None,
) -> TermRuleRecord:
    """Build a `TermRuleRecord` using the shared live/draft mutation rules."""

    parsed_segments = build_term_rule_segments(segments)
    try:
        parsed_apply_scope = RuleApplyScope(str(apply_scope).strip().lower())
    except ValueError as exc:
        raise ValueError(f"不支持的 apply_scope: {apply_scope}") from exc
    resolved_custom_html = custom_html if custom_html is not None else render_segments_html(parsed_segments)
    resolved_custom_markdown = custom_markdown if custom_markdown is not None else render_segments_markdown(parsed_segments)
    return TermRuleRecord(
        id=rule_id,
        category_id=category_id,
        source_term=source_term,
        normalized_term=normalize_term_key(source_term),
        scope_type=scope_type or TermRuleScopeType.GLOBAL,
        scope_id=scope_id,
        active=active,
        current_version=current_version,
        rule_mode=RuleMode.SIMPLE if len(parsed_segments) <= 2 else RuleMode.ADVANCED,
        apply_scope=parsed_apply_scope,
        case_sensitive=case_sensitive,
        enabled=enabled,
        priority=int(priority),
        segments=parsed_segments,
        custom_html=resolved_custom_html,
        custom_markdown=resolved_custom_markdown,
        notes=str(notes or ""),
        **({"created_at": created_at} if created_at is not None else {}),
    )


def build_term_rule_segments(raw_segments: list[dict[str, Any]]) -> list[TermRuleSegmentRecord]:
    """Convert API segment payloads into sequential persisted rule segments."""

    if not raw_segments:
        raise ValueError("segments 必须是非空数组")
    segments: list[TermRuleSegmentRecord] = []
    for index, raw_segment in enumerate(raw_segments):
        segment_text = str(raw_segment.get("segment_text", "") or "")
        if not segment_text:
            raise ValueError("segment_text 不能为空")
        render_type_value = str(raw_segment.get("render_type", "") or "").strip().lower()
        try:
            render_type = RuleRenderType(render_type_value)
        except ValueError as exc:
            raise ValueError(f"不支持的 render_type: {render_type_value}") from exc
        segments.append(
            TermRuleSegmentRecord(
                seq=index + 1,
                segment_text=segment_text,
                render_type=render_type,
            )
        )
    return segments
