from __future__ import annotations

# app/services/renderer/semantic_text.py: 提供 DocumentIR Word 渲染器的文本语义归一化 helper。

import re
from html import unescape


WRAPPER_RE = re.compile(r"\\(?:mathrm|mathsf|text)\s*\{([^{}]+)\}")
CONTROL_WORD_RE = re.compile(r"\\([A-Za-z]+)")
SQRT_RE = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
INLINE_TEX_RE = re.compile(r"\$(?P<dollar>[^$\n]+)\$|\\\((?P<paren>.*?)\\\)")
SIMPLE_EXPR_RE = re.compile(
    r"(?P<base>[A-Za-zΑ-Ωα-ωΔΨθρμπμΩ]+[A-Za-z0-9Α-Ωα-ωΔΨθρμπμΩ]*)"
    r"(?:_(?:\{(?P<sub_braced>[^{}]+)\}|(?P<sub_plain>[A-Za-z0-9()+/\-]+)))?"
    r"(?:\^(?:\{(?P<sup_braced>[^{}]+)\}|(?P<sup_plain>\([^)]+\)|[A-Za-z0-9()+/\-]+)))?"
)
SUP_ONLY_EXPR_RE = re.compile(
    r"(?P<base>[A-Za-zΑ-Ωα-ωΔΨθρμπμΩ]+[A-Za-z0-9Α-Ωα-ωΔΨθρμπμΩ]*)"
    r"\^(?P<sup>\([^)]+\)|[A-Za-z0-9()+/\-]+)"
)
SPACED_ALPHA_TOKEN_RE = re.compile(r"\b(?:[A-Za-z]\s+){1,}[A-Za-z]\b")
SPACED_DIGIT_TOKEN_RE = re.compile(r"\b(?:\d\s+){1,}\d\b")
LIST_MARKER_RE = re.compile(r"^\s*(?:[•■*]|[-–—])\s+")

GREEK_AND_TEXT_COMMANDS = {
    "Delta": "Δ",
    "delta": "δ",
    "Theta": "Θ",
    "theta": "θ",
    "mu": "μ",
    "Omega": "Ω",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "lambda": "λ",
    "rho": "ρ",
    "psi": "ψ",
    "phi": "φ",
    "pm": "±",
    "circ": "°",
    "vee": "V",
    "to": "to",
    "max": "max",
    "min": "min",
    "typ": "typ",
    "avg": "avg",
    "rms": "RMS",
    "pk": "pk",
    "pp": "pp",
}


def normalize_formula_text(text: str) -> str:
    """把常见 TeX 片段转成可由现有 rich text helper 消费的安全内联标记。"""

    if not text:
        return ""
    normalized = unescape(text)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"<eq>\s*(.*?)\s*</eq>", r"\1", normalized, flags=re.IGNORECASE | re.DOTALL)
    normalized = re.sub(r"\$+\s*(.*?)\s*\$+", r"\1", normalized, flags=re.DOTALL)
    normalized = normalize_tex_text(normalized)
    normalized = convert_inline_tex_to_html(normalized)
    normalized = re.sub(r"\s+,", ",", normalized)
    normalized = re.sub(r"([±+\-])\s+(\d)", r"\1\2", normalized)
    normalized = re.sub(r"(\d)\s*°\s*([CFK])\b", r"\1°\2", normalized)
    normalized = re.sub(r"([A-Za-zµμ])\s+Ω\b", r"\1Ω", normalized)
    normalized = re.sub(r"/\s+√", "/√", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" ?\n ?", "\n", normalized)
    return normalized.strip()


