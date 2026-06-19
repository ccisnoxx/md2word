// frontend/src/navigation/appShell.ts: App shell navigation IA, permission filtering, and route ownership.
import type { Component } from "vue";
import type { RouteLocationNormalizedLoaded, RouteLocationRaw } from "vue-router";
import {
  Collection,
  DataAnalysis,
  Document,
  DocumentAdd,
  DocumentChecked,
  Files,
  FolderOpened,
  Management,
  Monitor,
  Notebook,
  Operation,
  Reading,
  Setting,
  Stamp,
  Ticket,
} from "@element-plus/icons-vue";

export type AppNavGroupId = "processing" | "quality" | "configuration" | "system";

export type AppNavItemId =
  | "jobs"
  | "incidents"
  | "job-create"
  | "translation-qa"
  | "term-proposals"
  | "term-rule-sets"
  | "term-rules"
  | "translation-term-sets"
  | "settings"
  | "templates"
  | "word-page-styles"
  | "translation-profiles"
  | "system-status"
  | "audit-events"
  | "file-retention"
  | "ops-dashboard";

export type AppAccessContext = {
  role?: string | null;
  roles: string[];
  permissions: string[];
};

export type AppBreadcrumbItem = {
  label: string;
  to?: RouteLocationRaw;
};

export type AppNavTone = "default" | "success" | "warning" | "danger";

export type AppNavItem = {
  id: AppNavItemId;
  label: string;
  to: RouteLocationRaw;
  icon: Component;
  roles?: string[];
  permissions?: string[];
  badge?: string;
  tone?: AppNavTone;
};

export type AppNavGroup = {
  id: AppNavGroupId;
  label: string;
  icon: Component;
  items: AppNavItem[];
};

export type AppRouteContext = {
  groupId: AppNavGroupId | null;
  itemId: AppNavItemId | null;
  moduleLabel: string;
  pageLabel: string;
  breadcrumbs: AppBreadcrumbItem[];
};

type AppNavItemDefinition = Omit<AppNavItem, "label"> & {
  label: string | ((access: AppAccessContext) => string);
};

type AppNavGroupDefinition = Omit<AppNavGroup, "items"> & {
  items: AppNavItemDefinition[];
};

type RouteOwnership = {
  groupId: AppNavGroupId | null;
  itemId: AppNavItemId | null;
  moduleLabel?: string;
  pageLabel?: string;
};

const GROUP_LABELS: Record<AppNavGroupId, string> = {
  processing: "处理队列",
  quality: "质量治理",
  configuration: "配置发布",
  system: "系统运维",
};

const NAV_GROUP_DEFINITIONS: AppNavGroupDefinition[] = [
  {
    id: "processing",
    label: GROUP_LABELS.processing,
    icon: Files,
    items: [
      { id: "jobs", label: "任务工作台", to: "/jobs", icon: Files, permissions: ["document_jobs:read"] },
      { id: "incidents", label: "异常处理", to: "/incidents", icon: Operation, permissions: ["document_jobs:read"] },
      { id: "job-create", label: "创建任务", to: "/jobs/new", icon: DocumentAdd, permissions: ["document_jobs:create"] },
    ],
  },
  {
    id: "quality",
    label: GROUP_LABELS.quality,
    icon: Reading,
    items: [
      { id: "translation-qa", label: "翻译 QA", to: "/translation-qa", icon: Reading, permissions: ["translation_qa:read"] },
      {
        id: "term-proposals",
        label: (access) => (access.permissions.includes("term_proposals:review") ? "提案审核" : "术语建议"),
        to: "/term-proposals",
        icon: Stamp,
        permissions: ["term_proposals:read"],
      },
      { id: "term-rule-sets", label: "术语发布", to: "/settings/term-rule-sets", icon: Ticket, permissions: ["settings:read"] },
      { id: "term-rules", label: "术语规则", to: "/settings/term-rules", icon: Collection, permissions: ["settings:read"] },
      {
        id: "translation-term-sets",
        label: "翻译术语集",
        to: "/settings/translation-term-sets",
        icon: Notebook,
        permissions: ["settings:read"],
      },
    ],
  },
  {
    id: "configuration",
    label: GROUP_LABELS.configuration,
    icon: Setting,
    items: [
      { id: "settings", label: "配置中心", to: "/settings", icon: Setting, permissions: ["settings:read"] },
      { id: "templates", label: "Word 模板", to: "/settings/templates", icon: FolderOpened, roles: ["admin"], permissions: ["settings:read"] },
      {
        id: "word-page-styles",
        label: "页面样式",
        to: "/settings/word-page-styles",
        icon: Document,
        roles: ["admin"],
        permissions: ["settings:read"],
      },
      {
        id: "translation-profiles",
        label: "翻译配置",
        to: "/settings/translation-profiles",
        icon: Management,
        permissions: ["settings:read"],
      },
    ],
  },
  {
    id: "system",
    label: GROUP_LABELS.system,
    icon: Monitor,
    items: [
      { id: "system-status", label: "系统状态", to: "/system-status", icon: Monitor, permissions: ["system:read"] },
      { id: "audit-events", label: "审计日志", to: "/system-status/audit-events", icon: DataAnalysis, permissions: ["audit:read"] },
      {
        id: "file-retention",
        label: "文件保留",
        to: "/system-status/file-retention",
        icon: Operation,
        permissions: ["files:retention"],
      },
      { id: "ops-dashboard", label: "运维看板", to: "/system-status/ops-dashboard", icon: DocumentChecked, permissions: ["ops:read"] },
    ],
  },
];

