"""纯内存技术 Token Codec；尚未接入 Provider、翻译回填或 Worker。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from app.domains.translation.models import TranslationTextItem


class ProtectedTokenKind(str, Enum):
    """静态分类；规则的扩展必须同时提供精确跨度和自然语言反例。"""

    URL = "url"
    EMAIL = "email"
    FORMULA = "formula"
    LITERAL_PLACEHOLDER = "literal_placeholder"
    ADDRESS = "address"
    BIT_FIELD = "bit_field"
    MODEL = "model"
    STANDARD = "standard"
    VERSION = "version"
    SIGNAL = "signal"
    QUANTITY = "quantity"
    UNIT = "unit"
    NUMBER = "number"
    SYMBOL = "symbol"
    TECHNICAL_LITERAL = "technical_literal"


@dataclass(frozen=True, slots=True)
class ProtectedTokenOccurrence:
    """一次出现的原始字符偏移；敏感原文不进入默认 repr。"""

    item_id: str
    kind: ProtectedTokenKind
    start: int
    end: int
    placeholder: str
    original_text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class EncodedTokenBatch:
    """编码文本与只读 ledger 必须同批持有，不能作为 Provider 映射发送。"""

    item_ids: tuple[str, ...]
    namespace: str
    items: tuple[TranslationTextItem, ...] = field(repr=False)
    occurrences: tuple[ProtectedTokenOccurrence, ...] = field(repr=False)


_ERROR_MESSAGES = {
    "protected_token_invalid_input": "技术 Token 编解码输入无效。",
    "protected_token_item_mismatch": "技术 Token 返回项的 ID 序列与原批次不一致。",
    "protected_token_missing": "技术 Token 返回项缺少占位符。",
    "protected_token_duplicate": "技术 Token 返回项包含重复占位符。",
    "protected_token_unknown": "技术 Token 返回项包含未知占位符。",
    "protected_token_wrong_item": "技术 Token 占位符不属于当前返回项。",
    "protected_token_malformed": "技术 Token 返回项包含损坏的占位语法。",
}


class ProtectedTokenError(ValueError):
    """仅携带机器码与非正文诊断；异常消息不包含原文或返回文本。"""

    def __init__(self, code: str, *, item_id: str | None = None) -> None:
        self.code = code
        self.item_id = item_id
        super().__init__(_ERROR_MESSAGES[code])


_GAP = r"[\s\u200b\u200c\u200d\ufeff]*"
_FAMILY = _GAP.join("MD2W_PT")
_PLACEHOLDER_RE = re.compile(r"\{\{MD2W_PT_v1_(?:0|[1-9][0-9]*)_[1-9][0-9]*\}\}")
_EXACT_RESERVED_RE = re.compile(rf"{_PLACEHOLDER_RE.pattern}|\{{\{{PH_[0-9]+\}}\}}", re.IGNORECASE)
# 同一个扫描器同时保护源文字面量与拒绝返回变体，避免源文往返被误拒绝。
# 仅括号后带保留家族标识的片段属于保留语法；不吞掉 {{NAME}} 或普通 PH 单词。
_RESERVED_RE = re.compile(
    rf"[{{\[(]+{_GAP}(?:{_FAMILY}|P{_GAP}H(?=[_\s\d\u200b\u200c\u200d\ufeff]))"
    r"[A-Za-z0-9_ \t\u00a0\u200b\u200c\u200d\ufeff]*[}\])]*",
    re.IGNORECASE,
)
_SPACE = r"[ \t\u00a0]*"
_UNSIGNED_NUMBER = r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+−-]?[0-9]+)?"
_SIGNED_NUMBER = rf"[+−±-]?{_UNSIGNED_NUMBER}"
_VALUE = (
    rf"(?:<=|>=|[<>≤≥≈~])?{_SPACE}{_SIGNED_NUMBER}"
    rf"(?:{_SPACE}(?:[–—−-]|\bto\b|\.\.|…|±|\+/-){_SPACE}{_SIGNED_NUMBER})?"
)
_UNIT_ATOM = (
    r"(?:[pnumkMGTµμ]?(?:Hz|V|A|Ω|F|H|W|s|m)|°[CF]|K|%|dB|S|"
    r"(?:мк|м|к|М|н|п)?(?:Гц|Ом|В|А|Ф|Вт|с))"
    r"(?:\^?[−-]?[0-9]+|[²³])?"
)
_UNIT = (
    rf"{_UNIT_ATOM}(?:{_SPACE}[/·⋅*]{_SPACE}"
    rf"(?:sqrt\({_UNIT_ATOM}\)|√{_UNIT_ATOM}|{_UNIT_ATOM}))*"
)
_QUANTITY = rf"{_VALUE}{_SPACE}{_UNIT}"
_LEFT = r"(?<![A-Za-z0-9_])"
_RIGHT = r"(?![A-Za-z0-9_])"
_IDENTIFIER = r"[A-Za-zΑ-Ωα-ω][A-Za-zΑ-Ωα-ω0-9]*(?:_[A-Za-zΑ-Ωα-ω0-9]+)*"
_LHS = r"(?:[A-Z][A-Z0-9]{0,4}|[A-Za-zΑ-Ωα-ω]|[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)"
_MATH_ATOM = rf"(?:{_QUANTITY}|{_SIGNED_NUMBER}|{_IDENTIFIER})"
_EXPRESSION = rf"{_MATH_ATOM}(?:{_SPACE}[+−*/^\-]{_SPACE}{_MATH_ATOM})+"
_ASSIGNMENT = rf"{_LEFT}{_LHS}{_SPACE}={_SPACE}(?:{_EXPRESSION}|{_QUANTITY}|{_SIGNED_NUMBER}|[A-Z][A-Z0-9_]*){_RIGHT}"
_TECHNICAL_LITERALS = frozenset({"ADC", "DAC", "PLL", "I2C", "SPI", "UART", "USB", "JEDEC"})

# 顺序即类别优先级；同级按最长、起点和规则顺序选择，始终匹配原文。
_RULES: tuple[tuple[int, ProtectedTokenKind, re.Pattern[str]], ...] = tuple(
    (priority, kind, re.compile(pattern))
    for priority, kind, pattern in (
        (1, ProtectedTokenKind.URL, r"\b(?:https?://|ftp://|www\.)[^\s<>\"$]+"),
        (1, ProtectedTokenKind.EMAIL, rf"{_LEFT}[A-Za-z0-9.!#$%&'*+/=?^_`{{|}}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+{_RIGHT}"),
        (2, ProtectedTokenKind.FORMULA, r"\$\$[\s\S]+?\$\$|(?<!\$)\$(?!\$)[^$\r\n]+\$(?!\$)|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]"),
        (2, ProtectedTokenKind.FORMULA, _ASSIGNMENT),
        (3, ProtectedTokenKind.LITERAL_PLACEHOLDER, _RESERVED_RE.pattern),
        (4, ProtectedTokenKind.ADDRESS, rf"{_LEFT}0[xX][0-9A-Fa-f]+(?:\[[0-9]+(?::[0-9]+)?\])?{_RIGHT}"),
        (4, ProtectedTokenKind.BIT_FIELD, rf"{_LEFT}(?:[A-Z][A-Z0-9_]*)?\[[0-9]+:[0-9]+\]{_RIGHT}"),
        (5, ProtectedTokenKind.STANDARD, rf"{_LEFT}(?:IEEE{_SPACE}[0-9]+(?:\.[0-9]+)*[a-z]*|(?:IEC|ISO){_SPACE}[0-9]+(?:-[0-9]+)*){_RIGHT}"),
        (5, ProtectedTokenKind.VERSION, rf"{_LEFT}v?[0-9]+(?:\.[0-9]+){{2,}}(?:[-+][A-Za-z0-9.-]+)?{_RIGHT}|{_LEFT}v[0-9]+\.[0-9]+{_RIGHT}"),
        (5, ProtectedTokenKind.MODEL, rf"{_LEFT}(?:[A-Z][A-Z0-9]*[0-9][A-Z0-9]*(?:[-/+][A-Z0-9]+)*|(?:SOIC|QFN|DIP|TSSOP|SOT|BGA)-[0-9]+){_RIGHT}"),
        (6, ProtectedTokenKind.SIGNAL, rf"{_LEFT}(?:{_IDENTIFIER}_[A-Za-zΑ-Ωα-ω0-9]+|VCC|VDD|VSS|GND|VIN|VOUT|RESET|CLK){_RIGHT}"),
        (7, ProtectedTokenKind.QUANTITY, rf"{_LEFT}{_QUANTITY}{_RIGHT}"),
        (8, ProtectedTokenKind.NUMBER, rf"{_LEFT}{_VALUE}{_RIGHT}"),
        (8, ProtectedTokenKind.SYMBOL, rf"(?:<=|>=|[<>≤≥≈±])(?={_SPACE}[A-Za-zΑ-Ωα-ω][A-Za-z0-9_]*)"),
        (9, ProtectedTokenKind.TECHNICAL_LITERAL, rf"{_LEFT}(?:{'|'.join(sorted(_TECHNICAL_LITERALS))}){_RIGHT}"),
    )
)
_STANDALONE_UNIT_RE = re.compile(rf"\s*(?P<unit>{_UNIT})\s*\Z")


def _reserved_matches(text: str) -> list[re.Match[str]]:
    """完整语法先认领；外侧普通括号不能抢占其中完整的占位符。"""

    matches = list(_EXACT_RESERVED_RE.finditer(text))
    occupied = bytearray(len(text))
    for match in matches:
        occupied[match.start():match.end()] = b"\1" * (match.end() - match.start())
    for match in _RESERVED_RE.finditer(text):
        if not any(occupied[match.start():match.end()]):
            matches.append(match)
    return sorted(matches, key=lambda match: match.start())


def _validate_items(items: tuple[TranslationTextItem, ...], *, unique: bool) -> None:
    if not isinstance(items, tuple):
        raise ProtectedTokenError("protected_token_invalid_input")
    ids: set[str] = set()
    for item in items:
        if (
            not isinstance(item, TranslationTextItem)
            or not isinstance(item.id, str)
            or not item.id.strip()
            or not isinstance(item.text, str)
            or (unique and item.id in ids)
        ):
            raise ProtectedTokenError("protected_token_invalid_input")
        ids.add(item.id)


def _spans(text: str) -> list[tuple[int, int, ProtectedTokenKind]]:
    candidates: list[tuple[int, int, int, int, ProtectedTokenKind]] = []
    for rule_index, (priority, kind, pattern) in enumerate(_RULES):
        matches = _reserved_matches(text) if kind == ProtectedTokenKind.LITERAL_PLACEHOLDER else pattern.finditer(text)
        for match in matches:
            start, end = match.span()
            if kind == ProtectedTokenKind.URL:
                closing_pairs = {")": "(", "]": "[", "}": "{"}
                while end > start:
                    last = text[end - 1]
                    if last in ".,;:!?" or (
                        last in closing_pairs
                        and text.count(last, start, end) > text.count(closing_pairs[last], start, end)
                    ):
                        end -= 1
                    else:
                        break
            elif kind == ProtectedTokenKind.LITERAL_PLACEHOLDER:
                while end > start and text[end - 1].isspace():
                    end -= 1
            elif kind == ProtectedTokenKind.MODEL and match.group() in _TECHNICAL_LITERALS:
                continue
            # 数值的前导空白不属于 Token；符号后的内部空白仍保持原始切片。
            if kind in {ProtectedTokenKind.NUMBER, ProtectedTokenKind.QUANTITY}:
                while start < end and text[start].isspace():
                    start += 1
            candidates.append((priority, start, end, rule_index, kind))
    unit_match = _STANDALONE_UNIT_RE.fullmatch(text)
    if unit_match:
        start, end = unit_match.span("unit")
        candidates.append((7, start, end, len(_RULES), ProtectedTokenKind.UNIT))
    occupied = bytearray(len(text))
    selected: list[tuple[int, int, ProtectedTokenKind]] = []
    for _priority, start, end, _rule_index, kind in sorted(
        candidates, key=lambda candidate: (candidate[0], -(candidate[2] - candidate[1]), candidate[1], candidate[3])
    ):
        fragments = [(start, end)]
        if any(occupied[start:end]):
            if kind != ProtectedTokenKind.LITERAL_PLACEHOLDER:
                continue
            # URL/公式仍整体优先，但不能把其外侧的残缺保留前缀裸留给 decode。
            fragments = []
            cursor = start
            while cursor < end:
                if occupied[cursor]:
                    cursor += 1
                    continue
                fragment_start = cursor
                while cursor < end and not occupied[cursor]:
                    cursor += 1
                fragments.append((fragment_start, cursor))
        for fragment_start, fragment_end in fragments:
            occupied[fragment_start:fragment_end] = b"\1" * (fragment_end - fragment_start)
            selected.append((fragment_start, fragment_end, kind))
    return sorted(selected, key=lambda span: span[0])


def encode(items: tuple[TranslationTextItem, ...]) -> EncodedTokenBatch:
    """以完整有序批次编码；每次出现独立编号，不改变任何未选中的字符。"""

    _validate_items(items, unique=True)
    namespace_index = 0
    while True:
        namespace = f"{{{{MD2W_PT_v1_{namespace_index}_"
        if not any(namespace in item.text for item in items):
            break
        namespace_index += 1
    encoded: list[TranslationTextItem] = []
    occurrences: list[ProtectedTokenOccurrence] = []
    for item in items:
        parts: list[str] = []
        cursor = 0
        for start, end, kind in _spans(item.text):
            placeholder = f"{namespace}{len(occurrences) + 1}}}}}"
            occurrences.append(ProtectedTokenOccurrence(item.id, kind, start, end, placeholder, item.text[start:end]))
            parts.extend((item.text[cursor:start], placeholder))
            cursor = end
        parts.append(item.text[cursor:])
        encoded.append(TranslationTextItem(id=item.id, text="".join(parts)))
    return EncodedTokenBatch(tuple(item.id for item in items), namespace, tuple(encoded), tuple(occurrences))


def decode(
    items: tuple[TranslationTextItem, ...], batch: EncodedTokenBatch
) -> tuple[TranslationTextItem, ...]:
    """先验证整批身份与每次出现，再一次性还原；合法的恢复值不会被递归扫描。"""

    _validate_items(items, unique=False)
    if not isinstance(batch, EncodedTokenBatch):
        raise ProtectedTokenError("protected_token_invalid_input")
    if tuple(item.id for item in items) != batch.item_ids:
        raise ProtectedTokenError("protected_token_item_mismatch")

    ledger = {occurrence.placeholder: occurrence for occurrence in batch.occurrences}
    counts: Counter[str] = Counter()
    scans: list[list[re.Match[str]]] = []
    # 所有 item 的语法与归属错误优先于缺失/重复；此阶段不构造任何还原结果。
    for item in items:
        matches = _reserved_matches(item.text)
        scans.append(matches)
        for match in matches:
            placeholder = match.group().rstrip()
            if _PLACEHOLDER_RE.fullmatch(placeholder) is None:
                raise ProtectedTokenError("protected_token_malformed", item_id=item.id)
            occurrence = ledger.get(placeholder)
            if occurrence is None:
                raise ProtectedTokenError("protected_token_unknown", item_id=item.id)
            if occurrence.item_id != item.id:
                raise ProtectedTokenError("protected_token_wrong_item", item_id=item.id)
            counts[placeholder] += 1
    for occurrence in batch.occurrences:
        if counts[occurrence.placeholder] == 0:
            raise ProtectedTokenError("protected_token_missing", item_id=occurrence.item_id)
    for occurrence in batch.occurrences:
        if counts[occurrence.placeholder] != 1:
            raise ProtectedTokenError("protected_token_duplicate", item_id=occurrence.item_id)

    decoded: list[TranslationTextItem] = []
    for item, matches in zip(items, scans):
        parts: list[str] = []
        cursor = 0
        for match in matches:
            placeholder = match.group().rstrip()
            end = match.start() + len(placeholder)
            parts.extend((item.text[cursor:match.start()], ledger[placeholder].original_text))
            cursor = end
        parts.append(item.text[cursor:])
        decoded.append(TranslationTextItem(id=item.id, text="".join(parts)))
    return tuple(decoded)
