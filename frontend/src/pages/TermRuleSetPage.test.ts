// frontend/src/pages/TermRuleSetPage.test.ts: Guard the draft-rule dialog scroll contract.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(fileURLToPath(new URL("./TermRuleSetPage.vue", import.meta.url)), "utf8");

describe("TermRuleSetPage draft-rule dialog", () => {
  it("keeps the long dialog mounted on body with an owned scroll container", () => {
    expect(source).toMatch(/<el-dialog[\s\S]*class="rule-dialog"[\s\S]*append-to="body"[\s\S]*:append-to-body="true"/);
    expect(source).toContain('<div class="rule-dialog-scroll">');
    expect(source).toMatch(/<template #footer>[\s\S]*保存[\s\S]*<\/template>/);
  });

  it("keeps header and footer reachable while only the dialog body scrolls", () => {
    expect(source).toMatch(/:global\(\.rule-dialog\) \{[\s\S]*display: flex;[\s\S]*flex-direction: column;[\s\S]*max-height: calc\(100dvh - 48px\);[\s\S]*\}/);
    expect(source).toMatch(/:global\(\.rule-dialog \.el-dialog__header\),[\s\S]*:global\(\.rule-dialog \.el-dialog__footer\) \{[\s\S]*flex: 0 0 auto;[\s\S]*\}/);
    expect(source).toMatch(/:global\(\.rule-dialog \.el-dialog__body\) \{[\s\S]*min-height: 0;[\s\S]*overflow: hidden;[\s\S]*\}/);
    expect(source).toMatch(/\.rule-dialog-scroll \{[\s\S]*max-height: min\(640px, calc\(100dvh - 220px\)\);[\s\S]*overflow-y: auto;[\s\S]*overscroll-behavior: contain;[\s\S]*\}/);
  });
});
