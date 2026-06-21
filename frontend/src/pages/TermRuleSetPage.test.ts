// frontend/src/pages/TermRuleSetPage.test.ts: Guard the draft-rule dialog scroll contract.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(fileURLToPath(new URL("./TermRuleSetPage.vue", import.meta.url)), "utf8");
const formSource = readFileSync(fileURLToPath(new URL("../composables/useTermRuleForm.ts", import.meta.url)), "utf8");
const dialogSource = readFileSync(fileURLToPath(new URL("../components/TermRuleDraftRuleDialog.vue", import.meta.url)), "utf8");
const panelSource = readFileSync(fileURLToPath(new URL("../components/TermRuleDraftRulePanel.vue", import.meta.url)), "utf8");
const governanceSource = readFileSync(fileURLToPath(new URL("../components/TermRuleGovernanceReports.vue", import.meta.url)), "utf8");
const governanceDisplaySource = readFileSync(fileURLToPath(new URL("../composables/useTermRuleGovernanceDisplay.ts", import.meta.url)), "utf8");
const proposalsSource = readFileSync(fileURLToPath(new URL("../components/TermRuleApprovedProposalsPanel.vue", import.meta.url)), "utf8");
const publishSource = readFileSync(fileURLToPath(new URL("../components/TermRulePublishDialog.vue", import.meta.url)), "utf8");
const versionsSource = readFileSync(fileURLToPath(new URL("../components/TermRulePublishedVersionsPanel.vue", import.meta.url)), "utf8");
const yamlSource = readFileSync(fileURLToPath(new URL("../components/TermRuleYamlFallbackPanel.vue", import.meta.url)), "utf8");

