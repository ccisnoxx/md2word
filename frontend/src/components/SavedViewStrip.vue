<!-- File: frontend/src/components/SavedViewStrip.vue -->
<!-- Purpose: Render compact system presets and personal saved-view actions for operations workbenches. -->
<template>
  <section class="saved-view-strip" aria-label="Saved views">
    <div class="saved-view-group">
      <button
        v-for="view in systemViews"
        :key="view.id"
        type="button"
        class="saved-view-chip is-system"
        :class="{ 'is-active': activeViewId === view.id }"
        @click="$emit('apply', view)"
      >
        <span>{{ view.name }}</span>
      </button>
    </div>

    <div v-if="personalViews.length" class="saved-view-group is-personal">
      <div
        v-for="view in personalViews"
        :key="view.id"
        class="saved-view-personal"
        :class="{ 'is-active': activeViewId === view.id }"
      >
        <button type="button" class="saved-view-chip is-personal-chip" @click="$emit('apply', view)">
          <StarFilled v-if="view.is_default" class="default-icon" aria-hidden="true" />
          <span>{{ view.name }}</span>
        </button>
        <el-dropdown trigger="click" @command="handleCommand(view, $event)">
          <button type="button" class="saved-view-menu-button" :aria-label="`${view.name} actions`">
            <MoreFilled aria-hidden="true" />
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="apply">应用</el-dropdown-item>
              <el-dropdown-item command="update">用当前筛选更新</el-dropdown-item>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="default">设为默认</el-dropdown-item>
              <el-dropdown-item command="move-left" :disabled="view.position === 0">左移</el-dropdown-item>
              <el-dropdown-item command="move-right" :disabled="view.position === personalViews.length - 1">右移</el-dropdown-item>
              <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-button class="saved-view-save" size="small" :icon="Plus" :loading="loading" @click="$emit('save-current')">
      保存当前视图
    </el-button>
  </section>
</template>

<script setup lang="ts">
import { MoreFilled, Plus, StarFilled } from "@element-plus/icons-vue";

import type { SavedViewStripItem } from "@/utils/savedViews";

type SavedViewCommand = "apply" | "update" | "rename" | "delete" | "default" | "move-left" | "move-right";

defineProps<{
  systemViews: SavedViewStripItem[];
  personalViews: SavedViewStripItem[];
  activeViewId: string | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  apply: [view: SavedViewStripItem];
  "save-current": [];
  update: [view: SavedViewStripItem];
  rename: [view: SavedViewStripItem];
  delete: [view: SavedViewStripItem];
  "set-default": [view: SavedViewStripItem];
  move: [view: SavedViewStripItem, direction: "left" | "right"];
}>();

function isSavedViewCommand(command: unknown): command is SavedViewCommand {
  return (
    command === "apply" ||
    command === "update" ||
    command === "rename" ||
    command === "delete" ||
    command === "default" ||
    command === "move-left" ||
    command === "move-right"
  );
}

function handleCommand(view: SavedViewStripItem, command: unknown): void {
  if (!isSavedViewCommand(command)) {
    return;
  }
  if (command === "apply") {
    emit("apply", view);
  } else if (command === "update") {
    emit("update", view);
  } else if (command === "rename") {
    emit("rename", view);
  } else if (command === "delete") {
    emit("delete", view);
  } else if (command === "default") {
    emit("set-default", view);
  } else if (command === "move-left") {
    emit("move", view, "left");
  } else {
    emit("move", view, "right");
  }
}
</script>

<style scoped lang="scss">
.saved-view-strip {
  display: flex;
  align-items: center;
  gap: var(--app-space-2);
  min-height: 42px;
  overflow-x: auto;
  padding-block: 2px;
}

.saved-view-group {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: var(--app-space-2);
}

.saved-view-group.is-personal {
  padding-left: var(--app-space-2);
  border-left: 1px solid var(--app-color-border);
}

.saved-view-chip,
.saved-view-menu-button {
  border: 1px solid var(--app-color-border);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    color 0.18s ease;
}

.saved-view-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  max-width: 190px;
  padding: 0 10px;
  border-radius: 8px;
  white-space: nowrap;
}

.saved-view-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.saved-view-personal {
  display: inline-flex;
  align-items: stretch;
  flex: 0 0 auto;
}

.saved-view-personal .saved-view-chip {
  border-radius: 8px 0 0 8px;
}

.saved-view-menu-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  border-left: 0;
  border-radius: 0 8px 8px 0;
}

.saved-view-chip:hover,
.saved-view-menu-button:hover,
.saved-view-personal.is-active .saved-view-chip,
.saved-view-personal.is-active .saved-view-menu-button,
.saved-view-chip.is-active {
  border-color: var(--app-color-primary);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary);
}

.default-icon {
  width: 13px;
  height: 13px;
  color: var(--app-color-warning);
}

.saved-view-save {
  flex: 0 0 auto;
}

@media (max-width: 720px) {
  .saved-view-strip {
    align-items: flex-start;
  }

  .saved-view-chip {
    max-width: 150px;
  }
}
</style>
