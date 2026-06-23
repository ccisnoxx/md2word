// File: frontend/src/utils/releaseGateRoutes.ts
// Purpose: Map release gate finding codes to the most relevant workbench route.

export function releaseGateRouteForCode(code: string): string {
  const normalized = code.toLowerCase();
  if (normalized.startsWith("document_jobs") || normalized === "p0_document_jobs_not_ready") {
    return "/system-status/ops-dashboard";
  }
  if (normalized.includes("ai_provider") || normalized.includes("openai")) {
    return "/settings/ai-provider";
  }
  if (normalized.includes("translation_term") || normalized.includes("translation-term")) {
    return "/settings/translation-term-sets";
  }
  if (normalized.includes("translation_profile") || normalized.includes("translation-profile")) {
    return "/settings/translation-profiles";
  }
  if (normalized.includes("layout")) {
    return "/settings/word-page-styles";
  }
  if (normalized.includes("template") || normalized.includes("subscript")) {
    return "/settings/templates";
  }
  if (normalized.includes("term_rule") || normalized.includes("term-rule") || normalized.includes("term")) {
    return "/settings/term-rule-sets";
  }
  if (normalized.includes("translation")) {
    return "/settings/translation-profiles";
  }
  return "/system-status";
}

export function releaseGateRouteLabel(route: string): string {
  const labels: Record<string, string> = {
    "/system-status/ops-dashboard": "运维看板",
    "/system-status": "系统状态",
    "/settings/templates": "Word 模板文档",
    "/settings/word-page-styles": "Word 页面样式配置",
    "/settings/term-rule-sets": "术语规则",
    "/settings/translation-profiles": "翻译配置",
    "/settings/translation-term-sets": "翻译术语",
    "/settings/ai-provider": "AI 配置",
  };
  return labels[route] || "配置详情";
}
