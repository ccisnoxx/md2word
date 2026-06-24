from __future__ import annotations

# app/services/renderer/semantic_text.py: 兼容导出正式 renderer 使用的共享文本语义规则。

from app.conversion.docx_rules.text_semantics import (
    clean_tex_fragment,
    collapse_double_escaped_tex_commands,
    compact_math_token_runs,
    convert_inline_tex_to_html,
    convert_simple_tex_expr,
    infer_heading_level,
    infer_list_item_level,
    is_list_item_text,
    is_toc_title_text,
    looks_like_english_heading_text,
    looks_like_heading_text,
    normalize_formula_text,
    normalize_heading_probe_text,
    normalize_list_item,
    normalize_tex_text,
    parse_toc_entry_text,
    replace_control_word,
    replace_overline_expr,
    unwrap_tex_text_wrappers,
)

__all__ = [
    "clean_tex_fragment",
    "collapse_double_escaped_tex_commands",
    "compact_math_token_runs",
    "convert_inline_tex_to_html",
    "convert_simple_tex_expr",
    "infer_heading_level",
    "infer_list_item_level",
    "is_list_item_text",
    "is_toc_title_text",
    "looks_like_english_heading_text",
    "looks_like_heading_text",
    "normalize_formula_text",
    "normalize_heading_probe_text",
    "normalize_list_item",
    "normalize_tex_text",
    "parse_toc_entry_text",
    "replace_control_word",
    "replace_overline_expr",
    "unwrap_tex_text_wrappers",
]
