<!-- File: frontend/src/components/OperatorCommandPalette.vue -->
<!-- Purpose: Protected-app command palette for permission-filtered page and saved-view navigation. -->
<template>
  <Teleport to="body">
    <div v-if="open" class="command-palette-overlay" @mousedown.self="closePalette(true)">
      <section
        class="command-palette-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="operator-command-palette-title"
        @keydown="handlePanelKeydown"
      >
        <header class="command-palette-header">
          <div>
            <p class="page-kicker">快速命令</p>
            <h2 id="operator-command-palette-title">命令面板</h2>
          </div>
          <ShortcutHintList :items="paletteHints" />
        </header>

        <div class="command-search-row">
          <el-icon aria-hidden="true"><Search /></el-icon>
          <input
            ref="searchInput"
            v-model="query"
            type="search"
            aria-label="搜索页面、视图或操作"
            aria-controls="operator-command-list"
            :aria-activedescendant="activeCommandId"
            placeholder="搜索页面、视图或操作"
            @keydown.down.prevent="moveActive(1)"
            @keydown.up.prevent="moveActive(-1)"
            @keydown.enter.prevent="selectActiveCommand"
            @keydown.esc.prevent="closePalette(true)"
          />
        </div>

        <div v-if="loading" class="command-state" aria-live="polite">保存视图加载中...</div>
        <div v-if="loadErrorText" class="command-state is-warning" aria-live="polite">{{ loadErrorText }}</div>

        <div
          v-if="groupedCommands.length"
          id="operator-command-list"
          class="command-list"
          role="listbox"
          aria-label="命令列表"
        >
          <section v-for="group in groupedCommands" :key="group.id" class="command-group" :aria-label="group.label">
            <h3>{{ group.label }}</h3>
            <button
              v-for="command in group.commands"
              :id="commandElementId(command.id)"
              :key="command.id"
              type="button"
              class="command-item"
              :class="{ 'is-active': command.id === activeCommand?.id }"
              role="option"
              :aria-selected="command.id === activeCommand?.id"
              @mouseenter="setActiveCommand(command.id)"
              @click="selectCommand(command)"
            >
              <span>
                <strong>{{ command.title }}</strong>
                <small>{{ command.description }}</small>
              </span>
              <span class="command-enter">回车</span>
            </button>
          </section>
        </div>
        <div v-else class="command-empty" aria-live="polite">
          <strong>没有可用命令</strong>
          <span>{{ query ? "换个关键词试试。" : "当前账号暂无可跳转的页面或保存视图。" }}</span>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Search } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { savedViewsApi } from "@/api/savedViews";
import type { SavedViewPageKey, SavedViewResponse } from "@/api/types";
import ShortcutHintList from "@/components/ShortcutHintList.vue";
import type { AppAccessContext } from "@/navigation/appShell";
import { normalizeApiError } from "@/utils/errors";
import { isCommandPaletteShortcut, type ShortcutHint } from "@/utils/keyboardShortcuts";
import {
  buildPageCommands,
  buildSavedViewCommands,
  filterOperatorCommands,
  groupOperatorCommands,
  savedViewPageKeysForAccess,
  type OperatorCommand,
} from "@/utils/operatorCommands";

const props = defineProps<{
  access: AppAccessContext;
}>();

const router = useRouter();
const open = ref(false);
const query = ref("");
const activeIndex = ref(0);
const searchInput = ref<HTMLInputElement | null>(null);
const savedViewsByPage = ref<Partial<Record<SavedViewPageKey, SavedViewResponse[]>>>({});
const loadErrors = ref<Partial<Record<SavedViewPageKey, string>>>({});
const loading = ref(false);
const loadedKey = ref("");
let lastFocusedElement: HTMLElement | null = null;

const paletteHints: ShortcutHint[] = [
  { keys: ["Cmd/Ctrl", "K"], label: "打开" },
  { keys: ["Esc"], label: "关闭" },
  { keys: ["↑/↓"], label: "选择" },
];

const flatCommands = computed(() => [
  ...buildPageCommands(props.access),
  ...buildSavedViewCommands(props.access, savedViewsByPage.value),
]);
const filteredCommands = computed(() => filterOperatorCommands(flatCommands.value, query.value));
const groupedCommands = computed(() => groupOperatorCommands(filteredCommands.value));
const activeCommand = computed(() => filteredCommands.value[activeIndex.value] ?? null);
const activeCommandId = computed(() => (activeCommand.value ? commandElementId(activeCommand.value.id) : undefined));
const loadErrorText = computed(() => {
  const count = Object.keys(loadErrors.value).length;
  return count ? `${count} 组保存视图加载失败，页面入口仍可使用。` : "";
});

watch(filteredCommands, () => {
  activeIndex.value = filteredCommands.value.length ? Math.min(activeIndex.value, filteredCommands.value.length - 1) : 0;
});

watch(
  () => savedViewPageKeysForAccess(props.access).join(","),
  () => {
    loadedKey.value = "";
    savedViewsByPage.value = {};
    loadErrors.value = {};
    if (open.value) {
      void loadSavedViews();
    }
  },
);

