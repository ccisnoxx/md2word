<!-- frontend/src/components/AppBreadcrumb.vue: Layout-level route breadcrumb for workbench hierarchy. -->
<template>
  <el-breadcrumb v-if="items.length" separator="/" class="app-breadcrumb">
    <el-breadcrumb-item v-for="item in items" :key="item.label" :to="item.to">
      {{ item.label }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, type RouteLocationRaw } from "vue-router";

import { useAuthStore } from "@/stores/auth";

type BreadcrumbItem = {
  label: string;
  to?: RouteLocationRaw;
};

const route = useRoute();
const auth = useAuthStore();

const jobId = computed(() => String(route.params.jobId || ""));
const templateId = computed(() => String(route.params.templateId || ""));
const translationQaReturnQuery = computed(() => {
  const query: Record<string, string> = {};
  for (const key of ["translation_qa_status", "status", "sort", "include_archived", "q", "page"]) {
    const value = route.query[key];
    if (typeof value === "string" && value.trim()) {
      query[key] = value;
    }
  }
  return query;
});
const terminologyGovernanceQuery = computed(() => {
  const query: Record<string, string> = {};
  for (const key of ["proposal_id", "source_term", "target_rule_id", "return_tab", "set_id"]) {
    const value = route.query[key];
    if (typeof value === "string" && value.trim()) {
      query[key] = value;
    }
  }
  return query;
});
const terminologyWorkbenchRoute = computed<RouteLocationRaw>(() => ({
  path: "/settings/term-rule-sets",
  query: terminologyGovernanceQuery.value,
}));

const items = computed<BreadcrumbItem[]>(() => {
  switch (route.name) {
    case "jobs":
      return [{ label: "任务工作台" }];
    case "translation-qa":
      return [{ label: "翻译 QA" }];
    case "job-detail":
      return [
        { label: "任务工作台", to: "/jobs" },
        { label: "任务详情" },
        { label: jobId.value },
      ];
    case "job-translation-qa":
      if (route.query.from === "translation-qa") {
        return [
          { label: "翻译 QA", to: { path: "/translation-qa", query: translationQaReturnQuery.value } },
          { label: jobId.value },
        ];
      }
      return [
        { label: "任务工作台", to: "/jobs" },
        { label: "任务详情", to: `/jobs/${jobId.value}` },
        { label: "翻译 QA" },
      ];
    case "settings":
      return [{ label: "配置中心" }];
    case "settings-templates":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "模板配置" },
      ];
    case "settings-template-detail":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "模板配置", to: "/settings/templates" },
        { label: templateId.value },
      ];
    case "settings-term-rule-sets":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "术语工作台", to: terminologyWorkbenchRoute.value },
        { label: "草稿与发布" },
      ];
    case "settings-term-rules":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "术语工作台", to: terminologyWorkbenchRoute.value },
        { label: "当前生效规则" },
      ];
    case "settings-translation-profiles":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "翻译配置" },
      ];
    case "settings-translation-term-sets":
      return [
        { label: "配置中心", to: "/settings" },
        { label: "翻译术语集" },
      ];
    case "term-proposals":
      return [{ label: auth.user?.role === "admin" ? "提案审核" : "术语建议" }];
    case "system-status":
      return [{ label: "系统状态" }];
    case "system-status-ops-dashboard":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "运维看板" },
      ];
    case "system-status-audit-events":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "审计日志" },
      ];
    case "system-status-file-retention":
      return [
        { label: "系统状态", to: "/system-status" },
        { label: "文件管理与清理" },
      ];
    default:
      return [];
  }
});
</script>

<style scoped lang="scss">
.app-breadcrumb {
  font-size: 13px;
}
</style>
