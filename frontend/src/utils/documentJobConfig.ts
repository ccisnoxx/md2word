// 文件：frontend/src/utils/documentJobConfig.ts
// 用途：按任务模式解析配置默认值、就绪提示和只读快照展示。
import type {
  DocumentJobConfigSummaryResponse,
  DocumentJobMode,
  DocumentJobTranslationResourceDefaults,
  TranslationMode,
} from "@/api/types";
import { documentJobModeRequiresTranslationResources } from "@/utils/format";

const translationResourceWarningCodes = new Set([
  "translation_term_repository_unavailable",
  "translation_term_set_default_missing",
  "translation_term_set_default_unavailable",
  "translation_profile_service_unavailable",
  "translation_profile_default_missing",
  "translation_profile_default_unavailable",
  "translation_profile_options_unavailable",
  "translation_profile_versions_unavailable",
]);

export function documentJobConfigWarningsForMode(
  summary: DocumentJobConfigSummaryResponse | null | undefined,
  mode: DocumentJobMode,
): string[] {
  const warnings = summary?.readiness.warnings || [];
  if (documentJobModeRequiresTranslationResources(mode)) {
    return warnings;
  }
  // 仅排除 config-summary 的已知翻译资源项；P0、普通配置错误及新 warning 均保留。
  return warnings.filter((warning) => !translationResourceWarningCodes.has(warning.split(":")[0] || ""));
}

export function documentJobRequestSnapshotForDisplay(
  snapshot: Record<string, unknown>,
  mode: DocumentJobMode,
): Record<string, unknown> {
  if (documentJobModeRequiresTranslationResources(mode)) {
    return snapshot;
  }
  // 仅投影已知任务配置结构；响应、持久快照和审计仍保留原始字段。
  const preview = { ...snapshot };
  delete preview.term_version_id;
  delete preview.translation_profile;
  delete preview.debug_full_text_enabled;
  if (isSnapshotRecord(snapshot.clone)) {
    const clone = { ...snapshot.clone };
    delete clone.source_term_version_id;
    preview.clone = clone;
  }
  if (isSnapshotRecord(snapshot.term_assets)) {
    const termAssets = { ...snapshot.term_assets };
    delete termAssets.translation_term_set_id;
    delete termAssets.translation_term_version;
    preview.term_assets = termAssets;
  }
  if (isSnapshotRecord(snapshot.resources)) {
    const resources = { ...snapshot.resources };
    delete resources.translation_term_set;
    delete resources.translation_profile;
    delete resources.translation_prompt_id;
    delete resources.translation_prompt_content_hash;
    preview.resources = resources;
  }
  return preview;
}

function isSnapshotRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

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