const ROUTE_OWNERS: Record<string, RouteOwnership> = {
  jobs: { groupId: "processing", itemId: "jobs", pageLabel: "任务工作台" },
  incidents: { groupId: "processing", itemId: "incidents", pageLabel: "异常处理" },
  "job-create": { groupId: "processing", itemId: "job-create", pageLabel: "创建任务" },
  "job-detail": { groupId: "processing", itemId: "jobs", pageLabel: "任务详情" },
  "translation-qa": { groupId: "quality", itemId: "translation-qa", pageLabel: "翻译 QA" },
  settings: { groupId: "configuration", itemId: "settings", pageLabel: "配置中心" },
  "settings-templates": { groupId: "configuration", itemId: "templates", pageLabel: "Word 模板" },
  "settings-template-detail": { groupId: "configuration", itemId: "templates", pageLabel: "Word 模板详情" },
  "settings-word-page-styles": { groupId: "configuration", itemId: "word-page-styles", pageLabel: "页面样式" },
  "settings-word-page-style-detail": { groupId: "configuration", itemId: "word-page-styles", pageLabel: "页面样式详情" },
  "settings-term-rule-sets": { groupId: "quality", itemId: "term-rule-sets", pageLabel: "术语发布" },
  "settings-term-rules": { groupId: "quality", itemId: "term-rules", pageLabel: "术语规则" },
  "settings-translation-profiles": { groupId: "configuration", itemId: "translation-profiles", pageLabel: "翻译配置" },
  "settings-translation-term-sets": { groupId: "quality", itemId: "translation-term-sets", pageLabel: "翻译术语集" },
  "term-proposals": { groupId: "quality", itemId: "term-proposals" },
  "system-status": { groupId: "system", itemId: "system-status", pageLabel: "系统状态" },
  "system-status-ops-dashboard": { groupId: "system", itemId: "ops-dashboard", pageLabel: "运维看板" },
  "system-status-audit-events": { groupId: "system", itemId: "audit-events", pageLabel: "审计日志" },
  "system-status-file-retention": { groupId: "system", itemId: "file-retention", pageLabel: "文件保留" },
  forbidden: { groupId: null, itemId: null, moduleLabel: "访问控制", pageLabel: "没有访问权限" },
};

function materializeItem(item: AppNavItemDefinition, access: AppAccessContext): AppNavItem {
  return {
    ...item,
    label: typeof item.label === "function" ? item.label(access) : item.label,
  };
}

function hasRouteAccess(item: AppNavItemDefinition, access: AppAccessContext): boolean {
  if (item.roles?.length && !item.roles.includes(access.role ?? "")) {
    return false;
  }
  if (item.permissions?.length && !item.permissions.every((permission) => access.permissions.includes(permission))) {
    return false;
  }
  return true;
}

export function getAppNavigationGroups(access: AppAccessContext): AppNavGroup[] {
  return NAV_GROUP_DEFINITIONS.map((group) => ({
    ...group,
    items: group.items.filter((item) => hasRouteAccess(item, access)).map((item) => materializeItem(item, access)),
  })).filter((group) => group.items.length > 0);
}

export function findNavigationItem(itemId: AppNavItemId | null, access: AppAccessContext): AppNavItem | null {
  if (!itemId) {
    return null;
  }
  for (const group of getAppNavigationGroups(access)) {
    const item = group.items.find((candidate) => candidate.id === itemId);
    if (item) {
      return item;
    }
  }
  return null;
}

