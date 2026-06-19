<!-- frontend/src/components/AppThemeToggle.vue: Shared light/dark/system theme switch. -->
<template>
  <span class="app-theme-toggle">
    <el-tooltip :content="themeTooltip" placement="bottom">
      <el-button
        class="app-theme-toggle-button"
        :aria-label="themeTooltip"
        :icon="themeIcon"
        circle
        @click="cycleThemeMode"
      />
    </el-tooltip>
  </span>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, type Component } from "vue";
import { Moon, Monitor, Sunny } from "@element-plus/icons-vue";

type ThemeMode = "system" | "light" | "dark";

const THEME_STORAGE_KEY = "md2word.theme.mode";
const themeMode = ref<ThemeMode>(getStoredThemeMode());
const themeOrder: ThemeMode[] = ["system", "dark", "light"];
const themeLabels: Record<ThemeMode, string> = {
  system: "跟随系统主题",
  dark: "深色模式",
  light: "浅色模式",
};

const themeIcon = computed<Component>(() => {
  if (themeMode.value === "dark") {
    return Moon;
  }
  if (themeMode.value === "light") {
    return Sunny;
  }
  return Monitor;
});
const themeTooltip = computed(() => `当前：${themeLabels[themeMode.value]}。点击切换主题。`);

onMounted(() => {
  applyThemeMode(themeMode.value);
});

function cycleThemeMode(): void {
  const currentIndex = themeOrder.indexOf(themeMode.value);
  const nextMode = themeOrder[(currentIndex + 1) % themeOrder.length] || "system";
  themeMode.value = nextMode;
  persistThemeMode(nextMode);
}

function getStoredThemeMode(): ThemeMode {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }
  return "system";
}

function persistThemeMode(mode: ThemeMode): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  applyThemeMode(mode);
}

function applyThemeMode(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.dataset.theme = mode;
  }
  root.dataset.themeMode = mode;
}
</script>

<style scoped lang="scss">
.app-theme-toggle {
  display: inline-flex;
}

.app-theme-toggle-button {
  flex: 0 0 auto;
  border-color: var(--app-color-border-soft);
  background: var(--app-color-glass);
  color: var(--app-color-primary-hover);
  box-shadow: var(--app-shadow-subtle);
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out,
    color var(--app-motion-fast) ease-out,
    transform var(--app-motion-fast) ease-out;
}

.app-theme-toggle-button:hover,
.app-theme-toggle-button:focus-visible {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  box-shadow: var(--app-shadow-focus);
  transform: translateY(-1px);
}
</style>
