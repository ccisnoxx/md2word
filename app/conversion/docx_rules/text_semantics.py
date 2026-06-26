"""Shared text, formula, heading, list, and TOC semantics for DOCX rendering."""

from __future__ import annotations

# File: app/conversion/docx_rules/text_semantics.py
# Purpose: Keep local runtime and formal DocumentIR renderer text semantics aligned.

import re
from html import unescape


WRAPPER_RE = re.compile(r"\\(?:mathrm|mathsf|text)\s*\{([^{}]+)\}")
TEXT_WRAPPER_START_RE = re.compile(r"\\(?:mathrm|mathsf|text)\s*\{")
CONTROL_WORD_RE = re.compile(r"\\([A-Za-z]+)")
SQRT_RE = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
OVERLINE_RE = re.compile(r"\\overline\s*\{([^{}]*)\}")
DOUBLE_ESCAPED_TEX_COMMAND_RE = re.compile(
    r"\\{2,}(?=(?:mathrm|mathsf|text|sqrt|overline|Delta|delta|Theta|theta|mu|Omega|alpha|beta|gamma|lambda|rho|psi|phi|pm|circ|vee|to|max|min|typ|avg|rms|pk|pp)\b)"
)
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
LEADING_SUP_EXPR_RE = re.compile(r"\^(?:\{(?P<sup_braced>[^{}]+)\}|(?P<sup_plain>\([^)]+\)|[A-Za-z0-9()+/\-]+))")
SPACED_ALPHA_TOKEN_RE = re.compile(r"\b(?:[A-Za-z]\s+){1,}[A-Za-z]\b")
SPACED_DIGIT_TOKEN_RE = re.compile(r"\b(?:\d\s+){1,}\d\b")
LIST_MARKER_RE = re.compile(r"^\s*(?:[•■*]|[-–—])\s+")
NUMBERED_HEADING_RE = re.compile(r"^(?P<num>\d+(?:\.\d+){0,5})\b")
CHAPTER_HEADING_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百千零〇两\d]+(章|节|部分)\b|(?:chapter|section|part)\s+(?:[ivxlcdm]+|\d+)\b)",
    re.IGNORECASE,
)
HEADING_NUMBER_RE = re.compile(
    r"^(?:\d+[.、]|\d+\.\d+|附录[A-Z\d.\-]+|appendix\s+[A-Z\d.\-]+|(?:表|table|图|figure)\s*[A-Z\d.\-]+)",
    re.IGNORECASE,
)
TOC_TITLE_RE = re.compile(r"^(目录|table of contents|contents)\b", re.IGNORECASE)
TOC_ENTRY_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+|\d+[.、]|\d+\.\d+|附录\s*[A-Z\d.\-]+|appendix\s+[A-Z\d.\-]+|"
    r"(?:table|figure)\s*[A-Z\d.\-]+|(?:chapter|section|part)\s+(?:[ivxlcdm]+|\d+))",
    re.IGNORECASE,
)
TOC_EXPLICIT_LEADER_ENTRY_RE = re.compile(r"^(?P<title>.+?)(?:\s*[.·。…]{2,}\s*)(?P<page>\d+)\s*$")
TOC_ENTRY_WITH_PAGE_RE = re.compile(r"^(?P<title>.+?)\s+(?P<page>\d+)\s*$")
TRAILING_PAGE_NOISE_RE = re.compile(r"(?:[.\s·。…]{2,}|\s+)\d+\s*$")
ENGLISH_HEADING_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9/&()\-]*")
ENGLISH_HEADING_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
}
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
    """Convert common MinerU/TeX fragments to safe inline HTML-like markup."""

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
    normalized = re.sub(r"°\s+([CFK])\b", r"°\1", normalized)
    normalized = re.sub(r"([µμ])\s+([A-Za-z])\b", r"\1\2", normalized)
    normalized = re.sub(r"([A-Za-zµμ])\s+Ω\b", r"\1Ω", normalized)
    normalized = re.sub(r"([A-Za-zµμΩ°])\s*/\s*([°√A-Za-zµμΩ])", r"\1/\2", normalized)
    normalized = re.sub(r"/\s+√", "/√", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" ?\n ?", "\n", normalized)
    return normalized.strip()


def normalize_tex_text(text: str) -> str:
    normalized = collapse_double_escaped_tex_commands(text)
    normalized = unwrap_tex_text_wrappers(normalized)
    prev = None
    while prev != normalized:
        prev = normalized
        normalized = SQRT_RE.sub(lambda match: f"√{compact_math_token_runs(match.group(1) or '')}", normalized)
        normalized = WRAPPER_RE.sub(lambda match: compact_math_token_runs(match.group(1) or ""), normalized)
        normalized = OVERLINE_RE.sub(replace_overline_expr, normalized)

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
    normalized = normalized.replace("^°", "°")
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
    converted = LEADING_SUP_EXPR_RE.sub(
        lambda match: f"<sup>{clean_tex_fragment(match.group('sup_braced') or match.group('sup_plain') or '')}</sup>",
        converted,
    )
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
    cleaned = collapse_double_escaped_tex_commands(text.strip())
    cleaned = unwrap_tex_text_wrappers(cleaned)
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


