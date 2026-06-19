import { afterEach, describe, expect, it, vi } from "vitest";

import { getStoredSidebarCollapsed, persistSidebarCollapsed, SIDEBAR_COLLAPSED_KEY } from "@/utils/sidebarState";

function stubBrowser(storedValue: string | null = null) {
  const store = new Map<string, string>();
  if (storedValue !== null) {
    store.set(SIDEBAR_COLLAPSED_KEY, storedValue);
  }
  const localStorage = {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
  };

  vi.stubGlobal("window", { localStorage });

  return { localStorage };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sidebar state utilities", () => {
  it("defaults to expanded outside the browser", () => {
    expect(getStoredSidebarCollapsed()).toBe(false);
  });

  it("only treats the literal true value as collapsed", () => {
    stubBrowser("true");
    expect(getStoredSidebarCollapsed()).toBe(true);

    vi.unstubAllGlobals();
    stubBrowser("false");
    expect(getStoredSidebarCollapsed()).toBe(false);

    vi.unstubAllGlobals();
    stubBrowser("collapsed");
    expect(getStoredSidebarCollapsed()).toBe(false);
  });

  it("persists the desktop collapsed state with the app shell key", () => {
    const { localStorage } = stubBrowser();

    persistSidebarCollapsed(true);
    expect(localStorage.setItem).toHaveBeenCalledWith(SIDEBAR_COLLAPSED_KEY, "true");

    persistSidebarCollapsed(false);
    expect(localStorage.setItem).toHaveBeenCalledWith(SIDEBAR_COLLAPSED_KEY, "false");
  });
});
