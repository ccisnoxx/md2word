import { describe, expect, it } from "vitest";

import type { DocumentJobConfigVersionOption } from "@/api/types";
import { configOptionKey, configVersionId, findConfigOption } from "@/utils/configOptions";

function option(
  resourceId: string,
  version: string,
  label: string,
): DocumentJobConfigVersionOption {
  return {
    resource_id: resourceId,
    version,
    label,
    status: "published",
    is_default: false,
    summary: {},
  };
}

describe("config option helpers", () => {
  it("uses resource id and version as the stable UI selection key", () => {
    const target = option("term_rule_default", "2", "Default");

    expect(configOptionKey(target)).toBe("term_rule_default@2");
    expect(configVersionId(target)).toBe("term_rule_default@2");
  });

  it("finds options by canonical key before falling back to legacy label", () => {
    const first = option("term_rule_a", "1", "Same label");
    const second = option("term_rule_b", "3", "Same label");
    const options = [first, second];

    expect(findConfigOption(options, "term_rule_b@3")).toBe(second);
    expect(findConfigOption(options, "Same label")).toBe(first);
    expect(findConfigOption(options, "missing")).toBeNull();
  });
});
