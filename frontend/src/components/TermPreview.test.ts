// frontend/src/components/TermPreview.test.ts: Guard native subscript/superscript preview semantics.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(fileURLToPath(new URL("./TermPreview.vue", import.meta.url)), "utf8");

describe("TermPreview native inline rendering", () => {
  it("renders subscript and superscript with native HTML elements", () => {
    expect(source).toContain("<sub v-if=\"segment.render_type === 'subscript'\">");
    expect(source).toContain("<sup v-else-if=\"segment.render_type === 'superscript'\">");
  });

  it("keeps preview content in normal inline flow so browser offsets are preserved", () => {
    expect(source).toMatch(/\.term-preview \{[\s\S]*display: inline-block;/);
    expect(source).not.toMatch(/\.term-preview \{[\s\S]*display: (?:inline-)?flex;/);
    expect(source).not.toMatch(/\.term-preview sub,[\s\S]*vertical-align:\s*(?:baseline|middle|top|bottom|text-top|text-bottom|0)/);
    expect(source).not.toMatch(/\.term-preview sup,[\s\S]*vertical-align:\s*(?:baseline|middle|top|bottom|text-top|text-bottom|0)/);
  });
});
