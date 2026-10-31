"""正式翻译的纯完整性边界；技术识别和占位恢复仍由 Codec 唯一拥有。"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace

from app.domains.translation.models import TranslationProviderResult, TranslationTextItem
from app.domains.translation.protected_tokens import EncodedTokenBatch, ProtectedTokenError, decode, encode


INTEGRITY_SCHEMA_VERSION = "translation-integrity/v1"
INTEGRITY_VALIDATOR_VERSION = "translation-integrity-validator/v1"
INTEGRITY_CODEC_VERSION = "MD2W_PT_v1"
INTEGRITY_INSTRUCTION_VERSION = "translation-integrity-instructions/v1"
INTEGRITY_INSTRUCTION = (
    "Translation integrity protocol: translation-integrity-instructions/v1. "
    "This protocol takes precedence over conflicting technical rewriting instructions above. "
    "Return exactly one JSON object containing only an items array; each item has only id and text strings. "
    "Keep every id and item order unchanged. Preserve each {{MD2W_PT_v1_n_k}} placeholder exactly once "
    "in its original item; do not alter, split, duplicate, remove, invent, or transfer placeholders. "
    "Translate natural language only. Never add technical numbers, units, addresses, models, or formulas. "
    "Do not localize or normalize technical content. Return no Markdown fences or surrounding prose."
)
INTEGRITY_INSTRUCTION_SHA256 = "sha256:" + hashlib.sha256(INTEGRITY_INSTRUCTION.encode("utf-8")).hexdigest()

_MESSAGES = {
    "translation_integrity_invalid_input": "翻译完整性源输入无效。",
    "translation_integrity_metadata_mismatch": "翻译完整性编码批次与源输入不一致。",
    "translation_integrity_invalid_response": "翻译返回项的结构、类型或非空约束无效。",
    "translation_integrity_item_duplicate": "翻译返回项包含重复 ID。",
    "translation_integrity_item_missing": "翻译返回项缺少预期 ID。",
    "translation_integrity_item_extra": "翻译返回项包含额外 ID。",
    "translation_integrity_item_order": "翻译返回项的 ID 顺序不一致。",
    "translation_integrity_placeholder_missing": "翻译返回项缺少技术占位符。",
    "translation_integrity_placeholder_duplicate": "翻译返回项包含重复技术占位符。",
    "translation_integrity_placeholder_unknown": "翻译返回项包含未知技术占位符。",
    "translation_integrity_placeholder_wrong_item": "翻译技术占位符不属于当前返回项。",
    "translation_integrity_placeholder_malformed": "翻译返回项的技术占位语法损坏。",
    "translation_integrity_technical_mismatch": "翻译恢复后的逐项技术内容或出现次数不一致。",
    "translation_integrity_evidence_missing": "翻译批次缺少完整性证据。",
    "translation_integrity_evidence_mismatch": "翻译批次完整性证据与当前来源不一致。",
    "translation_request_budget_exceeded": "翻译请求编码后的文本字符数超过批次限额。",
}
_CODEC_ERROR_CODES = {
    "protected_token_missing": "translation_integrity_placeholder_missing",
    "protected_token_duplicate": "translation_integrity_placeholder_duplicate",
    "protected_token_unknown": "translation_integrity_placeholder_unknown",
    "protected_token_wrong_item": "translation_integrity_placeholder_wrong_item",
    "protected_token_malformed": "translation_integrity_placeholder_malformed",
}


@dataclass(frozen=True, slots=True)
class TranslationIntegrityBinding:
    """由执行入口提供的本地权威关联；不查询仓储、不保存正文或 ledger。"""

    job_id: str
    batch_id: str
    root_batch_id: str
    parent_batch_id: str | None
    attempt: int
    generation: int
    source_document_ir_file_id: str
    source_document_ir_sha256: str
    profile_snapshot_hash: str | None
    prompt_content_hash: str | None
    term_snapshot_hash: str | None


@dataclass(frozen=True, slots=True)
class TranslationIntegrityEvidence:
    """只含版本、哈希、计数和受信关联的不可变摘要。"""

    status: str
    stage: str
    error_code: str | None
    expected_item_count: int
    actual_item_count: int | None
    checked_item_count: int
    failed_item_count: int
    source_char_count: int
    encoded_char_count: int | None
    response_char_count: int | None
    restored_char_count: int | None
    source_sha256: str
    encoded_sha256: str | None
    response_sha256: str | None
    restored_sha256: str | None
    expected_token_counts: tuple[tuple[str, int], ...]
    actual_token_counts: tuple[tuple[str, int], ...] | None
    schema_version: str = INTEGRITY_SCHEMA_VERSION
    validator_version: str = INTEGRITY_VALIDATOR_VERSION
    codec_version: str = INTEGRITY_CODEC_VERSION
    instruction_version: str = INTEGRITY_INSTRUCTION_VERSION
    instruction_sha256: str = INTEGRITY_INSTRUCTION_SHA256
    binding: TranslationIntegrityBinding | None = None

    def bind(self, binding: TranslationIntegrityBinding) -> TranslationIntegrityEvidence:
        """生成当前调用的关联副本，不修改原证据。"""
        return replace(self, binding=binding)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["expected_token_counts"] = dict(self.expected_token_counts)
        payload["actual_token_counts"] = dict(self.actual_token_counts) if self.actual_token_counts is not None else None
        return payload


@dataclass(frozen=True, slots=True)
class ValidatedTranslationBatch:
    """整批通过后才产生恢复文本；默认表示不包含任何正文。"""

    items: tuple[TranslationTextItem, ...] = field(repr=False)
    evidence: TranslationIntegrityEvidence

    @property
    def replacements(self) -> dict[str, str]:
        return {item.id: item.text for item in self.items}


class TranslationIntegrityError(ValueError):
    """安全机器码和同形证据；没有可消费的部分译文。"""

    def __init__(self, code: str, evidence: TranslationIntegrityEvidence) -> None:
        self.code = code
        self.evidence = replace(evidence, status="failed", error_code=code)
        super().__init__(_MESSAGES[code])


def items_sha256(items: tuple[TranslationTextItem, ...]) -> str:
    """规范化有序 id/text JSON 的哈希，供受控 Artifact 消费边界重核。"""
    payload = [{"id": item.id, "text": item.text} for item in items]
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _token_counts(batch: EncodedTokenBatch) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(Counter(token.kind.value for token in batch.occurrences).items()))


def _inventory(batch: EncodedTokenBatch) -> dict[str, Counter]:
    inventory = {item_id: Counter() for item_id in batch.item_ids}
    for token in batch.occurrences:
        inventory[token.item_id][(token.kind, token.original_text)] += 1
    return inventory


def _valid_items(items: object, *, unique: bool) -> bool:
    if not isinstance(items, tuple):
        return False
    ids: set[str] = set()
    for item in items:
        if (
            not isinstance(item, TranslationTextItem)
            or not isinstance(item.id, str) or not item.id.strip()
            or not isinstance(item.text, str) or not item.text.strip()
            or (unique and item.id in ids)
        ):
            return False
        ids.add(item.id)
    return True


def _evidence(
    source: tuple[TranslationTextItem, ...],
    encoded: EncodedTokenBatch | None = None,
    response: tuple[TranslationTextItem, ...] | None = None,
    restored: tuple[TranslationTextItem, ...] | None = None,
    *, stage: str,
) -> TranslationIntegrityEvidence:
    return TranslationIntegrityEvidence(
        status="pending", stage=stage, error_code=None,
        expected_item_count=len(source), actual_item_count=len(response) if response is not None else None,
        checked_item_count=0, failed_item_count=0,
        source_char_count=sum(len(item.text) for item in source),
        encoded_char_count=sum(len(item.text) for item in encoded.items) if encoded is not None else None,
        response_char_count=sum(len(item.text) for item in response) if response is not None else None,
        restored_char_count=sum(len(item.text) for item in restored) if restored is not None else None,
        source_sha256=items_sha256(source), encoded_sha256=items_sha256(encoded.items) if encoded is not None else None,
        response_sha256=items_sha256(response) if response is not None else None,
        restored_sha256=items_sha256(restored) if restored is not None else None,
        expected_token_counts=_token_counts(encoded) if encoded is not None else (),
        actual_token_counts=_token_counts(encode(restored)) if restored is not None else None,
    )


class TranslationIntegrityValidator:
    """无 I/O、无共享状态；所有外部文本都须经此整批边界。"""

    def prepare(self, source_items: tuple[TranslationTextItem, ...], *, max_chars: int) -> EncodedTokenBatch:
        """生成真实批次 ledger；单项和既存批次超限均在 Provider 调用前失败。"""
        if not _valid_items(source_items, unique=True):
            raise TranslationIntegrityError("translation_integrity_invalid_input", _evidence((), stage="input"))
        batch = encode(source_items)
        evidence = _evidence(source_items, batch, stage="budget")
        if sum(len(item.text) for item in batch.items) > max_chars:
            raise TranslationIntegrityError("translation_request_budget_exceeded", evidence)
        return batch

    def call_failure_evidence(
        self, source_items: tuple[TranslationTextItem, ...], encoded_batch: EncodedTokenBatch,
        *, error_code: str,
    ) -> TranslationIntegrityEvidence:
        """真实调用未产生可验证响应时，保留未到达恢复阶段的安全摘要。"""
        return replace(_evidence(source_items, encoded_batch, stage="provider"), status="failed", error_code=error_code)

    def validate(
        self, source_items: tuple[TranslationTextItem, ...], encoded_batch: EncodedTokenBatch,
        result: TranslationProviderResult,
    ) -> ValidatedTranslationBatch:
        if not _valid_items(source_items, unique=True):
            raise TranslationIntegrityError("translation_integrity_invalid_input", _evidence((), stage="input"))
        expected = encode(source_items)
        evidence = _evidence(source_items, expected, stage="metadata")
        if not isinstance(encoded_batch, EncodedTokenBatch) or encoded_batch != expected:
            raise TranslationIntegrityError("translation_integrity_metadata_mismatch", evidence)
        evidence = replace(evidence, stage="response_shape")
        if not isinstance(result, TranslationProviderResult) or not _valid_items(result.items, unique=False):
            raise TranslationIntegrityError("translation_integrity_invalid_response", evidence)
        response = result.items
        evidence = _evidence(source_items, expected, response, stage="item_ids")
        self._validate_ids(expected.item_ids, response, evidence)
        evidence = replace(evidence, stage="placeholders")
        try:
            restored = decode(response, expected)
        except ProtectedTokenError as exc:
            code = _CODEC_ERROR_CODES[exc.code]
            raise TranslationIntegrityError(code, replace(evidence, failed_item_count=1)) from None
        return self._validate_technical(source_items, expected, restored, response=response)

    @staticmethod
    def _validate_ids(expected_ids: tuple[str, ...], response: tuple[TranslationTextItem, ...], evidence: TranslationIntegrityEvidence) -> None:
        actual = tuple(item.id for item in response)
        counts = Counter(actual)
        expected = set(expected_ids)
        # 首错优先级是接口合同；不记录 Provider 返回的未经信任 ID。
        code = (
            "translation_integrity_item_duplicate" if any(count > 1 for count in counts.values()) else
            "translation_integrity_item_missing" if expected - counts.keys() else
            "translation_integrity_item_extra" if counts.keys() - expected else
            "translation_integrity_item_order" if actual != expected_ids else None
        )
        if code is not None:
            raise TranslationIntegrityError(code, evidence)

    @staticmethod
    def _validate_technical(
        source: tuple[TranslationTextItem, ...], encoded: EncodedTokenBatch,
        restored: tuple[TranslationTextItem, ...], *, response: tuple[TranslationTextItem, ...] | None,
    ) -> ValidatedTranslationBatch:
        actual = encode(restored)
        expected_inventory = _inventory(encoded)
        actual_inventory = _inventory(actual)
        failed = sum(expected_inventory[item.id] != actual_inventory[item.id] for item in source)
        evidence = _evidence(source, encoded, response, restored, stage="technical_inventory")
        evidence = replace(evidence, checked_item_count=len(source), failed_item_count=failed)
        if failed:
            raise TranslationIntegrityError("translation_integrity_technical_mismatch", evidence)
        return ValidatedTranslationBatch(restored, replace(evidence, status="passed", stage="completed"))

    def validate_persisted(
        self, source_items: tuple[TranslationTextItem, ...], restored_items: tuple[TranslationTextItem, ...],
        evidence: object, *, binding: TranslationIntegrityBinding,
    ) -> ValidatedTranslationBatch:
        """fan-in 使用本地来源重核恢复文本与证据；缺证据的历史中间结果不能自证通过。"""
        if not _valid_items(source_items, unique=True):
            raise TranslationIntegrityError("translation_integrity_invalid_input", _evidence((), stage="input"))
        encoded = encode(source_items)
        base = _evidence(source_items, encoded, stage="persisted_evidence")
        if evidence is None:
            raise TranslationIntegrityError("translation_integrity_evidence_missing", base)
        if not _valid_items(restored_items, unique=False):
            raise TranslationIntegrityError("translation_integrity_invalid_response", base)
        self._validate_ids(encoded.item_ids, restored_items, base)
        validated = self._validate_technical(source_items, encoded, restored_items, response=None)
        expected = validated.evidence.bind(binding).to_dict()
        if not isinstance(evidence, dict) or set(evidence) != set(expected):
            raise TranslationIntegrityError("translation_integrity_evidence_mismatch", base)
        def same_evidence_field(actual: object, expected_value: object) -> bool:
            # JSON 中 bool/float 不能借 Python 的数值相等冒充计数或代次整数。
            if type(actual) is not type(expected_value):
                return False
            if isinstance(expected_value, dict):
                return actual.keys() == expected_value.keys() and all(
                    same_evidence_field(actual[key], value) for key, value in expected_value.items()
                )
            return actual == expected_value

        response_fields = {"actual_item_count", "response_char_count", "response_sha256"}
        valid = all(same_evidence_field(evidence[key], value) for key, value in expected.items() if key not in response_fields)
        valid = valid and type(evidence["actual_item_count"]) is int and evidence["actual_item_count"] == len(source_items)
        valid = valid and type(evidence["response_char_count"]) is int and evidence["response_char_count"] >= 0
        valid = valid and isinstance(evidence["response_sha256"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["response_sha256"]) is not None
        if not valid:
            raise TranslationIntegrityError("translation_integrity_evidence_mismatch", base)
        checked = replace(
            validated.evidence, binding=binding, actual_item_count=evidence["actual_item_count"],
            response_char_count=evidence["response_char_count"], response_sha256=evidence["response_sha256"],
        )
        return ValidatedTranslationBatch(restored_items, checked)
