// frontend/src/utils/documentJobConfig.test.ts: Guard language-pair defaults in document job config summary.
import { describe, expect, it } from "vitest";

import type { DocumentJobConfigSummaryResponse } from "@/api/types";
import { isTranslationModeAvailable, translationResourceDefaultsForMode } from "@/utils/documentJobConfig";

function buildSummary(): DocumentJobConfigSummaryResponse {
  return {
    role: "operator",
    resource_mode: "versioned",
    defaults: {
      template: null,
      term_rule_set: null,
      translation_term_set: {
        resource_id: "translation-terms-en2zh",
        version: "v1",
        label: "translation-terms-en2zh@v1",
        status: "published",
        is_default: true,
        summary: { language_pair: "en2zh" },
      },
      translation_profile: {
        resource_id: "electronics-en2zh",
        version: "1",
        label: "electronics-en2zh@1",
        status: "published",
        is_default: true,
        summary: { language_pair: "en2zh" },
      },
    },
    translation_defaults: {
      en2zh: {
        translation_term_set: {
          resource_id: "translation-terms-en2zh",
          version: "v1",
          label: "translation-terms-en2zh@v1",
          status: "published",
          is_default: true,
          summary: { language_pair: "en2zh" },
        },
        translation_profile: {
          resource_id: "electronics-en2zh",
          version: "1",
          label: "electronics-en2zh@1",
          status: "published",
          is_default: true,
          summary: { language_pair: "en2zh" },
        },
      },
      ru2zh: {
        translation_term_set: {
          resource_id: "translation-terms-ru2zh",
          version: "v1",
          label: "translation-terms-ru2zh@v1",
          status: "published",
          is_default: true,
          summary: { language_pair: "ru2zh" },
        },
        translation_profile: {
          resource_id: "electronics-ru2zh",
          version: "seed",
          label: "electronics-ru2zh@seed",
          status: "published",
          is_default: true,
          summary: { language_pair: "ru2zh" },
        },
      },
      zh2en: {
        translation_term_set: {
          resource_id: "translation-terms-zh2en",
          version: "v1",
          label: "translation-terms-zh2en@v1",
          status: "published",
          is_default: true,
          summary: { language_pair: "zh2en" },
        },
        translation_profile: {
          resource_id: "electronics-zh2en",
          version: "seed",
          label: "electronics-zh2en@seed",
          status: "published",
          is_default: true,
          summary: { language_pair: "zh2en" },
        },
      },
      zh2ru: {
        translation_term_set: {
          resource_id: "translation-terms-zh2ru",
          version: "v1",
          label: "translation-terms-zh2ru@v1",
          status: "published",
          is_default: true,
          summary: { language_pair: "zh2ru" },
        },
        translation_profile: {
          resource_id: "electronics-zh2ru",
          version: "seed",
          label: "electronics-zh2ru@seed",
          status: "published",
          is_default: true,
          summary: { language_pair: "zh2ru" },
        },
      },
    },
    options: {
      templates: [],
      term_rule_sets: [],
      translation_term_sets: [],
      translation_profiles: [],
    },
    readiness: {
      en2zh_available: true,
      ru2zh_available: true,
      translation_modes: { en2zh: true, ru2zh: true, zh2en: true, zh2ru: true },
      p0_document_jobs_required: false,
      p0_document_jobs_ready: true,
      document_jobs_worker_backend: "disabled",
      document_jobs_automatic_execution_enabled: false,
      blockers: [],
      warnings: [],
    },
  };
}

describe("translationResourceDefaultsForMode", () => {
  it("uses ru2zh defaults instead of legacy en2zh defaults", () => {
    const defaults = translationResourceDefaultsForMode(buildSummary(), "ru2zh");

    expect(defaults?.translation_term_set?.label).toBe("translation-terms-ru2zh@v1");
    expect(defaults?.translation_profile?.label).toBe("electronics-ru2zh@seed");
  });

  it("falls back to legacy defaults for en2zh when a backend does not send translation_defaults", () => {
    const summary = buildSummary();
    summary.translation_defaults = {};

    const defaults = translationResourceDefaultsForMode(summary, "en2zh");

    expect(defaults?.translation_term_set?.label).toBe("translation-terms-en2zh@v1");
    expect(defaults?.translation_profile?.label).toBe("electronics-en2zh@1");
  });

  it("resolves the two Chinese-source language-pair defaults independently", () => {
    expect(
      translationResourceDefaultsForMode(buildSummary(), "zh2en")?.translation_profile?.label,
    ).toBe("electronics-zh2en@seed");
    expect(
      translationResourceDefaultsForMode(buildSummary(), "zh2ru")?.translation_term_set?.label,
    ).toBe("translation-terms-zh2ru@v1");
  });
});

describe("isTranslationModeAvailable", () => {
  it("does not treat a missing Chinese-source readiness entry as ru2zh readiness", () => {
    const summary = buildSummary();
    summary.readiness.translation_modes = { en2zh: true, ru2zh: true };

    expect(isTranslationModeAvailable(summary, "zh2en")).toBe(false);
    expect(isTranslationModeAvailable(summary, "zh2ru")).toBe(false);
  });

  it("keeps the legacy dedicated readiness fallback bounded to en2zh and ru2zh", () => {
    const summary = buildSummary();
    summary.readiness.translation_modes = {};

    expect(isTranslationModeAvailable(summary, "en2zh")).toBe(true);
    expect(isTranslationModeAvailable(summary, "ru2zh")).toBe(true);
    expect(isTranslationModeAvailable(summary, "zh2en")).toBe(false);
  });
});
