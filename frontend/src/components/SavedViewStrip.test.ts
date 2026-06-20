import { renderToString } from "@vue/server-renderer";
import { describe, expect, it } from "vitest";
import { createSSRApp, defineComponent, h } from "vue";

import SavedViewStrip from "@/components/SavedViewStrip.vue";
import type { SavedViewStripItem } from "@/utils/savedViews";

const ElButtonStub = defineComponent({
  name: "ElButton",
  setup(_props, { slots }) {
    return () => h("button", { class: "el-button" }, slots.default?.());
  },
});

const ElDropdownStub = defineComponent({
  name: "ElDropdown",
  setup(_props, { slots }) {
    return () => h("div", { class: "el-dropdown" }, [slots.default?.(), slots.dropdown?.()]);
  },
});

const ElDropdownMenuStub = defineComponent({
  name: "ElDropdownMenu",
  setup(_props, { slots }) {
    return () => h("ul", { class: "el-dropdown-menu" }, slots.default?.());
  },
});

const ElDropdownItemStub = defineComponent({
  name: "ElDropdownItem",
  props: {
    command: { type: String, default: "" },
    disabled: { type: Boolean, default: false },
    divided: { type: Boolean, default: false },
  },
  setup(_props, { slots }) {
    return () => h("li", { class: "el-dropdown-item" }, slots.default?.());
  },
});

async function renderSavedViewStrip(systemViews: SavedViewStripItem[], personalViews: SavedViewStripItem[]): Promise<string> {
  const app = createSSRApp({
    render() {
      return h(SavedViewStrip, {
        systemViews,
        personalViews,
        activeViewId: personalViews[0]?.id ?? null,
        loading: false,
      });
    },
  });
  app.component("el-button", ElButtonStub);
  app.component("el-dropdown", ElDropdownStub);
  app.component("el-dropdown-menu", ElDropdownMenuStub);
  app.component("el-dropdown-item", ElDropdownItemStub);
  return renderToString(app);
}

describe("SavedViewStrip", () => {
  const systemView: SavedViewStripItem = {
    id: "system:jobs:failed",
    source: "system",
    page_key: "jobs",
    name: "失败任务",
    filters: { status: "failed" },
    sort: "updated_at_desc",
  };
  const personalView: SavedViewStripItem = {
    id: "savedview_1",
    source: "personal",
    page_key: "jobs",
    name: "我的失败任务",
    filters: { status: "failed" },
    sort: "updated_at_desc",
    is_default: true,
    position: 0,
  };

  it("renders system and personal saved views with personal actions", async () => {
    const html = await renderSavedViewStrip([systemView], [personalView]);

    expect(html).toContain("失败任务");
    expect(html).toContain("我的失败任务");
    expect(html).toContain("保存当前视图");
    expect(html).toContain("用当前筛选更新");
    expect(html).toContain("设为默认");
  });

  it("declares the action events consumed by operations pages", () => {
    expect((SavedViewStrip as unknown as { emits: string[] }).emits).toEqual(
      expect.arrayContaining([
        "apply",
        "save-current",
        "update",
        "rename",
        "delete",
        "set-default",
        "move",
      ]),
    );
  });
});
