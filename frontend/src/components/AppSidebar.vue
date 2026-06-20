<!-- frontend/src/components/AppSidebar.vue: Workflow-based app shell sidebar navigation. -->
<template>
  <div class="app-sidebar" :class="{ 'is-collapsed': isCompact, 'is-mobile': mobile }">
    <div class="sidebar-brand-row">
      <router-link class="sidebar-brand" :to="brandTo" :aria-label="brandAriaLabel" @click="emitNavigate">
        <span class="sidebar-brand-mark" aria-hidden="true">
          <el-icon><DocumentChecked /></el-icon>
        </span>
        <span v-if="!isCompact" class="sidebar-brand-copy">
          <strong>md2word</strong>
          <small>运营工作台</small>
        </span>
      </router-link>

      <el-tooltip v-if="!mobile" :content="collapseLabel" placement="right">
        <el-button class="sidebar-collapse-button" :aria-label="collapseLabel" :icon="collapseIcon" circle @click="emitToggleCollapse" />
      </el-tooltip>
    </div>

    <nav class="sidebar-nav" aria-label="工作流导航">
      <section
        v-for="group in groups"
        :key="group.id"
        class="sidebar-group"
        :class="{ 'is-active': group.id === activeGroupId }"
      >
        <button
          v-if="!isCompact"
          class="sidebar-group-button"
          type="button"
          :aria-expanded="isGroupOpen(group.id)"
          @click="toggleGroup(group.id)"
        >
          <span class="sidebar-group-title">
            <el-icon aria-hidden="true"><component :is="group.icon" /></el-icon>
            <span>{{ group.label }}</span>
          </span>
          <el-icon class="sidebar-group-arrow" aria-hidden="true">
            <ArrowDown v-if="isGroupOpen(group.id)" />
            <ArrowRight v-else />
          </el-icon>
        </button>

        <el-tooltip v-else :content="group.label" placement="right">
          <div class="sidebar-group-compact" :aria-label="group.label">
            <el-icon aria-hidden="true"><component :is="group.icon" /></el-icon>
          </div>
        </el-tooltip>

        <div v-show="isGroupOpen(group.id)" class="sidebar-items">
          <template v-for="item in group.items" :key="item.id">
            <el-tooltip v-if="isCompact" :content="item.label" placement="right">
              <router-link
                class="sidebar-link"
                :class="[`is-tone-${item.tone || 'default'}`, { 'is-active': item.id === activeItemId }]"
                :to="item.to"
                :aria-label="item.label"
                :aria-current="item.id === activeItemId ? 'page' : undefined"
                @click="emitNavigate"
              >
                <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
                <span v-if="item.badge" class="sidebar-link-badge-dot" aria-hidden="true"></span>
              </router-link>
            </el-tooltip>

            <router-link
              v-else
              class="sidebar-link"
              :class="[`is-tone-${item.tone || 'default'}`, { 'is-active': item.id === activeItemId }]"
              :to="item.to"
              :aria-current="item.id === activeItemId ? 'page' : undefined"
              @click="emitNavigate"
            >
              <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
              <span class="sidebar-link-label">{{ item.label }}</span>
              <span v-if="item.badge" class="sidebar-link-badge" :class="`is-tone-${item.tone || 'default'}`">{{ item.badge }}</span>
            </router-link>
          </template>
        </div>
      </section>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ArrowDown, ArrowRight, DocumentChecked, Expand, Fold } from "@element-plus/icons-vue";
import type { RouteLocationRaw } from "vue-router";

import type { AppNavGroup, AppNavGroupId, AppNavItemId } from "@/navigation/appShell";

const props = withDefaults(
  defineProps<{
    groups: AppNavGroup[];
    activeGroupId?: AppNavGroupId | null;
    activeItemId?: AppNavItemId | null;
    brandTo?: RouteLocationRaw;
    collapsed?: boolean;
    mobile?: boolean;
  }>(),
  {
    activeGroupId: null,
    activeItemId: null,
    brandTo: "/cockpit",
    collapsed: false,
    mobile: false,
  },
);

const emit = defineEmits<{
  navigate: [];
  toggleCollapse: [];
}>();

const openGroupIds = ref<Set<AppNavGroupId>>(new Set());

const isCompact = computed(() => props.collapsed && !props.mobile);
const collapseLabel = computed(() => (props.collapsed ? "展开侧边栏" : "收起侧边栏"));
const collapseIcon = computed(() => (props.collapsed ? Expand : Fold));
const brandAriaLabel = computed(() => (isCompact.value ? "md2word 工作台" : "md2word 运营工作台"));
const groupIdsKey = computed(() => props.groups.map((group) => group.id).join("|"));

watch(
  groupIdsKey,
  () => {
    openGroupIds.value = new Set(props.groups.map((group) => group.id));
  },
  { immediate: true },
);

watch(
  () => props.activeGroupId,
  (groupId) => {
    if (!groupId) {
      return;
    }
    const next = new Set(openGroupIds.value);
    next.add(groupId);
    openGroupIds.value = next;
  },
);

function isGroupOpen(groupId: AppNavGroupId): boolean {
  return isCompact.value || openGroupIds.value.has(groupId);
}

function toggleGroup(groupId: AppNavGroupId): void {
  const next = new Set(openGroupIds.value);
  if (next.has(groupId)) {
    next.delete(groupId);
  } else {
    next.add(groupId);
  }
  openGroupIds.value = next;
}

