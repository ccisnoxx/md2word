import { afterEach, describe, expect, it, vi } from "vitest";

import {
  defaultWorkbenchTablePreferences,
  getStoredWorkbenchTablePreferences,
  JOBS_TABLE_COLUMNS,
  normalizeWorkbenchTablePreferences,
  persistWorkbenchTablePreferences,
  resetWorkbenchTablePreferences,
  setWorkbenchTableColumnVisibility,
  WORKBENCH_TABLE_STORAGE_KEYS,
  type WorkbenchTablePreferences,
} from "@/utils/tablePreferences";

function stubBrowser(storedValue: string | null = null) {
  const store = new Map<string, string>();
  if (storedValue !== null) {
    store.set(WORKBENCH_TABLE_STORAGE_KEYS.jobs, storedValue);
  }
  const localStorage = {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
  };

  vi.stubGlobal("window", { localStorage });

  return { localStorage, store };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("workbench table preferences", () => {
  it("defaults to standard density, default columns, and 20 rows outside the browser", () => {
    expect(getStoredWorkbenchTablePreferences("jobs", JOBS_TABLE_COLUMNS)).toEqual(defaultWorkbenchTablePreferences(JOBS_TABLE_COLUMNS));
  });

  it("falls back safely when localStorage contains malformed JSON", () => {
    stubBrowser("{not-json");

    expect(getStoredWorkbenchTablePreferences("jobs", JOBS_TABLE_COLUMNS)).toEqual(defaultWorkbenchTablePreferences(JOBS_TABLE_COLUMNS));
  });

  it("normalizes unsupported fields and keeps required columns visible", () => {
    const normalized = normalizeWorkbenchTablePreferences(
      {
        density: "dense",
        visibleColumns: ["qa", "unknown"],
        pageSize: 25,
      },
      JOBS_TABLE_COLUMNS,
    );

    expect(normalized).toMatchObject({
      density: "standard",
      pageSize: 20,
    });
    expect(normalized.visibleColumns).toEqual(["selection", "identity", "status", "actions", "qa"]);
  });

  it("hides and restores optional columns without hiding required columns", () => {
    const defaults = defaultWorkbenchTablePreferences(JOBS_TABLE_COLUMNS);
    const withoutQa = setWorkbenchTableColumnVisibility(defaults, JOBS_TABLE_COLUMNS, "qa", false);
    const withoutRequired = setWorkbenchTableColumnVisibility(withoutQa, JOBS_TABLE_COLUMNS, "identity", false);
    const restoredQa = setWorkbenchTableColumnVisibility(withoutRequired, JOBS_TABLE_COLUMNS, "qa", true);

    expect(withoutQa.visibleColumns).not.toContain("qa");
    expect(withoutRequired.visibleColumns).toContain("identity");
    expect(restoredQa.visibleColumns).toContain("qa");
  });

  it("persists normalized preferences under the page-scoped key", () => {
    const { localStorage, store } = stubBrowser();
    const preferences: WorkbenchTablePreferences = {
      density: "compact",
      visibleColumns: ["identity", "status", "actions"],
      pageSize: 100,
    };

    const normalized = persistWorkbenchTablePreferences("jobs", preferences, JOBS_TABLE_COLUMNS);

    expect(localStorage.setItem).toHaveBeenCalledWith(WORKBENCH_TABLE_STORAGE_KEYS.jobs, JSON.stringify(normalized));
    expect(JSON.parse(store.get(WORKBENCH_TABLE_STORAGE_KEYS.jobs) || "{}")).toMatchObject({
      density: "compact",
      pageSize: 100,
    });
  });

  it("resets page-scoped storage and returns defaults", () => {
    const { localStorage } = stubBrowser(JSON.stringify({ density: "compact", visibleColumns: ["identity"], pageSize: 50 }));

    expect(resetWorkbenchTablePreferences("jobs", JOBS_TABLE_COLUMNS)).toEqual(defaultWorkbenchTablePreferences(JOBS_TABLE_COLUMNS));
    expect(localStorage.removeItem).toHaveBeenCalledWith(WORKBENCH_TABLE_STORAGE_KEYS.jobs);
  });
});
