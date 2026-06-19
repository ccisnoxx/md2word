<!-- frontend/src/components/AppBreadcrumb.vue: Topbar route breadcrumb for workbench hierarchy. -->
<template>
  <el-breadcrumb v-if="displayItems.length" separator="/" class="app-breadcrumb">
    <el-breadcrumb-item v-for="item in displayItems" :key="item.label" :to="item.to">
      {{ item.label }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import { getBreadcrumbItems, type AppAccessContext, type AppBreadcrumbItem } from "@/navigation/appShell";
import { useAuthStore } from "@/stores/auth";

const props = defineProps<{
  items?: AppBreadcrumbItem[];
}>();

const route = useRoute();
const auth = useAuthStore();

const access = computed<AppAccessContext>(() => ({
  role: auth.user?.role ?? null,
  roles: auth.user?.roles ?? [],
  permissions: auth.user?.permissions ?? [],
}));

const fallbackItems = computed<AppBreadcrumbItem[]>(() => getBreadcrumbItems(route, access.value));
const displayItems = computed<AppBreadcrumbItem[]>(() => props.items ?? fallbackItems.value);
</script>

<style scoped lang="scss">
.app-breadcrumb {
  font-size: 13px;
}
</style>
