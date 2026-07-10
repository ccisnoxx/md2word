// frontend/src/pages/MinerUConfigPage.test.ts: 守护 MinerU 配置页的密钥不回显边界。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(fileURLToPath(new URL("./MinerUConfigPage.vue", import.meta.url)), "utf8");

describe("MinerUConfigPage secret boundary", () => {
  it("只提供密码输入和安全状态，不实现当前密钥回显或清空操作", () => {
    expect(source).toContain('type="password"');
    expect(source).toContain('return config.value.api_token_configured ? "configured" : "missing";');
    expect(source).not.toContain("show-password");
    expect(source).not.toContain("api_token_mask");
    expect(source).not.toContain("clear_api_token");
  });

  it("成功后清空输入并且不调用测试密钥接口", () => {
    expect(source).toContain('form.api_token = "";');
    expect(source).toContain("mineruConfigApi.update");
    expect(source).not.toContain("testToken");
    expect(source).not.toContain("validateToken");
  });
});