onMounted(() => {
  window.addEventListener("keydown", handleGlobalKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleGlobalKeydown);
});

function show(): void {
  openPalette();
}

function openPalette(): void {
  if (!open.value) {
    lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  open.value = true;
  query.value = "";
  activeIndex.value = 0;
  void loadSavedViews();
  void nextTick(() => searchInput.value?.focus());
}

function closePalette(restoreFocus = false): void {
  open.value = false;
  query.value = "";
  if (restoreFocus) {
    void nextTick(() => lastFocusedElement?.focus());
  }
}

function handleGlobalKeydown(event: KeyboardEvent): void {
  if (!isCommandPaletteShortcut(event)) {
    return;
  }
  event.preventDefault();
  openPalette();
}

function handlePanelKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    closePalette(true);
  }
}

async function loadSavedViews(): Promise<void> {
  const pageKeys = savedViewPageKeysForAccess(props.access);
  const nextLoadedKey = pageKeys.join(",");
  if (!pageKeys.length || loading.value || (loadedKey.value === nextLoadedKey && !Object.keys(loadErrors.value).length)) {
    return;
  }
  loading.value = true;
  const nextErrors: Partial<Record<SavedViewPageKey, string>> = {};
  await Promise.all(
    pageKeys.map(async (pageKey) => {
      try {
        const response = await savedViewsApi.list(pageKey);
        savedViewsByPage.value = {
          ...savedViewsByPage.value,
          [pageKey]: response.items,
        };
      } catch (caught) {
        nextErrors[pageKey] = normalizeApiError(caught).message;
        savedViewsByPage.value = {
          ...savedViewsByPage.value,
          [pageKey]: [],
        };
      }
    }),
  );
  loadErrors.value = nextErrors;
  loadedKey.value = nextLoadedKey;
  loading.value = false;
}

function moveActive(delta: number): void {
  if (!filteredCommands.value.length) {
    return;
  }
  activeIndex.value = (activeIndex.value + delta + filteredCommands.value.length) % filteredCommands.value.length;
}

function setActiveCommand(commandId: string): void {
  const index = filteredCommands.value.findIndex((command) => command.id === commandId);
  if (index >= 0) {
    activeIndex.value = index;
  }
}

function selectActiveCommand(): void {
  if (activeCommand.value) {
    selectCommand(activeCommand.value);
  }
}

function selectCommand(command: OperatorCommand): void {
  closePalette(false);
  void router.push(command.to);
}

function commandElementId(commandId: string): string {
  return `operator-command-${commandId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

defineExpose({ show });
</script>

<style scoped lang="scss">
.command-palette-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  align-items: start;
  justify-items: center;
  padding: min(9vh, 72px) var(--app-space-4) var(--app-space-4);
  background: var(--app-color-overlay);
}

.command-palette-panel {
  display: grid;
  gap: var(--app-space-3);
  width: min(720px, 100%);
  max-height: min(680px, calc(100vh - 48px));
  min-width: 0;
  overflow: hidden;
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-elevated);
  color: var(--app-color-text);
  box-shadow: var(--app-shadow-panel);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
}

.command-palette-header {
  display: flex;
  justify-content: space-between;
  gap: var(--app-space-3);
  align-items: flex-start;
}

.command-palette-header h2,
.command-palette-header p {
  margin: 0;
}

.command-palette-header h2 {
  font-size: 20px;
}

.command-search-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--app-space-2);
  align-items: center;
  min-height: 44px;
  padding: 0 var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.command-search-row:focus-within {
  border-color: var(--app-color-primary);
  box-shadow: var(--app-shadow-focus);
}

.command-search-row input {
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--app-color-text);
  font: inherit;
}

.command-state,
.command-empty {
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.command-state.is-warning {
  border-color: var(--app-color-warning-border);
  background: var(--app-color-warning-soft);
}

.command-empty {
  display: grid;
  gap: 4px;
  min-height: 120px;
  place-content: center;
  text-align: center;
}

.command-list {
  overflow: auto;
  display: grid;
  gap: var(--app-space-3);
  padding-right: 2px;
}

.command-group {
  display: grid;
  gap: var(--app-space-2);
}

.command-group h3 {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.command-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
  width: 100%;
  min-width: 0;
  min-height: 48px;
  padding: 8px 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
}

.command-item:hover,
.command-item:focus-visible,
.command-item.is-active {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft);
  box-shadow: var(--app-shadow-focus);
}

.command-item > span:first-child {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.command-item strong,
.command-item small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.command-item small,
.command-enter {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.command-enter {
  flex: 0 0 auto;
  padding: 2px 6px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
  font-family: var(--app-font-mono);
}

@media (max-width: 640px) {
  .command-palette-overlay {
    padding: var(--app-space-3);
  }

  .command-palette-panel {
    max-height: calc(100vh - 24px);
    padding: var(--app-space-3);
  }

  .command-palette-header {
    display: grid;
  }
}
</style>