function emitNavigate(): void {
  emit("navigate");
}

function emitToggleCollapse(): void {
  emit("toggleCollapse");
}
</script>

<style scoped lang="scss">
.app-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: var(--app-space-5);
  height: 100%;
  min-height: 100vh;
  padding: var(--app-space-4) var(--app-space-3);
  background:
    linear-gradient(180deg, color-mix(in srgb, #111827 88%, var(--app-color-primary)), #0f172a),
    #0f172a;
  color: #e5e7eb;
}

.app-sidebar.is-mobile {
  min-height: 100%;
  padding: var(--app-space-4);
}

.sidebar-brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-2);
  min-width: 0;
}

.sidebar-brand {
  display: inline-flex;
  align-items: center;
  gap: var(--app-space-3);
  min-width: 0;
  color: #ffffff;
}

.sidebar-brand:hover,
.sidebar-brand:focus-visible {
  color: #ffffff;
}

.sidebar-brand-mark {
  display: inline-grid;
  flex: 0 0 auto;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid rgba(167, 243, 208, 0.34);
  border-radius: var(--app-radius-md);
  background: color-mix(in srgb, var(--app-color-primary) 76%, #0f172a);
  color: #ffffff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.34);
  font-size: 18px;
}

.sidebar-brand-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.sidebar-brand-copy strong,
.sidebar-brand-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-brand-copy strong {
  font-size: 17px;
  line-height: 1.1;
}

.sidebar-brand-copy small {
  color: #a7b1c4;
  font-size: 12px;
  line-height: 1.2;
}

.sidebar-collapse-button {
  flex: 0 0 auto;
  border-color: rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.5);
  color: #dbeafe;
}

.sidebar-nav {
  overflow-y: auto;
  display: grid;
  align-content: start;
  gap: var(--app-space-3);
  min-width: 0;
  padding-right: 2px;
}

.sidebar-group {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.sidebar-group-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-2);
  width: 100%;
  min-height: 32px;
  padding: 0 var(--app-space-2);
  border: 0;
  border-radius: var(--app-radius-sm);
  background: transparent;
  color: #a7b1c4;
  font: inherit;
  font-size: 12px;
  font-weight: 760;
  letter-spacing: 0;
  text-align: left;
}

.sidebar-group-button:hover,
.sidebar-group-button:focus-visible,
.sidebar-group.is-active .sidebar-group-button {
  background: rgba(99, 102, 241, 0.18);
  color: #ffffff;
}

.sidebar-group-title {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  gap: 7px;
}

.sidebar-group-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-group-arrow {
  flex: 0 0 auto;
  font-size: 13px;
}

.sidebar-group-compact {
  display: grid;
  width: 100%;
  height: 28px;
  place-items: center;
  border-radius: var(--app-radius-sm);
  color: #94a3b8;
}

.sidebar-group.is-active .sidebar-group-compact {
  background: rgba(99, 102, 241, 0.18);
  color: #ffffff;
}

.sidebar-items {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.sidebar-link {
  position: relative;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--app-space-2);
  min-height: 38px;
  padding: 0 var(--app-space-3);
  border: 1px solid transparent;
  border-radius: var(--app-radius-md);
  color: #d1d5db;
  font-size: 14px;
  font-weight: 650;
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    color var(--app-motion-fast) ease-out;
}

.sidebar-link:hover,
.sidebar-link:focus-visible {
  border-color: rgba(199, 210, 254, 0.28);
  background: rgba(99, 102, 241, 0.16);
  color: #ffffff;
}

.sidebar-link.is-active {
  border-color: rgba(167, 243, 208, 0.38);
  background:
    linear-gradient(90deg, rgba(99, 102, 241, 0.36), rgba(16, 185, 129, 0.18)),
    rgba(15, 23, 42, 0.6);
  color: #ffffff;
}

.sidebar-link.is-active::before {
  position: absolute;
  inset: 8px auto 8px 0;
  width: 3px;
  border-radius: 0 var(--app-radius-pill) var(--app-radius-pill) 0;
  content: "";
  background: var(--app-color-accent-emerald);
}

.sidebar-link-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-link-badge {
  min-width: 20px;
  padding: 2px 6px;
  border-radius: var(--app-radius-pill);
  background: rgba(148, 163, 184, 0.2);
  color: #e5e7eb;
  font-size: 11px;
  font-weight: 760;
}

.sidebar-link-badge-dot {
  position: absolute;
  top: 9px;
  right: 10px;
  width: 7px;
  height: 7px;
  border-radius: var(--app-radius-pill);
  background: var(--app-color-accent-emerald);
}

.app-sidebar.is-collapsed {
  gap: var(--app-space-4);
  padding: var(--app-space-4) 10px;
}

.app-sidebar.is-collapsed .sidebar-brand-row {
  display: grid;
  justify-items: center;
}

.app-sidebar.is-collapsed .sidebar-brand {
  justify-content: center;
}

.app-sidebar.is-collapsed .sidebar-brand-mark {
  width: 40px;
  height: 40px;
}

.app-sidebar.is-collapsed .sidebar-collapse-button {
  width: 34px;
  height: 34px;
}

.app-sidebar.is-collapsed .sidebar-link {
  grid-template-columns: 1fr;
  justify-items: center;
  min-height: 40px;
  padding: 0;
}

.app-sidebar.is-collapsed .sidebar-link.is-active::before {
  inset: 9px auto 9px -1px;
}
</style>
