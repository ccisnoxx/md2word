// File: frontend/src/utils/documentJobConfig.ts
// Purpose: Resolve document job config-summary defaults for the selected translation mode.
import type {
  DocumentJobConfigSummaryResponse,
  DocumentJobTranslationResourceDefaults,
  TranslationMode,
} from "@/api/types";

export function isTranslationModeAvailable(
  summary: DocumentJobConfigSummaryResponse | null | undefined,
  translationMode: TranslationMode,
): boolean {
  if (translationMode === "direct") {
    return true;
  }
  const readiness = summary?.readiness;
  if (!readiness) {
    return false;
  }
  const modeAvailability = readiness.translation_modes?.[translationMode];
  if (typeof modeAvailability === "boolean") {
    return modeAvailability;
  }
  if (translationMode === "en2zh") {
    return readiness.en2zh_available;
  }
  if (translationMode === "ru2zh") {
    return readiness.ru2zh_available;
  }
  return false;
}

export function translationResourceDefaultsForMode(
  summary: DocumentJobConfigSummaryResponse | null | undefined,
  translationMode: TranslationMode,
): DocumentJobTranslationResourceDefaults | null {
  if (!summary || translationMode === "direct") {
    return null;
  }
  const modeDefaults = summary.translation_defaults?.[translationMode];
  if (modeDefaults) {
    return modeDefaults;
  }
  if (translationMode === "en2zh") {
    return {
      translation_term_set: summary.defaults.translation_term_set ?? null,
      translation_profile: summary.defaults.translation_profile ?? null,
    };
  }
  return {
    translation_term_set: null,
    translation_profile: null,
  };
}
