import { describe, expect, it } from "vitest";

import type { SavedViewResponse } from "@/api/types";
import type { AppAccessContext } from "@/navigation/appShell";
import {
  buildPageCommands,
  buildSavedViewCommands,
  filterOperatorCommands,
  groupOperatorCommands,
  savedViewPageKeysForAccess,
} from "@/utils/operatorCommands";

const operatorAccess: AppAccessContext = {
  role: "operator",
  roles: ["operator"],
  permissions: ["document_jobs:read", "document_jobs:create", "translation_qa:read"],
};

const adminAccess: AppAccessContext = {
  role: "admin",
  roles: ["admin"],
  permissions: [...operatorAccess.permissions, "ops:read"],
};

function buildSavedView(overrides: Partial<SavedViewResponse> = {}): SavedViewResponse {
  return {
    view_id: "savedview_default",
    tenant_id: "tenant_default",
    company_id: "company_default",
    owner_user_id: "user_operator",
    page_key: "jobs",
    name: "我的失败任务",
    filters: { status: "failed" },
    sort: "updated_at_desc",
    is_default: true,
    position: 0,
    created_at: "2026-06-20T00:00:00Z",
    updated_at: "2026-06-20T00:00:00Z",
    ...overrides,
  };
}

describe("operator commands", () => {
  it("builds only permitted high-frequency page commands", () => {
    expect(buildPageCommands(operatorAccess).map((command) => command.title)).toEqual([
      "今日工作",
      "任务工作台",
      "异常处理",
      "创建任务",
      "翻译 QA",
    ]);
    expect(buildPageCommands(adminAccess).map((command) => command.title)).toContain("运维看板");
  });

  it("loads saved views only for accessible operation page keys", () => {
    expect(savedViewPageKeysForAccess({ role: "operator", roles: ["operator"], permissions: ["translation_qa:read"] })).toEqual([
      "translation_qa",
    ]);
    expect(savedViewPageKeysForAccess(operatorAccess)).toEqual(["jobs", "incidents", "translation_qa"]);
  });

  it("puts personal default saved views before system presets and builds route queries", () => {
    const commands = buildSavedViewCommands(operatorAccess, {
      jobs: [
        buildSavedView({ view_id: "savedview_later", name: "稍后处理", is_default: false, position: 1 }),
        buildSavedView(),
      ],
    });

    expect(commands[0]).toMatchObject({
      title: "任务工作台 · 我的失败任务",
      description: "个人默认视图",
      to: { name: "jobs", query: { status: "failed", page: "1" } },
    });
    expect(commands.map((command) => command.title)).toContain("异常处理 · 可重试异常");
  });

  it("filters and groups commands using Chinese labels and technical keywords", () => {
    const commands = [...buildPageCommands(operatorAccess), ...buildSavedViewCommands(operatorAccess, {})];
    const filtered = filterOperatorCommands(commands, "失败");

    expect(filtered.map((command) => command.title)).toEqual(expect.arrayContaining(["任务工作台 · 失败任务"]));
    expect(groupOperatorCommands(filtered).map((group) => group.label)).toContain("保存视图");
  });
});