function stringParam(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function queryStringValues(route: RouteLocationNormalizedLoaded, keys: string[]): Record<string, string> {
  const query: Record<string, string> = {};
  for (const key of keys) {
    const value = route.query[key];
    if (typeof value === "string" && value.trim()) {
      query[key] = value;
    }
  }
  return query;
}

function terminologyWorkbenchRoute(route: RouteLocationNormalizedLoaded): RouteLocationRaw {
  return {
    path: "/settings/term-rule-sets",
    query: queryStringValues(route, ["proposal_id", "source_term", "target_rule_id", "return_tab", "set_id"]),
  };
}

export function getBreadcrumbItems(route: RouteLocationNormalizedLoaded, access: AppAccessContext): AppBreadcrumbItem[] {
  const jobId = stringParam(route.params.jobId);
  const templateId = stringParam(route.params.templateId);

  switch (route.name) {
    case "jobs":
      return [{ label: "任务工作台" }];
    case "job-create":
      return [
        { label: "任务工作台", to: "/jobs" },
        { label: "创建任务" },
      ];
    case "translation-qa":
      return [{ label: "翻译 QA" }];
    case "job-detail":
      return [
        { label: "任务工作台", to: "/jobs" },
        { label: "任务详情" },
        { label: jobId },
      ];
    case "job-translation-qa":
      if (route.query.from === "translation-qa") {
        return [
          {
            label: "翻译 QA",
            to: {
              path: "/translation-qa",
              query: queryStringValues(route, ["translation_qa_status", "status", "sort", "include_archived", "q", "page"]),
            },
          },
          { label: jobId },
        ];
      }
      return [
        { label: "任务工作台", to: "/jobs" },
        { label: "任务详情", to: `/jobs/${jobId}` },
        { label: "翻译 QA" },
      ];
    case "settings":
      return [{ label: "配置中心" }];
    case "settings-templates":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "Word 模板文档" },
      ];
    case "settings-template-detail":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "Word 模板文档", to: "/settings/templates" },
        { label: templateId },
      ];
    case "settings-word-page-styles":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "Word 页面样式配置" },
      ];
    case "settings-word-page-style-detail":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "Word 页面样式配置", to: "/settings/word-page-styles" },
        { label: templateId },
      ];
    case "settings-term-rule-sets":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "术语工作台", to: terminologyWorkbenchRoute(route) },
        { label: "草稿与发布" },
      ];
    case "settings-term-rules":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "术语工作台", to: terminologyWorkbenchRoute(route) },
        { label: "当前生效规则" },
      ];
    case "settings-translation-profiles":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "翻译配置" },
      ];
    case "settings-translation-term-sets":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "翻译术语集" },
      ];
    case "term-proposals":
      return [{ label: access.permissions.includes("term_proposals:review") ? "提案审核" : "术语建议" }];
    case "system-status":
      return [{ label: "系统状态" }];
    case "system-status-ops-dashboard":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "运维看板" },
      ];
    case "system-status-audit-events":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "审计日志" },
      ];
    case "system-status-file-retention":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "文件管理与清理" },
      ];
    case "forbidden":
      return [{ label: "没有访问权限" }];
    default:
      return [];
  }
}

function routeOwnership(route: RouteLocationNormalizedLoaded): RouteOwnership {
  if (route.name === "job-translation-qa") {
    if (route.query.from === "translation-qa") {
      return { groupId: "quality", itemId: "translation-qa", pageLabel: "翻译 QA" };
    }
    return { groupId: "processing", itemId: "jobs", pageLabel: "翻译 QA" };
  }
  return ROUTE_OWNERS[String(route.name ?? "")] ?? { groupId: null, itemId: null };
}

export function getAppRouteContext(route: RouteLocationNormalizedLoaded, access: AppAccessContext): AppRouteContext {
  const ownership = routeOwnership(route);
  const breadcrumbs = getBreadcrumbItems(route, access);
  const navItem = findNavigationItem(ownership.itemId, access);
  const pageLabel = ownership.pageLabel ?? navItem?.label ?? breadcrumbs[breadcrumbs.length - 1]?.label ?? "工作台";
  const moduleLabel = ownership.moduleLabel ?? (ownership.groupId ? GROUP_LABELS[ownership.groupId] : pageLabel);

  return {
    groupId: ownership.groupId,
    itemId: ownership.itemId,
    moduleLabel,
    pageLabel,
    breadcrumbs,
  };
}
