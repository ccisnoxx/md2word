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

export function persistThemeMode(mode: ThemeMode): void {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  }
  applyThemeMode(mode);
}