def collapse_double_escaped_tex_commands(text: str) -> str:
    return DOUBLE_ESCAPED_TEX_COMMAND_RE.sub(r"\\", text)


def unwrap_tex_text_wrappers(text: str) -> str:
    result: list[str] = []
    index = 0
    while True:
        match = TEXT_WRAPPER_START_RE.search(text, index)
        if match is None:
            result.append(text[index:])
            return "".join(result)

        result.append(text[index : match.start()])
        content_start = match.end()
        depth = 1
        position = content_start
        while position < len(text) and depth > 0:
            char = text[position]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            position += 1

        if depth != 0:
            result.append(text[match.start() :])
            return "".join(result)

        inner = text[content_start : position - 1]
        if "{" in inner or "}" in inner:
            result.append(unwrap_tex_text_wrappers(inner))
        else:
            result.append(text[match.start() : position])
        index = position


def replace_control_word(match: re.Match[str]) -> str:
    return GREEK_AND_TEXT_COMMANDS.get(match.group(1), match.group(0))


def replace_overline_expr(match: re.Match[str]) -> str:
    content = clean_tex_fragment(match.group(1) or "")
    if re.search(r"[=<>+\-*/]|\s", content):
        return content
    return "".join(f"{char}\u0305" for char in content)


def normalize_list_item(text: str) -> str:
    normalized = text.strip()
    while True:
        match = LIST_MARKER_RE.match(normalized)
        if match is None:
            return normalized
        normalized = normalized[match.end() :].strip()


def is_list_item_text(text: str) -> bool:
    return LIST_MARKER_RE.match(text or "") is not None


def infer_list_item_level(text: str) -> int:
    return 1 if re.match(r"^\s*[-–—]\s+", text or "") else 0


def normalize_heading_probe_text(text: str) -> str:
    cleaned = " ".join((text or "").replace("\n", " ").split())
    cleaned = TRAILING_PAGE_NOISE_RE.sub("", cleaned)
    cleaned = cleaned.replace("..", " ").replace(" .", " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def infer_heading_level(text: str) -> int:
    cleaned = normalize_heading_probe_text(text)
    match = NUMBERED_HEADING_RE.match(cleaned)
    if match:
        numbering = match.group("num")
        return min(numbering.count(".") + 1, 3)
    if CHAPTER_HEADING_RE.match(cleaned):
        return 1
    if re.match(r"^(?:附录|appendix\b)", cleaned, re.IGNORECASE):
        return 1
    return 2


def parse_toc_entry_text(text: str) -> tuple[str, str] | None:
    cleaned = " ".join((text or "").replace("\n", " ").split()).strip()
    if not cleaned:
        return None
    parsed = _split_toc_entry_text(cleaned)
    if parsed is None:
        return None
    title, page, has_explicit_leader = parsed
    if not title or not page or len(title) > 120:
        return None
    # Explicit dot leaders are the TOC signal for translated datasheet entries
    # that no longer start with English numbering or Appendix/Table prefixes.
    if not has_explicit_leader and not TOC_ENTRY_RE.match(title):
        return None
    return title, page


def is_toc_title_text(text: str) -> bool:
    cleaned = " ".join((text or "").replace("\n", " ").split()).strip()
    return bool(cleaned and parse_toc_entry_text(cleaned) is None and TOC_TITLE_RE.match(cleaned))


def _split_toc_entry_text(text: str) -> tuple[str, str, bool] | None:
    explicit_match = TOC_EXPLICIT_LEADER_ENTRY_RE.match(text)
    if explicit_match is not None:
        return explicit_match.group("title").strip(" .·。…"), explicit_match.group("page").strip(), True

    match = TOC_ENTRY_WITH_PAGE_RE.match(text)
    if match is None:
        return None
    return match.group("title").strip(" .·。…"), match.group("page").strip(), False


def looks_like_heading_text(text: str) -> bool:
    cleaned = normalize_heading_probe_text(text)
    if len(cleaned) > 80:
        return False
    if re.match(r"^\d+\.[A-Z]", cleaned):
        return False
    return bool(
        HEADING_NUMBER_RE.match(cleaned)
        or CHAPTER_HEADING_RE.match(cleaned)
        or looks_like_english_heading_text(cleaned)
    )


def looks_like_english_heading_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 60:
        return False
    if stripped[-1] in ".!?;:":
        return False

    tokens = ENGLISH_HEADING_TOKEN_RE.findall(stripped)
    if not 1 <= len(tokens) <= 8:
        return False

    significant_chars = sum(1 for char in stripped if char.isalpha() or char.isdigit())
    token_chars = sum(len(token) for token in tokens)
    if token_chars < significant_chars * 0.7:
        return False

    acceptable = 0
    for token in tokens:
        lowered = token.lower()
        if lowered in ENGLISH_HEADING_STOPWORDS or token.isupper() or token[0].isupper():
            acceptable += 1

    return acceptable >= max(len(tokens) - 1, 1)
