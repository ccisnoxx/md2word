import { computed } from "vue";
import { describe, expect, it, vi } from "vitest";

import { savedViewsApi } from "@/api/savedViews";
import { useWorkbenchSavedViews } from "./useWorkbenchSavedViews";

vi.mock("@/api/savedViews", () => ({ savedViewsApi: { reorder: vi.fn() } }));

function view(id: string, position: number) {
  return { view_id: id, position, name: id } as never;
}

function stripItem(id: string, source: "personal" | "system" = "personal") {
  return { id, source, name: id } as never;
}

describe("useWorkbenchSavedViews 排序", () => {
  it("按 position 排序后与相邻视图交换，并以后端返回结果为准", async () => {
    const reorder = vi.mocked(savedViewsApi.reorder).mockResolvedValue({ items: [view("b", 0), view("a", 1)] } as never);
    const store = useWorkbenchSavedViews("incidents", computed(() => ({ filters: {}, sort: "priority" })), vi.fn());
    store.savedViews.value = [view("c", 2), view("a", 0), view("b", 1)];
    await store.moveSavedView(stripItem("b"), "left");
    expect(reorder).toHaveBeenCalledWith({ page_key: "incidents", view_ids: ["b", "a", "c"] });
    expect(store.savedViews.value).toEqual([view("b", 0), view("a", 1)]);
    expect(store.savedViewsLoading.value).toBe(false);
  });

  it("越界移动、系统视图和未知视图不发请求", async () => {
    const reorder = vi.mocked(savedViewsApi.reorder).mockClear();
    const store = useWorkbenchSavedViews("jobs", computed(() => ({ filters: {}, sort: "created_at_desc" })), vi.fn());
    store.savedViews.value = [view("a", 0), view("b", 1)];
    await store.moveSavedView(stripItem("a"), "left");
    await store.moveSavedView(stripItem("b"), "right");
    await store.moveSavedView(stripItem("a", "system"), "right");
    await store.moveSavedView(stripItem("missing"), "right");
    expect(reorder).not.toHaveBeenCalled();
  });

  it("排序失败交给页面错误处理并结束加载态", async () => {
    const failure = new Error("reorder failed");
    vi.mocked(savedViewsApi.reorder).mockRejectedValue(failure);
    const onError = vi.fn();
    const store = useWorkbenchSavedViews("jobs", computed(() => ({ filters: {}, sort: "created_at_desc" })), onError);
    store.savedViews.value = [view("a", 0), view("b", 1)];
    await store.moveSavedView(stripItem("a"), "right");
    expect(onError).toHaveBeenCalledWith(failure);
    expect(store.savedViewsLoading.value).toBe(false);
  });
});
