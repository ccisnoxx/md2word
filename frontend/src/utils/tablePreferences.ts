// frontend/src/utils/tablePreferences.ts: Local-only workbench table preference storage and validation.
export type WorkbenchTablePageId = "jobs" | "translation_qa" | "incidents";
export type WorkbenchTableDensity = "standard" | "compact";
export type WorkbenchTablePageSize = 20 | 50 | 100;

export type WorkbenchTableColumn = {
  id: string;
  label: string;
  required: boolean;
  defaultVisible: boolean;
};

export type WorkbenchTablePreferences = {
  density: WorkbenchTableDensity;
  visibleColumns: string[];
  pageSize: WorkbenchTablePageSize;
};

export const WORKBENCH_TABLE_STORAGE_KEYS: Record<WorkbenchTablePageId, string> = {
  jobs: "md2word.workbench.jobs.table",
  translation_qa: "md2word.workbench.translation_qa.table",
  incidents: "md2word.workbench.incidents.table",
};

export const WORKBENCH_TABLE_DENSITIES: WorkbenchTableDensity[] = ["standard", "compact"];
export const WORKBENCH_TABLE_PAGE_SIZES: WorkbenchTablePageSize[] = [20, 50, 100];

export const JOBS_TABLE_COLUMNS: WorkbenchTableColumn[] = [
  { id: "selection", label: "选择", required: true, defaultVisible: true },
  { id: "identity", label: "任务 / 异常", required: true, defaultVisible: true },
  { id: "status", label: "状态", required: true, defaultVisible: true },
  { id: "qa", label: "QA", required: false, defaultVisible: true },
  { id: "progress", label: "进度", required: false, defaultVisible: true },
  { id: "updated", label: "更新", required: false, defaultVisible: true },
  { id: "actions", label: "操作", required: true, defaultVisible: true },
];

export const TRANSLATION_QA_TABLE_COLUMNS: WorkbenchTableColumn[] = [
  { id: "task", label: "任务", required: true, defaultVisible: true },
  { id: "job_status", label: "任务状态", required: false, defaultVisible: true },
  { id: "qa_status", label: "QA 状态", required: true, defaultVisible: true },
  { id: "issue_type", label: "问题归因", required: false, defaultVisible: true },
  { id: "evidence", label: "证据", required: false, defaultVisible: true },
  { id: "reviewer", label: "复核人", required: false, defaultVisible: true },
  { id: "updated", label: "更新", required: false, defaultVisible: true },
  { id: "actions", label: "操作", required: true, defaultVisible: true },
];

export const INCIDENT_TABLE_COLUMNS: WorkbenchTableColumn[] = [
  { id: "selection", label: "选择", required: true, defaultVisible: true },
  { id: "identity", label: "任务 / 证据", required: true, defaultVisible: true },
  { id: "status", label: "状态", required: true, defaultVisible: true },
  { id: "retry", label: "重试", required: false, defaultVisible: true },
  { id: "updated", label: "更新", required: false, defaultVisible: true },
  { id: "actions", label: "操作", required: true, defaultVisible: true },
];

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

function isDensity(value: unknown): value is WorkbenchTableDensity {
  return typeof value === "string" && WORKBENCH_TABLE_DENSITIES.includes(value as WorkbenchTableDensity);
}

export function isWorkbenchTablePageSize(value: unknown): value is WorkbenchTablePageSize {
  return typeof value === "number" && WORKBENCH_TABLE_PAGE_SIZES.includes(value as WorkbenchTablePageSize);
}

function defaultVisibleColumnIds(columns: WorkbenchTableColumn[]): string[] {
  return columns.filter((column) => column.required || column.defaultVisible).map((column) => column.id);
}

export function defaultWorkbenchTablePreferences(columns: WorkbenchTableColumn[]): WorkbenchTablePreferences {
  return {
    density: "standard",
    visibleColumns: defaultVisibleColumnIds(columns),
    pageSize: 20,
  };
}

export function normalizeWorkbenchTablePreferences(
  value: unknown,
  columns: WorkbenchTableColumn[],
): WorkbenchTablePreferences {
  const defaults = defaultWorkbenchTablePreferences(columns);
  if (!value || typeof value !== "object") {
    return defaults;
  }

  const candidate = value as Partial<WorkbenchTablePreferences>;
  const validColumnIds = new Set(columns.map((column) => column.id));
  const requiredColumnIds = columns.filter((column) => column.required).map((column) => column.id);
  const candidateVisibleColumns = Array.isArray(candidate.visibleColumns) ? candidate.visibleColumns : defaults.visibleColumns;
  const visibleColumns = Array.from(new Set([...requiredColumnIds, ...candidateVisibleColumns]))
    .filter((columnId): columnId is string => typeof columnId === "string" && validColumnIds.has(columnId));

  return {
    density: isDensity(candidate.density) ? candidate.density : defaults.density,
    visibleColumns,
    pageSize: isWorkbenchTablePageSize(candidate.pageSize) ? candidate.pageSize : defaults.pageSize,
  };
}

export function getStoredWorkbenchTablePreferences(
  pageId: WorkbenchTablePageId,
  columns: WorkbenchTableColumn[],
): WorkbenchTablePreferences {
  const stored = browserStorage()?.getItem(WORKBENCH_TABLE_STORAGE_KEYS[pageId]);
  if (!stored) {
    return defaultWorkbenchTablePreferences(columns);
  }
  try {
    return normalizeWorkbenchTablePreferences(JSON.parse(stored), columns);
  } catch {
    return defaultWorkbenchTablePreferences(columns);
  }
}

export function persistWorkbenchTablePreferences(
  pageId: WorkbenchTablePageId,
  preferences: WorkbenchTablePreferences,
  columns: WorkbenchTableColumn[],
): WorkbenchTablePreferences {
  const normalized = normalizeWorkbenchTablePreferences(preferences, columns);
  browserStorage()?.setItem(WORKBENCH_TABLE_STORAGE_KEYS[pageId], JSON.stringify(normalized));
  return normalized;
}

export function resetWorkbenchTablePreferences(
  pageId: WorkbenchTablePageId,
  columns: WorkbenchTableColumn[],
): WorkbenchTablePreferences {
  browserStorage()?.removeItem(WORKBENCH_TABLE_STORAGE_KEYS[pageId]);
  return defaultWorkbenchTablePreferences(columns);
}

export function isWorkbenchTableColumnVisible(preferences: WorkbenchTablePreferences, columnId: string): boolean {
  return preferences.visibleColumns.includes(columnId);
}

export function setWorkbenchTableColumnVisibility(
  preferences: WorkbenchTablePreferences,
  columns: WorkbenchTableColumn[],
  columnId: string,
  visible: boolean,
): WorkbenchTablePreferences {
  const column = columns.find((item) => item.id === columnId);
  if (!column || column.required) {
    return normalizeWorkbenchTablePreferences(preferences, columns);
  }
  const visibleColumnSet = new Set(preferences.visibleColumns);
  if (visible) {
    visibleColumnSet.add(columnId);
  } else {
    visibleColumnSet.delete(columnId);
  }
  return normalizeWorkbenchTablePreferences(
    {
      ...preferences,
      visibleColumns: Array.from(visibleColumnSet),
    },
    columns,
  );
}
