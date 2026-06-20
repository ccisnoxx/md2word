// File: frontend/src/utils/operatorCommands.ts
// Purpose: Build permission-filtered command-palette entries from app navigation and saved-view contracts.
import type { RouteLocationRaw } from "vue-router";

import type { SavedViewPageKey, SavedViewResponse } from "@/api/types";
import {
  getAppNavigationGroups,
  type AppAccessContext,
  type AppNavGroupId,
  type AppNavItemId,
} from "@/navigation/appShell";
import {
  SAVED_VIEW_PAGE_LABELS,
  personalSavedViewToStripItem,
  routeForSavedView,
  systemSavedViews,
  type SavedViewStripItem,
} from "@/utils/savedViews";

export type OperatorCommandGroupId = "pages" | "saved_views";

export type OperatorCommand = {
  id: string;
  groupId: OperatorCommandGroupId;
  title: string;
  description: string;
  keywords: string[];
  to: RouteLocationRaw;
};

export type OperatorCommandGroup = {
  id: OperatorCommandGroupId;
  label: string;
  commands: OperatorCommand[];
};

const PAGE_COMMAND_IDS: AppNavItemId[] = ["cockpit", "jobs", "incidents", "translation-qa", "job-create", "ops-dashboard"];

const GROUP_LABELS: Record<OperatorCommandGroupId, string> = {
  pages: "页面入口",
  saved_views: "保存视图",
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

