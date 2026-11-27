// 文件：frontend/src/stores/workbenchBadges.ts
// 用途：以非轮询方式缓存侧边栏高频入口（异常、翻译 QA、提案审核）的待办角标计数。
import { computed, ref } from "vue";
import { defineStore, getActivePinia } from "pinia";

import type { AppNavItemId, AppNavTone } from "@/navigation/appShell";

export type WorkbenchNavBadge = {
  badge: string;
  tone: AppNavTone;
};

function formatBadgeCount(count: number | null): string | null {
  if (count === null || !Number.isFinite(count) || count <= 0) {
    return null;
  }
  return count > 99 ? "99+" : String(Math.floor(count));
}

export const useWorkbenchBadgesStore = defineStore("workbenchBadges", () => {
  const incidentsCount = ref<number | null>(null);
  const translationQaCount = ref<number | null>(null);
  const termProposalsCount = ref<number | null>(null);

  const navBadges = computed<Partial<Record<AppNavItemId, WorkbenchNavBadge>>>(() => {
    const result: Partial<Record<AppNavItemId, WorkbenchNavBadge>> = {};
    const incidentsBadge = formatBadgeCount(incidentsCount.value);
    if (incidentsBadge) {
      result.incidents = { badge: incidentsBadge, tone: "danger" };
    }
    const qaBadge = formatBadgeCount(translationQaCount.value);
    if (qaBadge) {
      result["translation-qa"] = { badge: qaBadge, tone: "warning" };
    }
    const proposalsBadge = formatBadgeCount(termProposalsCount.value);
    if (proposalsBadge) {
      result["term-proposals"] = { badge: proposalsBadge, tone: "warning" };
    }
    return result;
  });

  function setIncidentsCount(count: number | null): void {
    incidentsCount.value = count;
  }

  function setTranslationQaCount(count: number | null): void {
    translationQaCount.value = count;
  }

  function setTermProposalsCount(count: number | null): void {
    termProposalsCount.value = count;
  }

  function reset(): void {
    incidentsCount.value = null;
    translationQaCount.value = null;
    termProposalsCount.value = null;
  }

  return {
    incidentsCount,
    translationQaCount,
    termProposalsCount,
    navBadges,
    setIncidentsCount,
    setTranslationQaCount,
    setTermProposalsCount,
    reset,
  };
});

export function syncIncidentsBadgeCount(count: number | null): void {
  if (!getActivePinia()) {
    return;
  }
  useWorkbenchBadgesStore().setIncidentsCount(count);
}

export function syncTranslationQaBadgeCount(count: number | null): void {
  if (!getActivePinia()) {
    return;
  }
  useWorkbenchBadgesStore().setTranslationQaCount(count);
}

export function syncTermProposalsBadgeCount(count: number | null): void {
  if (!getActivePinia()) {
    return;
  }
  useWorkbenchBadgesStore().setTermProposalsCount(count);
}
