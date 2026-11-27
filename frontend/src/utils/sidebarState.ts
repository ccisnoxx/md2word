// 文件：frontend/src/utils/sidebarState.ts
// 用途：持久化桌面侧边栏收起状态与导航分组展开偏好。
const SIDEBAR_COLLAPSED_KEY = "md2word.sidebar.collapsed";
const SIDEBAR_OPEN_GROUPS_KEY = "md2word.sidebar.open_groups";

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function getStoredSidebarCollapsed(): boolean {
  const stored = browserStorage()?.getItem(SIDEBAR_COLLAPSED_KEY);
  return stored === "true";
}

export function persistSidebarCollapsed(collapsed: boolean): void {
  browserStorage()?.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "true" : "false");
}

export function getStoredSidebarOpenGroups(): string[] | null {
  const raw = browserStorage()?.getItem(SIDEBAR_OPEN_GROUPS_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }
    return parsed.filter((item): item is string => typeof item === "string");
  } catch {
    return null;
  }
}

export function persistSidebarOpenGroups(groupIds: string[]): void {
  try {
    browserStorage()?.setItem(SIDEBAR_OPEN_GROUPS_KEY, JSON.stringify(groupIds));
  } catch {
    // 浏览器禁用或配额满时忽略本地 UI 偏好持久化失败。
  }
}

export { SIDEBAR_COLLAPSED_KEY, SIDEBAR_OPEN_GROUPS_KEY };
