// 守护 Translation Profile Prompt 工作区的交互与 API 请求合同。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api/client";
import { translationProfilesApi } from "@/api/translationProfiles";
import type { TranslationProfileDraftResponse } from "@/api/types";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
}));

const source = readFileSync(fileURLToPath(new URL("./TranslationProfilesPage.vue", import.meta.url)), "utf8");
const templateDetailSource = readFileSync(fileURLToPath(new URL("./TemplateDetailPage.vue", import.meta.url)), "utf8");

const draftResponse: TranslationProfileDraftResponse = {
  translation_profile_id: "electronics-zh2en",
  language_pair: "zh2en",
  base_version: "1",
  target_language: "en",
  domain: "electronics",
  prompt_version: "translation-zh2en-v1",
  prompt_schemes: [
    {
      id: "translation-zh2en-v1",
      name: "内置中译英 Prompt",
      markdown: "# Role",
      content_hash: "sha256:prompt",
      built_in: true,
      is_active: true,
      deletable: false,
      delete_disabled_reason: "内置 Prompt 不能删除。",
    },
  ],
  model: null,
  max_pages_per_batch: 20,
  max_chars_per_batch: 60000,
  snapshot_hash: "sha256:draft",
};

describe("TranslationProfilesPage Prompt workspace", () => {
  it("provides named Prompt editing, draft/online status and protected admin actions", () => {
    expect(source).toContain("Prompt 工作区");
    expect(source).toContain("草稿当前方案");
    expect(source).toContain("线上当前方案");
    expect(source).toContain('type="textarea"');
    expect(source).toContain("新建 Prompt");
    expect(source).toContain("保存 Prompt");
    expect(source).toContain("设为当前方案");
    expect(source).toContain("删除 Prompt");
    expect(source).toContain("selectedPrompt.value?.delete_disabled_reason");
    expect(source).toContain(':disabled="!isAdmin || promptBusy"');
    expect(source).toContain("expected_snapshot_hash: draft.value.snapshot_hash");
    expect(source).toMatch(/\.translation-profiles-page \{[\s\S]*grid-template-columns: minmax\(0, 1fr\);/);
    expect(source).toMatch(/@media \(max-width: 1024px\) \{[\s\S]*\.prompt-workspace,[\s\S]*grid-template-columns: 1fr;/);
    expect(source).not.toContain('v-model="draftForm.prompt_version"');
  });

  it("guards unsaved Prompt content across selection, refresh, route and browser leave", () => {
    expect(source).toContain("const isPromptDirty = computed");
    expect(source).toContain("confirmDiscardPromptChanges");
    expect(source).toContain("切换 Prompt 会丢弃当前未保存修改。");
    expect(source).toContain("切换翻译配置会丢弃当前未保存的 Prompt 修改。");
    expect(source).toContain("onBeforeRouteLeave");
    expect(source).toContain('window.addEventListener("beforeunload", handleBeforeUnload)');
    expect(source).toContain('window.removeEventListener("beforeunload", handleBeforeUnload)');
  });

  it("uses the shared five-mode definition in the template validation dialog", () => {
    expect(templateDetailSource).toMatch(
      /v-for="option in documentJobModeOptions"[\s\S]*:value="option\.mode"[\s\S]*option\.shortLabel/,
    );
    expect(templateDetailSource).toContain("validation-mode-options");
  });
});

describe("translationProfilesApi Prompt mutations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(draftResponse);
  });

  it("sends the current draft snapshot hash through every Prompt mutation", async () => {
    const expectedSnapshot = { expected_snapshot_hash: "sha256:draft" };

    await translationProfilesApi.createPrompt("electronics-zh2en", {
      name: "精简方案",
      source_prompt_id: "translation-zh2en-v1",
      ...expectedSnapshot,
    });
    await translationProfilesApi.updatePrompt("electronics-zh2en", "prompt-1", {
      name: "精简方案",
      markdown: "# Updated",
      ...expectedSnapshot,
    });
    await translationProfilesApi.activatePrompt("electronics-zh2en", "prompt-1", expectedSnapshot);
    await translationProfilesApi.deletePrompt("electronics-zh2en", "prompt-1", expectedSnapshot);

    expect(apiRequest).toHaveBeenNthCalledWith(1, {
      url: "/api/v1/translation-profiles/electronics-zh2en/draft/prompts",
      method: "POST",
      data: {
        name: "精简方案",
        source_prompt_id: "translation-zh2en-v1",
        expected_snapshot_hash: "sha256:draft",
      },
    });
    expect(apiRequest).toHaveBeenNthCalledWith(2, {
      url: "/api/v1/translation-profiles/electronics-zh2en/draft/prompts/prompt-1",
      method: "PUT",
      data: {
        name: "精简方案",
        markdown: "# Updated",
        expected_snapshot_hash: "sha256:draft",
      },
    });
    expect(apiRequest).toHaveBeenNthCalledWith(3, {
      url: "/api/v1/translation-profiles/electronics-zh2en/draft/prompts/prompt-1/activate",
      method: "POST",
      data: expectedSnapshot,
    });
    expect(apiRequest).toHaveBeenNthCalledWith(4, {
      url: "/api/v1/translation-profiles/electronics-zh2en/draft/prompts/prompt-1",
      method: "DELETE",
      data: expectedSnapshot,
    });
  });
});
