from __future__ import annotations

# File: app/domains/translation/modes.py
# Purpose: Centralize supported document translation modes and language-pair metadata.

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


TranslationMode = Literal["direct", "en2zh", "ru2zh", "zh2en", "zh2ru"]
TranslationLanguagePair = Literal["en2zh", "ru2zh", "zh2en", "zh2ru"]
DocumentJobMode = Literal[
    "direct_pdf_to_word",
    "en2zh_pdf_to_word",
    "ru2zh_pdf_to_word",
    "zh2en_pdf_to_word",
    "zh2ru_pdf_to_word",
]
DocumentLanguage = Literal["auto", "zh", "en", "ru"]


@dataclass(frozen=True, slots=True)
class TranslationModeSpec:
    translation_mode: TranslationMode
    document_job_mode: DocumentJobMode
    language_pair: TranslationLanguagePair | None
    source_language: str | None
    target_language: str | None
    default_document_language: DocumentLanguage
    target_document_language: str | None
    mineru_language: str | None
    default_profile_id: str | None
    default_prompt_file: str | None

    @property
    def is_translation(self) -> bool:
        return self.language_pair is not None

    @property
    def default_term_set_id(self) -> str | None:
        if self.language_pair is None:
            return None
        return derive_translation_term_set_id(self.language_pair)


TRANSLATION_MODE_SPECS: dict[TranslationMode, TranslationModeSpec] = {
    "direct": TranslationModeSpec(
        translation_mode="direct",
        document_job_mode="direct_pdf_to_word",
        language_pair=None,
        source_language=None,
        target_language=None,
        default_document_language="auto",
        target_document_language=None,
        mineru_language=None,
        default_profile_id=None,
        default_prompt_file=None,
    ),
    "en2zh": TranslationModeSpec(
        translation_mode="en2zh",
        document_job_mode="en2zh_pdf_to_word",
        language_pair="en2zh",
        source_language="en",
        target_language="zh",
        default_document_language="en",
        target_document_language="zh",
        mineru_language="en",
        default_profile_id="electronics-en2zh",
        default_prompt_file="translation_en2zh.md",
    ),
    "ru2zh": TranslationModeSpec(
        translation_mode="ru2zh",
        document_job_mode="ru2zh_pdf_to_word",
        language_pair="ru2zh",
        source_language="ru",
        target_language="zh",
        default_document_language="ru",
        target_document_language="zh",
        mineru_language="ru",
        default_profile_id="electronics-ru2zh",
        default_prompt_file="translation_ru2zh.md",
    ),
    "zh2en": TranslationModeSpec(
        translation_mode="zh2en",
        document_job_mode="zh2en_pdf_to_word",
        language_pair="zh2en",
        source_language="zh",
        target_language="en",
        default_document_language="zh",
        target_document_language="en",
        mineru_language="zh",
        default_profile_id="electronics-zh2en",
        default_prompt_file="translation_zh2en.md",
    ),
    "zh2ru": TranslationModeSpec(
        translation_mode="zh2ru",
        document_job_mode="zh2ru_pdf_to_word",
        language_pair="zh2ru",
        source_language="zh",
        target_language="ru",
        default_document_language="zh",
        target_document_language="ru",
        mineru_language="zh",
        default_profile_id="electronics-zh2ru",
        default_prompt_file="translation_zh2ru.md",
    ),
}

TRANSLATION_MODES: tuple[TranslationMode, ...] = tuple(TRANSLATION_MODE_SPECS)
TRANSLATION_LANGUAGE_PAIRS: tuple[TranslationLanguagePair, ...] = tuple(
    spec.language_pair
    for spec in TRANSLATION_MODE_SPECS.values()
    if spec.language_pair is not None
)
DOCUMENT_JOB_MODES: tuple[DocumentJobMode, ...] = tuple(
    spec.document_job_mode for spec in TRANSLATION_MODE_SPECS.values()
)
TRANSLATION_PROFILE_IDS: tuple[str, ...] = tuple(
    spec.default_profile_id
    for spec in TRANSLATION_MODE_SPECS.values()
    if spec.default_profile_id is not None
)


def derive_translation_term_set_id(language_pair: str) -> str:
    return f"translation-terms-{language_pair.strip().lower()}"


def normalize_translation_mode(value: str | None) -> TranslationMode:
    normalized = str(value or "direct").strip().lower()
    aliases = {
        "none": "direct",
        "zh2zh": "direct",
        "zh_to_zh": "direct",
        "llm_en_to_zh": "en2zh",
        "en_to_zh": "en2zh",
        "llm_ru_to_zh": "ru2zh",
        "ru_to_zh": "ru2zh",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in TRANSLATION_MODE_SPECS:
        raise ValueError(f"Unsupported translation_mode: {value}")
    return normalized  # type: ignore[return-value]


def translation_mode_for_document_job_mode(mode: str) -> TranslationMode:
    normalized = str(mode or "").strip()
    for spec in TRANSLATION_MODE_SPECS.values():
        if spec.document_job_mode == normalized:
            return spec.translation_mode
    raise ValueError(f"Unsupported document job mode: {mode}")


def document_job_mode_for_translation_mode(mode: str | None) -> DocumentJobMode:
    return spec_for_translation_mode(mode).document_job_mode


def spec_for_translation_mode(mode: str | None) -> TranslationModeSpec:
    return TRANSLATION_MODE_SPECS[normalize_translation_mode(mode)]


def spec_for_document_job_mode(mode: str) -> TranslationModeSpec:
    return TRANSLATION_MODE_SPECS[translation_mode_for_document_job_mode(mode)]


def spec_for_language_pair(language_pair: str) -> TranslationModeSpec:
    normalized = language_pair.strip().lower()
    for spec in TRANSLATION_MODE_SPECS.values():
        if spec.language_pair == normalized:
            return spec
    raise ValueError(f"Unsupported translation language_pair: {language_pair}")


def is_translation_mode(mode: str | None) -> bool:
    return spec_for_translation_mode(mode).is_translation


def is_translation_document_job_mode(mode: str) -> bool:
    return spec_for_document_job_mode(mode).is_translation


def language_pair_for_translation_mode(mode: str | None) -> TranslationLanguagePair | None:
    return spec_for_translation_mode(mode).language_pair


def translation_prompt_path(root_dir: Path, language_pair: str) -> Path:
    prompt_file = spec_for_language_pair(language_pair).default_prompt_file
    if prompt_file is None:
        raise ValueError(f"Translation prompt is not defined for language_pair={language_pair}")
    return root_dir / "resources" / "prompts" / prompt_file
