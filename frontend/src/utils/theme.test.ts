import { afterEach, describe, expect, it, vi } from "vitest";

import { applyThemeMode, getStoredThemeMode, persistThemeMode } from "@/utils/theme";

function stubBrowser(storedValue: string | null = null) {
  const store = new Map<string, string>();
  if (storedValue !== null) {
    store.set("md2word.theme.mode", storedValue);
  }
  const root = {
    dataset: {} as Record<string, string>,
    removeAttribute: vi.fn((name: string) => {
      if (name === "data-theme") {
        delete root.dataset.theme;
      }
    }),
  };
  const localStorage = {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
  };

  vi.stubGlobal("window", { localStorage });
  vi.stubGlobal("document", { documentElement: root });

  return { localStorage, root };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("theme utilities", () => {
  it("defaults to system theme outside the browser", () => {
    expect(getStoredThemeMode()).toBe("system");
  });

  it("reads only supported theme modes from localStorage", () => {
    stubBrowser("dark");
    expect(getStoredThemeMode()).toBe("dark");

    vi.unstubAllGlobals();
    stubBrowser("neon");
    expect(getStoredThemeMode()).toBe("system");
  });

  it("applies explicit and system theme attributes to the document root", () => {
    const { root } = stubBrowser();

    applyThemeMode("dark");
    expect(root.dataset.theme).toBe("dark");
    expect(root.dataset.themeMode).toBe("dark");

    applyThemeMode("system");
    expect(root.removeAttribute).toHaveBeenCalledWith("data-theme");
    expect(root.dataset.theme).toBeUndefined();
    expect(root.dataset.themeMode).toBe("system");
  });

  it("persists theme mode before applying it", () => {
    const { localStorage, root } = stubBrowser();

    persistThemeMode("light");

    expect(localStorage.setItem).toHaveBeenCalledWith("md2word.theme.mode", "light");
    expect(root.dataset.theme).toBe("light");
    expect(root.dataset.themeMode).toBe("light");
  });
});
