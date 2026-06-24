// File: frontend/src/utils/documentJobConfig.ts
// Purpose: Resolve document job config-summary defaults for the selected translation mode.
import type {
  DocumentJobConfigSummaryResponse,
  DocumentJobTranslationResourceDefaults,
  TranslationMode,
} from "@/api/types";

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
