import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const componentSource = readFileSync(
  fileURLToPath(new URL("./TemplateVersionLifecycleActions.vue", import.meta.url)),
  "utf8",
);
const stylePageSource = readFileSync(
  fileURLToPath(new URL("../pages/WordPageStyleDetailPage.vue", import.meta.url)),
  "utf8",
);
const templatePageSource = readFileSync(
  fileURLToPath(new URL("../pages/TemplateDetailPage.vue", import.meta.url)),
  "utf8",
);

describe("TemplateVersionLifecycleActions", () => {
  it("按当前 Template Version 状态提供验证、发布、设默认和默认标识", () => {
    expect(componentSource).toContain("version.status === 'draft'");
    expect(componentSource).toContain("version.status === 'published' && !version.is_default");
    expect(componentSource).toContain("当前默认");
    expect(componentSource).toContain("templatesApi.publishVersion");
    expect(componentSource).toContain("make_default: false");
    expect(componentSource).toContain("状态为 succeeded 且绑定当前版本");
    expect(componentSource).toContain("templatesApi.setDefaultVersion");
    expect(componentSource).toContain("template_version_id: templateVersionId.value");
  });

  it("同时接入页面样式详情和模板版本总览", () => {
    expect(stylePageSource).toContain("<TemplateVersionLifecycleActions");
    expect(stylePageSource).toContain(':version="currentTemplateVersion"');
    expect(templatePageSource).toContain("<TemplateVersionLifecycleActions");
    expect(templatePageSource).toContain("management");
  });
});