describe("TermRuleSetPage draft-rule dialog", () => {
  it("keeps the long dialog mounted on body with an owned scroll container", () => {
    expect(source).toMatch(/<TermRuleDraftRuleDialog[\s\S]*v-model:visible="ruleDialog\.visible"[\s\S]*@save="saveRule"/);
    expect(dialogSource).toMatch(/<el-dialog[\s\S]*class="rule-dialog"[\s\S]*append-to="body"[\s\S]*:append-to-body="true"/);
    expect(dialogSource).toContain('<div class="rule-dialog-scroll">');
    expect(dialogSource).toMatch(/<template #footer>[\s\S]*保存[\s\S]*<\/template>/);
  });

  it("keeps header and footer reachable while only the dialog body scrolls", () => {
    expect(dialogSource).toMatch(/:global\(\.rule-dialog\) \{[\s\S]*display: flex;[\s\S]*flex-direction: column;[\s\S]*max-height: calc\(100dvh - 48px\);[\s\S]*\}/);
    expect(dialogSource).toMatch(/:global\(\.rule-dialog \.el-dialog__header\),[\s\S]*:global\(\.rule-dialog \.el-dialog__footer\) \{[\s\S]*flex: 0 0 auto;[\s\S]*\}/);
    expect(dialogSource).toMatch(/:global\(\.rule-dialog \.el-dialog__body\) \{[\s\S]*min-height: 0;[\s\S]*overflow: hidden;[\s\S]*\}/);
    expect(dialogSource).toMatch(/\.rule-dialog-scroll \{[\s\S]*max-height: min\(640px, calc\(100dvh - 220px\)\);[\s\S]*overflow-y: auto;[\s\S]*overscroll-behavior: contain;[\s\S]*\}/);
  });
});

describe("TermRuleSetPage advanced draft-rule creation", () => {
  it("exposes separate basic and advanced creation actions", () => {
    expect(source).toMatch(/<TermRuleDraftRulePanel[\s\S]*@create="openCreateRuleDialog"/);
    expect(panelSource).toMatch(/@click="emit\('create'\)"[\s\S]*新增规则/);
    expect(panelSource).toMatch(/@click="emit\('create', 'advanced'\)"[\s\S]*新增高级规则/);
  });

  it("opens advanced creation with preset format segments and custom render fields", () => {
    expect(formSource).toContain('export type RuleDialogVariant = "basic" | "advanced";');
    expect(formSource).toMatch(/variant === "advanced"[\s\S]*render_type: "subscript"[\s\S]*render_type: "superscript"/);
    expect(source).toContain('return ruleDialog.variant === "advanced" ? "新增高级草稿规则" : "新增草稿规则";');
    expect(dialogSource).toContain('v-model="form.custom_markdown"');
    expect(dialogSource).toContain('v-model="form.custom_html"');
  });
});

describe("TermRuleSetPage draft snapshot guard", () => {
  it("sends the current draft snapshot hash with every draft mutation path", () => {
    expect(source).toContain("function currentDraftSnapshotHash()");
    expect(source).toContain("buildTermRuleMutationPayload(ruleForm, currentDraftSnapshotHash())");
    expect(source).toMatch(/updateDraftRule\(selectedSetId\.value, rule\.id, \{[\s\S]*expected_snapshot_hash: currentDraftSnapshotHash\(\)/);
    expect(source).toContain("deleteDraftRule(selectedSetId.value, rule.id, currentDraftSnapshotHash())");
    expect(source).toMatch(/termRuleSetsApi\.updateDraft\(selectedSetId\.value, \{[\s\S]*expected_snapshot_hash: currentDraftSnapshotHash\(\)/);
  });

  it("refreshes the draft when the backend reports a snapshot conflict", () => {
    expect(source).toContain('normalized.code === "draft_snapshot_conflict"');
    expect(source).toMatch(/ElMessage\.warning\([\s\S]*已刷新最新内容[\s\S]*await refreshAfterDraftMutation\(\)/);
  });
});

describe("TermRuleSetPage governance reports", () => {
  it("keeps diff and preflight display logic outside the page component", () => {
    expect(source).toMatch(/<TermRuleGovernanceReports[\s\S]*:diff-report="diffReport"[\s\S]*@refresh="loadGovernanceReports"/);
    expect(governanceSource).toContain("草稿差异");
    expect(governanceSource).toContain("发布前校验");
    expect(governanceSource).toContain("草稿将移除");
    expect(governanceSource).toContain("pagedDiffItems");
    expect(governanceSource).toContain("diffFilters.pageSize");
    expect(governanceSource).toContain("termRuleDiffCounters");
    expect(governanceSource).toContain("termRulePreflightFindings");
    expect(governanceDisplaySource).toContain("termRulePreflightStatusLabel");
    expect(governanceDisplaySource).toContain("termRuleChangeTypeTagType");
  });
});

describe("TermRuleSetPage configuration management panels", () => {
  it("keeps published-version and YAML fallback display outside the page component", () => {
    expect(source).toMatch(/<TermRulePublishedVersionsPanel[\s\S]*@set-default="setDefault"[\s\S]*@rollback="rollback"/);
    expect(source).toMatch(/<TermRuleYamlFallbackPanel[\s\S]*v-model:yaml-text="yamlText"[\s\S]*@save="saveYamlDraft"/);
    expect(versionsSource).toContain("已发布版本");
    expect(versionsSource).toContain("emit('set-default', row.version)");
    expect(versionsSource).toContain("emit('rollback', row.version)");
    expect(yamlSource).toContain("YAML 高级编辑兜底");
    expect(yamlSource).toContain('defineModel<string>("yamlText"');
  });
});

describe("TermRuleSetPage publish and proposal review panels", () => {
  it("keeps proposal review display and publish dialog markup outside the page component", () => {
    expect(source).toMatch(/<TermRuleApprovedProposalsPanel[\s\S]*@select="openApprovedProposal"/);
    expect(source).toMatch(/<TermRulePublishDialog[\s\S]*v-model:visible="publishDialog\.visible"[\s\S]*@publish="publishDraft"/);
    expect(proposalsSource).toContain("已通过待核对建议");
    expect(proposalsSource).toContain("TermProposalTable");
    expect(publishSource).toContain("发布术语规则集草稿");
    expect(publishSource).toContain("termRulePreflightFindings");
    expect(publishSource).toContain("defineExpose({ validate })");
  });
});
