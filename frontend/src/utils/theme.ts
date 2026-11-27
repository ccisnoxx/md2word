// frontend/src/utils/theme.ts: Persist and apply the visual theme without coupling it to business state.
export type ThemeMode = "system" | "light" | "dark";

const THEME_STORAGE_KEY = "md2word.theme.mode";
const THEME_MODES: ThemeMode[] = ["system", "light", "dark"];

function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && THEME_MODES.includes(value as ThemeMode);
}

export function getStoredThemeMode(): ThemeMode {
  if (typeof window === "undefined") {
    return "system";
  }
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return isThemeMode(stored) ? stored : "system";
}

export function applyThemeMode(mode: ThemeMode): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  if (mode === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.dataset.theme = mode;
  }
  root.dataset.themeMode = mode;
}

export const THEME_CHANGE_EVENT = "md2word:theme-change";

export function persistThemeMode(mode: ThemeMode): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
    if (typeof window.dispatchEvent === "function" && typeof CustomEvent === "function") {
      window.dispatchEvent(new CustomEvent<ThemeMode>(THEME_CHANGE_EVENT, { detail: mode }));
    }
  }
  applyThemeMode(mode);
}

export function cycleStoredThemeMode(): ThemeMode {
  const current = getStoredThemeMode();
  const order: ThemeMode[] = ["system", "dark", "light"];
  const next = order[(order.indexOf(current) + 1) % order.length] || "system";
  persistThemeMode(next);
  return next;
}
