import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import { filesApi } from "@/api/files";
import { useRetentionCleanup } from "./useRetentionCleanup";

vi.mock("@/api/files", () => ({ filesApi: { previewRetentionDelete: vi.fn() } }));
vi.mock("element-plus", () => ({ ElMessage: { success: vi.fn(), warning: vi.fn() }, ElMessageBox: {} }));

function candidate(fileId: string) {
  return { file_id: fileId, status: "expired" } as never;
}

function setup() {
  const history = { loadCleanupRunHistory: vi.fn(), showCleanupRunHistory: vi.fn() };
  return useRetentionCleanup(ref(null), history);
}

describe("useRetentionCleanup 物理删除门禁", () => {
  it("预览的文件顺序必须与当前选择一致，且存在 deletable 项才允许打开确认框", async () => {
    const cleanup = setup();
    vi.mocked(filesApi.previewRetentionDelete).mockResolvedValue({
      action_mode: "delete_preview",
      requested_file_ids: ["f1", "f2"],
      items: [{ outcome: "deletable" }],
      totals: { deletable: 1 },
      confirmation_phrase: "DELETE EXPIRED FILES",
    } as never);
    cleanup.handleSelectionChange([candidate("f1"), candidate("f2")]);
    await cleanup.previewPhysicalDelete();
    expect(cleanup.canOpenDeleteDialog.value).toBe(true);

    cleanup.openPhysicalDeleteDialog();
    cleanup.deleteDialog.reason = "过期清理";
    cleanup.deleteDialog.confirmation = "DELETE EXPIRED FILES";
    expect(cleanup.canSubmitPhysicalDelete.value).toBe(true);

    // 选择变化会清空已有预览，避免用旧预览执行删除。
    cleanup.handleSelectionChange([candidate("f2"), candidate("f1")]);
    expect(cleanup.deleteReport.value).toBeNull();
    expect(cleanup.canOpenDeleteDialog.value).toBe(false);
    expect(cleanup.canSubmitPhysicalDelete.value).toBe(false);
  });
});
