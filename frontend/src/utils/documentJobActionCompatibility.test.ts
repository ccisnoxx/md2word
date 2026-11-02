import { describe, expect, it } from "vitest";

import type { DocumentJobResponse } from "@/api/types";
import {
  documentJobActionDisabledReason,
  documentJobActionDisabledReasons,
  isDocumentJobActionEnabled,
} from "@/utils/format";

const legacyActions: DocumentJobResponse["available_actions"] = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: "后端未开放重试。", retryable: false },
  cancel: { enabled: false, disabled_reason: "任务已完成。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: true, disabled_reason: null, retryable: false },
};

describe("任务新增动作的旧响应兼容", () => {
  it("旧响应缺少发起新代动作时保持禁用并说明缺少后端可用性", () => {
    const job = { available_actions: legacyActions } as DocumentJobResponse;

    expect(isDocumentJobActionEnabled(job, "new_generation")).toBe(false);
    expect(documentJobActionDisabledReason(job, "new_generation")).toBe("后端未返回该操作的可用性。");
    expect(documentJobActionDisabledReasons(job, "new_generation")).toEqual([
      { code: "", message: "后端未返回该操作的可用性。" },
    ]);
    expect(isDocumentJobActionEnabled(job, "download")).toBe(true);
  });

  it.each([false, true])("发起新代只消费后端 enabled=%s 并保留禁用原因", (enabled) => {
    const disabledReason = enabled ? null : "服务器拒绝发起新代。";
    const job = {
      available_actions: {
        ...legacyActions,
        new_generation: { enabled, disabled_reason: disabledReason, retryable: false },
      },
    } as DocumentJobResponse;

    expect(isDocumentJobActionEnabled(job, "new_generation")).toBe(enabled);
    expect(documentJobActionDisabledReason(job, "new_generation")).toBe(disabledReason || "");
  });
});
