// 文件：frontend/src/utils/operatorCommands.ts
// 用途：按权限构建命令面板的页面入口、保存视图、实时匹配任务与快捷操作命令。
import type { RouteLocationRaw } from "vue-router";

import type { DocumentJobResponse, SavedViewPageKey, SavedViewResponse } from "@/api/types";
import {
  getAppNavigationGroups,
  type AppAccessContext,
  type AppNavGroupId,
  type AppNavItemId,
} from "@/navigation/appShell";
import { getJobSourceFilename, jobModeText, jobStatusText } from "@/utils/format";
import {
  SAVED_VIEW_PAGE_LABELS,
  personalSavedViewToStripItem,
  routeForSavedView,
  systemSavedViews,
  type SavedViewStripItem,
} from "@/utils/savedViews";

export type OperatorCommandGroupId = "jobs" | "pages" | "saved_views" | "actions";

export type OperatorCommandAction = "toggle-theme";

export type OperatorCommand = {
  id: string;
  groupId: OperatorCommandGroupId;
  title: string;
  description: string;
  keywords: string[];
  to?: RouteLocationRaw;
  action?: OperatorCommandAction;
};

export type OperatorCommandGroup = {
  id: OperatorCommandGroupId;
  label: string;
  commands: OperatorCommand[];
};

const PAGE_COMMAND_IDS: AppNavItemId[] = ["cockpit", "jobs", "incidents", "translation-qa", "job-create", "ops-dashboard"];

const GROUP_LABELS: Record<OperatorCommandGroupId, string> = {
  jobs: "匹配任务",
  pages: "页面入口",
  saved_views: "保存视图",
  actions: "快捷操作",
};

const NAV_GROUP_LABELS: Record<AppNavGroupId, string> = {
  processing: "处理队列",
  quality: "质量治理",
  configuration: "配置发布",
  system: "系统运维",
};

export function savedViewPageKeysForAccess(access: AppAccessContext): SavedViewPageKey[] {
  const pageKeys: SavedViewPageKey[] = [];
  if (access.permissions.includes("document_jobs:read")) {
    pageKeys.push("jobs", "incidents");
  }
  if (access.permissions.includes("translation_qa:read")) {
    pageKeys.push("translation_qa");
  }
  return pageKeys;
}

export function buildPageCommands(access: AppAccessContext): OperatorCommand[] {
  return getAppNavigationGroups(access).flatMap((group) =>
    group.items
      .filter((item) => PAGE_COMMAND_IDS.includes(item.id))
      .map((item) => ({
        id: `page:${item.id}`,
        groupId: "pages" as const,
        title: item.label,
        description: NAV_GROUP_LABELS[group.id],
        keywords: [item.id, group.id, item.label],
        to: item.to,
      })),
  );
}

export function buildSavedViewCommands(
  access: AppAccessContext,
  savedViewsByPage: Partial<Record<SavedViewPageKey, SavedViewResponse[]>>,
): OperatorCommand[] {
  return savedViewPageKeysForAccess(access).flatMap((pageKey) => {
    const personalViews = (savedViewsByPage[pageKey] || []).filter((view) => view.page_key === pageKey).map(personalSavedViewToStripItem);
    const orderedPersonalViews = [...personalViews].sort(compareSavedViews);
    return [...orderedPersonalViews, ...systemSavedViews[pageKey]].map((view) => savedViewCommand(pageKey, view));
  });
}

export function buildJobSearchCommands(jobs: DocumentJobResponse[]): OperatorCommand[] {
  return jobs.map((job) => {
    const filename = getJobSourceFilename(job);
    const modeLabel = jobModeText[job.mode] || job.mode;
    const statusLabel = jobStatusText[job.status] || job.status;
    return {
      id: `job:${job.id}`,
      groupId: "jobs",
      title: filename,
      description: `${modeLabel} · ${statusLabel} · ${job.id}`,
      keywords: [job.id, filename, job.mode, modeLabel, job.status, statusLabel],
      to: { name: "job-detail", params: { jobId: job.id } },
    };
  });
}

export function buildQuickActionCommands(): OperatorCommand[] {
  return [
    {
      id: "action:toggle-theme",
      groupId: "actions",
      title: "切换深色 / 浅色主题",
      description: "在跟随系统、深色与浅色模式间切换",
      keywords: ["theme", "dark", "light", "system", "主题", "深色", "浅色", "暗黑"],
      action: "toggle-theme",
    },
  ];
}

export function filterOperatorCommands(commands: OperatorCommand[], query: string): OperatorCommand[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return commands;
  }
  return commands.filter((command) => {
    const haystack = [command.title, command.description, ...command.keywords].join(" ").toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

export function groupOperatorCommands(commands: OperatorCommand[]): OperatorCommandGroup[] {
  return (Object.keys(GROUP_LABELS) as OperatorCommandGroupId[])
    .map((groupId) => ({
      id: groupId,
      label: GROUP_LABELS[groupId],
      commands: commands.filter((command) => command.groupId === groupId),
    }))
    .filter((group) => group.commands.length > 0);
}

function savedViewCommand(pageKey: SavedViewPageKey, view: SavedViewStripItem): OperatorCommand {
  return {
    id: `saved-view:${view.id}`,
    groupId: "saved_views",
    title: `${SAVED_VIEW_PAGE_LABELS[pageKey]} · ${view.name}`,
    description: view.source === "personal" ? (view.is_default ? "个人默认视图" : "个人保存视图") : "系统预设视图",
    keywords: [pageKey, view.name, SAVED_VIEW_PAGE_LABELS[pageKey], view.source],
    to: routeForSavedView(view),
  };
}

function compareSavedViews(left: SavedViewStripItem, right: SavedViewStripItem): number {
  if (left.is_default !== right.is_default) {
    return left.is_default ? -1 : 1;
  }
  return (left.position ?? Number.MAX_SAFE_INTEGER) - (right.position ?? Number.MAX_SAFE_INTEGER) || left.name.localeCompare(right.name);
}
