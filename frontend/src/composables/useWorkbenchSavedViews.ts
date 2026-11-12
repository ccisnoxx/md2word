// 工作台列表页（任务列表、异常处理）共用的个人保存视图 CRUD。
// 应用视图与路由同步仍由各页面的列表 composable 负责，这里只管理视图列表本身。
import { ref, type ComputedRef } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { savedViewsApi } from "@/api/savedViews";
import type { SavedViewPageKey, SavedViewResponse } from "@/api/types";
import type { SavedViewState, SavedViewStripItem } from "@/utils/savedViews";

export function useWorkbenchSavedViews(
  pageKey: SavedViewPageKey,
  currentState: ComputedRef<SavedViewState>,
  onError: (caught: unknown) => void,
) {
  const savedViews = ref<SavedViewResponse[]>([]);
  const savedViewsLoading = ref(false);

  function isCancel(caught: unknown): boolean {
    return caught === "cancel" || caught === "close";
  }

  async function loadSavedViews(): Promise<void> {
    savedViewsLoading.value = true;
    try {
      const response = await savedViewsApi.list(pageKey);
      savedViews.value = response.items;
    } catch (caught) {
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  async function promptSavedViewName(title: string, inputValue = ""): Promise<string | null> {
    try {
      const result = await ElMessageBox.prompt("名称仅用于当前页面的个人视图。", title, {
        inputValue,
        inputPlaceholder: "视图名称",
        confirmButtonText: "保存",
        cancelButtonText: "取消",
        inputValidator(value) {
          const normalized = value.trim();
          if (!normalized) {
            return "视图名称不能为空。";
          }
          if (normalized.length > 64) {
            return "视图名称最多 64 个字符。";
          }
          return true;
        },
      });
      return result.value.trim();
    } catch (caught) {
      if (isCancel(caught)) {
        return null;
      }
      throw caught;
    }
  }

  async function saveCurrentSavedView(): Promise<void> {
    const name = await promptSavedViewName("保存当前视图");
    if (!name) {
      return;
    }
    savedViewsLoading.value = true;
    try {
      await savedViewsApi.create({
        page_key: pageKey,
        name,
        filters: currentState.value.filters,
        sort: currentState.value.sort,
      });
      await loadSavedViews();
      ElMessage.success("视图已保存。");
    } catch (caught) {
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  async function updateSavedViewFromCurrent(view: SavedViewStripItem): Promise<void> {
    if (view.source !== "personal") {
      return;
    }
    try {
      await ElMessageBox.confirm(`将用当前筛选和排序覆盖“${view.name}”。`, "更新保存视图", {
        confirmButtonText: "确认更新",
        cancelButtonText: "返回",
        type: "warning",
      });
      savedViewsLoading.value = true;
      await savedViewsApi.update(view.id, {
        filters: currentState.value.filters,
        sort: currentState.value.sort,
      });
      await loadSavedViews();
      ElMessage.success("视图已更新。");
    } catch (caught) {
      if (isCancel(caught)) {
        return;
      }
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  async function renameSavedView(view: SavedViewStripItem): Promise<void> {
    if (view.source !== "personal") {
      return;
    }
    const name = await promptSavedViewName("重命名保存视图", view.name);
    if (!name || name === view.name) {
      return;
    }
    savedViewsLoading.value = true;
    try {
      await savedViewsApi.update(view.id, { name });
      await loadSavedViews();
      ElMessage.success("视图已重命名。");
    } catch (caught) {
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  async function deleteSavedView(view: SavedViewStripItem): Promise<void> {
    if (view.source !== "personal") {
      return;
    }
    try {
      await ElMessageBox.confirm(`删除后无法从该页面恢复“${view.name}”。`, "删除保存视图", {
        confirmButtonText: "确认删除",
        cancelButtonText: "返回",
        type: "warning",
      });
      savedViewsLoading.value = true;
      await savedViewsApi.delete(view.id);
      await loadSavedViews();
      ElMessage.success("视图已删除。");
    } catch (caught) {
      if (isCancel(caught)) {
        return;
      }
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  async function setDefaultSavedView(view: SavedViewStripItem): Promise<void> {
    if (view.source !== "personal") {
      return;
    }
    savedViewsLoading.value = true;
    try {
      await savedViewsApi.update(view.id, { is_default: true });
      await loadSavedViews();
      ElMessage.success("默认视图已更新。");
    } catch (caught) {
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  // 只在相邻个人视图之间交换位置；越界移动直接忽略，不发请求。
  async function moveSavedView(view: SavedViewStripItem, direction: "left" | "right"): Promise<void> {
    if (view.source !== "personal") {
      return;
    }
    const ordered = [...savedViews.value].sort((left, right) => left.position - right.position);
    const index = ordered.findIndex((item) => item.view_id === view.id);
    const nextIndex = direction === "left" ? index - 1 : index + 1;
    if (index < 0 || nextIndex < 0 || nextIndex >= ordered.length) {
      return;
    }
    [ordered[index], ordered[nextIndex]] = [ordered[nextIndex], ordered[index]];
    savedViewsLoading.value = true;
    try {
      const response = await savedViewsApi.reorder({
        page_key: pageKey,
        view_ids: ordered.map((item) => item.view_id),
      });
      savedViews.value = response.items;
    } catch (caught) {
      onError(caught);
    } finally {
      savedViewsLoading.value = false;
    }
  }

  return {
    savedViews,
    savedViewsLoading,
    loadSavedViews,
    saveCurrentSavedView,
    updateSavedViewFromCurrent,
    renameSavedView,
    deleteSavedView,
    setDefaultSavedView,
    moveSavedView,
  };
}
