// 文件：frontend/src/utils/documentJobConfig.test.ts；用途：验证任务模式的配置默认值与展示隔离。
import { describe, expect, it } from "vitest";

import type { DocumentJobConfigSummaryResponse } from "@/api/types";
import {
  documentJobConfigWarningsForMode,
  documentJobRequestSnapshotForDisplay,
  isTranslationModeAvailable,
  translationResourceDefaultsForMode,
} from "@/utils/documentJobConfig";

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

describe("CON-101：当前模式的配置 warnings", () => {
  it("direct 隐藏全部已知翻译资源 warning，保留普通错误、P0 和未知项", () => {
    const summary = buildSummary();
    const retainedWarnings = [
      "template_default_unavailable:invalid_template",
      "term_rule_set_default_missing",
      "ai_provider_config_invalid",
      "mineru_api_token_missing",
      "p0_document_jobs_not_ready",
      "translation_profile_default_missing_extra:ru2zh",
      "future_translation_warning:zh2ru",
    ];
    summary.readiness.warnings = [
      "translation_term_set_default_missing",
      "translation_profile_default_missing",
      "translation_term_repository_unavailable",
      "translation_profile_service_unavailable",
      "translation_term_set_default_unavailable:en2zh",
      "translation_profile_default_unavailable:zh2en:invalid_profile",
      "translation_profile_options_unavailable:profile_directory_missing",
      "translation_profile_versions_unavailable:electronics-ru2zh:version_missing",
      ...["en2zh", "ru2zh", "zh2en", "zh2ru"].flatMap((pair) => [
        `translation_term_set_default_missing:${pair}`,
        `translation_profile_default_missing:${pair}`,
      ]),
      ...retainedWarnings,
    ];
    const original = [...summary.readiness.warnings];

    expect(documentJobConfigWarningsForMode(summary, "direct_pdf_to_word")).toEqual(retainedWarnings);
    expect(summary.readiness.warnings).toEqual(original);
    expect(documentJobConfigWarningsForMode(null, "direct_pdf_to_word")).toEqual([]);
  });

  it("四个翻译方向保留全部资源 warnings", () => {
    const summary = buildSummary();
    summary.readiness.warnings = ["translation_profile_default_missing:ru2zh", "future_translation_warning"];

    for (const mode of ["en2zh_pdf_to_word", "ru2zh_pdf_to_word", "zh2en_pdf_to_word", "zh2ru_pdf_to_word"] as const) {
      expect(documentJobConfigWarningsForMode(summary, mode)).toEqual(summary.readiness.warnings);
    }
  });
});

describe("CON-101：请求快照只读展示", () => {
  const snapshot = {
    mode: "direct_pdf_to_word",
    translation_mode: "direct",
    document_language: "auto",
    source_file: { original_filename: "legacy.pdf" },
    source_job_id: "docjob_source",
    template_version_id: "template@1",
    term_version_id: "legacy-en2zh@1",
    debug_full_text_enabled: true,
    translation_profile: { translation_profile_id: "legacy-profile", model: "legacy-model" },
    term_assets: {
      use_latest_term_assets: false,
      term_rule_set_id: "symbols",
      term_rule_set_version: "2",
      translation_term_set_id: "legacy-terms",
      translation_term_version: "3",
    },
    resources: {
      template: { resource_id: "template", version: "1" },
      term_rule_set: { resource_id: "symbols", version: "2" },
      mineru: { model_version: "pipeline" },
      artifact_ids: { document_ir: "file_ir" },
      translation_term_set: { set_id: "legacy-terms", snapshot_hash: "legacy-term-hash" },
      translation_profile: { resource_id: "legacy-profile", model: "legacy-model" },
      translation_prompt_id: "legacy-prompt",
      translation_prompt_content_hash: "legacy-prompt-hash",
    },
  };

  it("direct 移除已知翻译和 AI 元数据，保留普通资源与来源且不修改输入", () => {
    const original = structuredClone(snapshot);
    const input = Object.freeze({
      ...snapshot,
      term_assets: Object.freeze({ ...snapshot.term_assets }),
      resources: Object.freeze({ ...snapshot.resources }),
    });
    const preview = documentJobRequestSnapshotForDisplay(input, "direct_pdf_to_word");

    expect(preview).toEqual({
      mode: "direct_pdf_to_word",
      translation_mode: "direct",
      document_language: "auto",
      source_file: { original_filename: "legacy.pdf" },
      source_job_id: "docjob_source",
      template_version_id: "template@1",
      term_assets: { use_latest_term_assets: false, term_rule_set_id: "symbols", term_rule_set_version: "2" },
      resources: {
        template: { resource_id: "template", version: "1" },
        term_rule_set: { resource_id: "symbols", version: "2" },
        mineru: { model_version: "pipeline" },
        artifact_ids: { document_ir: "file_ir" },
      },
    });
    expect(input).toEqual(original);
    expect(preview.term_assets).not.toBe(input.term_assets);
    expect(preview.resources).not.toBe(input.resources);
  });

  it("direct 克隆隐藏源翻译术语，保留来源和原始快照", () => {
    const clone = Object.freeze({
      source_job_id: "docjob_legacy",
      config_strategy: "keep_source_snapshot",
      source_template_version_id: "template@1",
      source_term_version_id: "en2zh@retired",
    });
    const input = { ...snapshot, clone };
    const preview = documentJobRequestSnapshotForDisplay(input, "direct_pdf_to_word");
    expect(preview.clone).toEqual({
      source_job_id: "docjob_legacy",
      config_strategy: "keep_source_snapshot",
      source_template_version_id: "template@1",
    });
    expect(input.clone.source_term_version_id).toBe("en2zh@retired");
    expect(preview.clone).not.toBe(input.clone);
    for (const mode of ["en2zh_pdf_to_word", "ru2zh_pdf_to_word", "zh2en_pdf_to_word", "zh2ru_pdf_to_word"] as const) {
      expect(documentJobRequestSnapshotForDisplay(input, mode).clone).toEqual(clone);
    }
  });

  it("四个翻译方向保留完整历史快照", () => {
    for (const mode of ["en2zh_pdf_to_word", "ru2zh_pdf_to_word", "zh2en_pdf_to_word", "zh2ru_pdf_to_word"] as const) {
      expect(documentJobRequestSnapshotForDisplay(snapshot, mode)).toEqual(snapshot);
    }
  });

  it("兼容没有版本资源结构的历史记录，不猜测未知配置的含义", () => {
    const legacySnapshot = { source_file: { id: "file_source" }, term_assets: null, resources: null, future_config: { id: "future" } };

    expect(documentJobRequestSnapshotForDisplay(legacySnapshot, "direct_pdf_to_word")).toEqual(legacySnapshot);
    expect(documentJobRequestSnapshotForDisplay({}, "direct_pdf_to_word")).toEqual({});
  });
});