def normalize_tex_text(text: str) -> str:
    normalized = text
    prev = None
    while prev != normalized:
        prev = normalized
        normalized = SQRT_RE.sub(lambda match: f"√{compact_math_token_runs(match.group(1) or '')}", normalized)
        normalized = WRAPPER_RE.sub(lambda match: compact_math_token_runs(match.group(1) or ""), normalized)

    normalized = CONTROL_WORD_RE.sub(replace_control_word, normalized)
    normalized = normalized.replace(r"\_", "_")
    normalized = normalized.replace(r"\{", "{").replace(r"\}", "}")
    normalized = normalized.replace(r"\(", "(").replace(r"\)", ")")
    normalized = normalized.replace(r"\ ", " ")
    normalized = re.sub(r"\s*_\s*", "_", normalized)
    normalized = re.sub(r"\s*\^\s*", "^", normalized)
    normalized = re.sub(r"\^\s*\{\s*", "^{", normalized)
    normalized = re.sub(r"_\s*\{\s*", "_{", normalized)
    normalized = re.sub(r"\{\s*", "{", normalized)
    normalized = re.sub(r"\s*\}", "}", normalized)
    normalized = normalized.replace("^{°}", "°")
    normalized = compact_math_token_runs(normalized)
    return normalized


def convert_inline_tex_to_html(text: str) -> str:
    if not text:
        return ""

    def replace_inline(match: re.Match[str]) -> str:
        expr = match.group("dollar") if match.group("dollar") is not None else match.group("paren")
        return convert_simple_tex_expr(expr or match.group(0))

    converted = INLINE_TEX_RE.sub(replace_inline, text)
    converted = SIMPLE_EXPR_RE.sub(lambda match: convert_simple_tex_expr(match.group(0)), converted)
    converted = SUP_ONLY_EXPR_RE.sub(lambda match: convert_simple_tex_expr(match.group(0)), converted)
    return converted


def convert_simple_tex_expr(expr: str) -> str:
    cleaned = clean_tex_fragment(expr)
    match = SIMPLE_EXPR_RE.fullmatch(cleaned.strip())
    if not match:
        sup_only_match = SUP_ONLY_EXPR_RE.fullmatch(cleaned.strip())
        if not sup_only_match:
            return cleaned
        base = clean_tex_fragment(sup_only_match.group("base") or "")
        sup = clean_tex_fragment(sup_only_match.group("sup") or "")
        return f"{base}<sup>{sup}</sup>" if sup else base

    base = clean_tex_fragment(match.group("base") or "")
    sub = clean_tex_fragment(match.group("sub_braced") or match.group("sub_plain") or "")
    sup = clean_tex_fragment(match.group("sup_braced") or match.group("sup_plain") or "")
    if not sub and not sup:
        return base

    result = base
    if sub:
        result += f"<sub>{sub}</sub>"
    if sup:
        result += f"<sup>{sup}</sup>"
    return result


def clean_tex_fragment(text: str) -> str:
    cleaned = text.strip()
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = SQRT_RE.sub(lambda match: f"√{compact_math_token_runs(match.group(1) or '')}", cleaned)
        cleaned = WRAPPER_RE.sub(lambda match: compact_math_token_runs(match.group(1) or ""), cleaned)

    cleaned = CONTROL_WORD_RE.sub(replace_control_word, cleaned)
    cleaned = cleaned.replace(r"\_", "_")
    cleaned = cleaned.replace(r"\{", "{").replace(r"\}", "}")
    cleaned = cleaned.replace(r"\(", "(").replace(r"\)", ")")
    cleaned = cleaned.replace(r"\ ", " ")
    cleaned = compact_math_token_runs(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"([ΔδΘθμΩαβγλρψφ])\s+([A-Za-z])", r"\1\2", cleaned)
    return cleaned


def compact_math_token_runs(text: str) -> str:
    compacted = text
    prev = None
    while prev != compacted:
        prev = compacted
        compacted = SPACED_ALPHA_TOKEN_RE.sub(lambda match: match.group(0).replace(" ", ""), compacted)
        compacted = SPACED_DIGIT_TOKEN_RE.sub(lambda match: match.group(0).replace(" ", ""), compacted)
    return compacted


def replace_control_word(match: re.Match[str]) -> str:
    return GREEK_AND_TEXT_COMMANDS.get(match.group(1), match.group(0))


def normalize_list_item(text: str) -> str:
    normalized = text.strip()
    while True:
        match = LIST_MARKER_RE.match(normalized)
        if match is None:
            return normalized
        normalized = normalized[match.end() :].strip()


def infer_list_item_level(text: str) -> int:
    """从 MinerU 常见 dash marker 粗略推断一个嵌套层级。"""

    return 1 if re.match(r"^\s*[-–—]\s+", text or "") else 0
