// frontend/src/utils/sidebarState.ts: Persist the desktop sidebar collapse preference only.
const SIDEBAR_COLLAPSED_KEY = "md2word.sidebar.collapsed";

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

export { SIDEBAR_COLLAPSED_KEY };
