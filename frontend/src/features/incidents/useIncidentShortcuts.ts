// 异常页的手动刷新与键盘快捷键：横跨队列、诊断抽屉和处置动作三个 owner，只做编排不持有业务状态。
import { onBeforeUnmount, onMounted } from "vue";

import type { ShortcutHint } from "@/utils/keyboardShortcuts";
import { shouldIgnoreIncidentShortcut } from "@/utils/incidents";
import type { IncidentActions } from "./useIncidentActions";
import type { IncidentDiagnostic } from "./useIncidentDiagnostic";
import type { IncidentQueue } from "./useIncidentQueue";

export const incidentListShortcutHints: ShortcutHint[] = [
  { keys: ["R"], label: "刷新" },
  { keys: ["Esc"], label: "关闭抽屉" },
  { keys: ["J/K"], label: "移动" },
  { keys: ["Cmd/Ctrl", "Enter"], label: "安全动作" },
];
export const incidentDrawerShortcutHints: ShortcutHint[] = [
  { keys: ["Esc"], label: "关闭" },
  { keys: ["Cmd/Ctrl", "Enter"], label: "安全重试" },
  { keys: ["J/K"], label: "上一条/下一条" },
];

export function useIncidentShortcuts(
  queue: Pick<IncidentQueue, "loadIncidents">,
  diagnostic: Pick<
    IncidentDiagnostic,
    "drawerVisible" | "drawerLoading" | "diagnostic" | "selectedIncidentJobId" | "loadDiagnostics" | "closeDiagnostic" | "selectAdjacentIncident"
  >,
  actions: Pick<IncidentActions, "batchLoading" | "handleSingleRetry">,
) {
  async function manualRefresh(): Promise<void> {
    await queue.loadIncidents();
    if (diagnostic.drawerVisible.value && diagnostic.selectedIncidentJobId.value) {
      await diagnostic.loadDiagnostics(diagnostic.selectedIncidentJobId.value);
    }
  }

  function handleIncidentKeydown(event: KeyboardEvent): void {
    if (shouldIgnoreIncidentShortcut(event.target)) {
      return;
    }
    if (event.key === "Escape" && diagnostic.drawerVisible.value) {
      event.preventDefault();
      void diagnostic.closeDiagnostic();
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      const current = diagnostic.diagnostic.value;
      if (current?.item.retryable && !diagnostic.drawerLoading.value && !actions.batchLoading.value) {
        event.preventDefault();
        void actions.handleSingleRetry(current.item);
      }
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "r") {
      event.preventDefault();
      void manualRefresh();
    } else if (key === "j") {
      event.preventDefault();
      diagnostic.selectAdjacentIncident(1);
    } else if (key === "k") {
      event.preventDefault();
      diagnostic.selectAdjacentIncident(-1);
    }
  }

  onMounted(() => {
    window.addEventListener("keydown", handleIncidentKeydown);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", handleIncidentKeydown);
  });

  return { manualRefresh };
}
