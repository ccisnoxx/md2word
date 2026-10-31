import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, effectScope, ref, watch, type ComputedRef, type Ref } from "vue";

import { apiRequest } from "@/api/client";
import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobActionId,
  DocumentJobResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewBlocksResponse,
  DocumentReviewSourceSpanResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  documentJobActionDisabledReason,
  documentJobModeRequiresTranslationResources,
  documentJobModeSupportsTranslationQa,
  documentReviewFlagSuggestion,
  documentReviewSourcePagesText,
  isDocumentJobActionEnabled,
  shouldShowDocumentJobAction,
} from "@/utils/format";
import JobDetailPage from "./JobDetailPage.vue";
import { deferred, executePageRequests } from "./pageRequestTestSupport";

vi.mock("@/api/client", () => ({ apiRequest: vi.fn() }));

function makeJob(overrides: Partial<DocumentJobResponse> = {}): DocumentJobResponse {
  return {
    id: "job-a", tenant_id: "tenant-a", company_id: "company-a", created_by: "user-a",
    source_file_id: "pdf-a", source_job_id: null, mode: "direct_pdf_to_word", translation_mode: "direct",
    document_language: "en", status: "succeeded", stage: "completed", progress: 100,
    quality_status: "warning", review_status: "unreviewed", delivery_status: "internal_draft", quality_summary: { count: 1 },
    template_version_id: "template-a", term_version_id: null, result_file_id: "word-a",
    mineru_raw_result_file_id: null, source_document_ir_file_id: null, document_ir_file_id: "ir-a", image_asset_file_ids: [],
    debug_full_text_enabled: false, mineru_batch_id: null, mineru_data_id: null,
    failed_stage: null, error_code: null, error_message: null, retry_count: 0,
    timeout_at: null, started_at: null, completed_at: null, canceled_at: null,
    archived_at: null, archived_by: null, deleted_at: null, deleted_by: null, delete_reason: null,
    translation_qa_status: "unreviewed", translation_qa_issue_type: null, translation_qa_note: null,
    translation_qa_reviewed_by: null, translation_qa_reviewed_at: null, request_snapshot: {},
    available_actions: {
      download: { enabled: false, retryable: false, disabled_reason: "当前结果不可下载。" },
      retry: { enabled: false, retryable: false, disabled_reason: "当前不可重试。" },
      clone: { enabled: true, retryable: false, disabled_reason: null },
      cancel: { enabled: false, retryable: false, disabled_reason: "任务已完成。" },
      archive: { enabled: true, retryable: false, disabled_reason: null },
      unarchive: { enabled: false, retryable: false, disabled_reason: "未归档。" },
      delete: { enabled: false, retryable: false, disabled_reason: "只有 admin 可以删除文档任务。" },
      publish: { enabled: false, retryable: false, eligible: true, disabled_reason: "尚未开放发布。" },
    },
    created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}

function spans(...pages: Array<number | null>): DocumentReviewSourceSpanResponse[] {
  return pages.map((source_page_index) => ({
    source_page_index, bbox: null, page_width: null, page_height: null, coordinate_unit: "mineru",
    coordinate_verified: false, reason_code: "coordinate_space_unverified", fragment_id: null,
  }));
}

function block(id: string, severity: "info" | "warning" | "blocker" = "info"): DocumentReviewBlockItemResponse {
  return {
    block_id: id, order: 0, block_type: "image", source_type: "image", excerpt: "",
    source_spans: spans(0, 20, null), table_ids: [],
    location: {
      kind: "estimated_start", preview_page_index: 77, confidence: "low", reason_code: null,
      bookmark_label: null, disposition: "rendered", representative_block_id: null,
      fallback_page_index: null, fallback_block_id: null, provenance_status: "legacy_layout",
    },
    flags: [{ code: severity === "info" ? "caption_reassociated" : "caption_binding_uncertain", severity, table_id: null }],
  };
}

function reviewResponse(target = makeJob(), overrides: Partial<DocumentReviewBlocksResponse> = {}): DocumentReviewBlocksResponse {
  const component = { availability: "available", reason_code: null } as const;
  return {
    job_id: target.id,
    source: {
      generation: target.retry_count, ir_file_id: target.document_ir_file_id, result_file_id: target.result_file_id,
      result_sha256: "sha256:word-a", file_review_source_revision: 0, receipt_sha256: "sha256:receipt-a",
    },
    content_snapshot: {
      snapshot_id: "sha256:snapshot-a", source_pdf_file_id: target.source_file_id,
      source_ir_file_id: target.document_ir_file_id, final_ir_file_id: null,
      preview_run_id: null, preview_revision: null, preview_attempt: null, basis: "final",
      source_content: component, target_content: component, translation: component,
      preview: component, mapping: component, tables: component,
    },
    availability: "available", reason_code: null, total: 1, items: [block("block-a")], next_cursor: null,
    ...overrides,
  };
}

const snapshotBindings = [
  {
    name: "direct 最终 IR", mode: "direct_pdf_to_word", translation_mode: "direct",
    source_document_ir_file_id: "source-ir-a", document_ir_file_id: "ir-a",
    snapshot: { source_ir_file_id: "ir-a", final_ir_file_id: null, basis: "final" },
  },
  {
    name: "direct 仅源 IR", mode: "direct_pdf_to_word", translation_mode: "direct",
    source_document_ir_file_id: "source-ir-a", document_ir_file_id: null,
    snapshot: { source_ir_file_id: "source-ir-a", final_ir_file_id: null, basis: "source" },
  },
  {
    name: "direct 无 IR", mode: "direct_pdf_to_word", translation_mode: "direct",
    source_document_ir_file_id: null, document_ir_file_id: null,
    snapshot: { source_ir_file_id: null, final_ir_file_id: null, basis: "none" },
  },
  {
    name: "翻译最终 IR", mode: "en2zh_pdf_to_word", translation_mode: "en2zh",
    source_document_ir_file_id: "source-ir-a", document_ir_file_id: "ir-a",
    snapshot: { source_ir_file_id: "source-ir-a", final_ir_file_id: "ir-a", basis: "final" },
  },
  {
    name: "翻译仅源 IR", mode: "en2zh_pdf_to_word", translation_mode: "en2zh",
    source_document_ir_file_id: "source-ir-a", document_ir_file_id: null,
    snapshot: { source_ir_file_id: "source-ir-a", final_ir_file_id: null, basis: "source" },
  },
  {
    name: "翻译无 IR", mode: "en2zh_pdf_to_word", translation_mode: "en2zh",
    source_document_ir_file_id: null, document_ir_file_id: null,
    snapshot: { source_ir_file_id: null, final_ir_file_id: null, basis: "none" },
  },
] as const;

type PageCore = {
  job: Ref<DocumentJobResponse | null>;
  reviewBlocks: Ref<DocumentReviewBlocksResponse | null>;
  reviewBlocksLoading: Ref<boolean>;
  reviewBlocksError: Ref<ApiClientError | null>;
  reviewBlocksConflict: Ref<boolean>;
  reviewHintsAvailable: ComputedRef<boolean>;
  reviewHintItems: ComputedRef<DocumentReviewBlockItemResponse[]>;
  reviewHintCounts: ComputedRef<{ blocker: number; warning: number; info: number }>;
  reviewHintSummary: ComputedRef<string>;
  reviewHintNotice: ComputedRef<string>;
  reviewHintsHaveWarnings: ComputedRef<boolean>;
  dispositionAlertType: ComputedRef<string>;
  dispositionTitle: ComputedRef<string>;
  dispositionDescription: ComputedRef<string>;
  downloadHint: ComputedRef<string>;
  actionSummaries: ComputedRef<Array<{ key: DocumentJobActionId; enabled: boolean; reason: string }>>;
  loadReviewBlocks: (append?: boolean, targetJobId?: string) => Promise<void>;
  loadAll: (options?: { secondary?: "all" | "smart" }) => Promise<void>;
  resetPageStateForRouteChange: () => void;
};

const disposers: Array<() => void> = [];

function setupPage() {
  const jobId = ref("job-a");
  const scope = effectScope();
  let unmount: (() => void) | undefined;
  // 执行页面真实请求、computed 和绑定 watch；其他诊断请求不参与本模块。
  const page = scope.run(() => executePageRequests<PageCore>(new URL("./JobDetailPage.vue", import.meta.url), [
    "job", "events", "files", "callbackSummary", "translationBatches", "translationBatchGeneration", "translationBatchExecution",
    "loading", "eventsLoading", "filesLoading", "callbackSummaryLoading", "translationBatchesLoading",
    "error", "eventsError", "filesError", "callbackSummaryError", "translationBatchesError", "configError", "lastDownloadLink",
    "retryDialogVisible", "cloneDialogVisible", "eventLevelFilter", "eventStageFilter", "activeTab",
    "reviewBlocks", "reviewBlocksLoading", "reviewBlocksError", "reviewBlocksConflict", "requestRounds", "disposed", "routeEpoch",
    "reviewContentBinding", "reviewSourceKey", "resetReviewBlocks", "loadReviewBlocks", "isCurrentRequest", "invalidateRequests",
    "loadJob", "loadAll", "supportsJobTranslationQa", "usesTranslationResources", "resetPageStateForRouteChange",
    "reviewHintsAvailable", "reviewHintItems", "reviewHintCounts", "reviewHintSummary", "reviewHintNotice", "reviewHintsHaveWarnings",
    "downloadHint", "dispositionAlertType", "dispositionTitle", "dispositionDescription", "taskActionOrder", "actionSummaries",
  ], {
    ref, computed, watch, jobId, documentJobsApi, normalizeApiError,
    documentJobActionDisabledReason, isDocumentJobActionEnabled, shouldShowDocumentJobAction,
    documentJobModeRequiresTranslationResources, documentJobModeSupportsTranslationQa,
    isJobStale: ref(false), failureHelpText: ref("失败详情"),
    loadEvents: vi.fn().mockResolvedValue(undefined), loadFiles: vi.fn().mockResolvedValue(undefined),
    loadCallbackSummary: vi.fn().mockResolvedValue(undefined), loadTranslationBatches: vi.fn().mockResolvedValue(undefined),
    shouldRefreshSecondaryDuringPoll: () => false, syncPolling: vi.fn(), stopPolling: vi.fn(),
    route: { query: {} }, openRetryDialog: vi.fn(), handleVisibilityChange: vi.fn(),
    document: { removeEventListener: vi.fn() },
    onBeforeUnmount: (callback: () => void) => { unmount = callback; },
  }, ["onBeforeUnmount", "watch"]))!;
  page.job.value = makeJob();
  const dispose = () => { unmount?.(); scope.stop(); };
  disposers.push(dispose);
  return { ...page, jobId, dispose };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiRequest).mockResolvedValue(reviewResponse());
});
afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
});

describe("只读复核提示的 API 与展示投影", () => {
  it("通过真实 GET wrapper 保留筛选、游标、来源和内容快照", async () => {
    const response = reviewResponse();
    vi.mocked(apiRequest).mockResolvedValueOnce(response);
    const params = { limit: 50, cursor: "cursor-a", source_page_index: 0, block_type: "image", problem: "flagged", severity: "warning" } as const;
    expect(await documentJobsApi.listReviewBlocks("job-a", params)).toBe(response);
    expect(apiRequest).toHaveBeenCalledWith({ url: "/api/v1/document-jobs/job-a/review/blocks", method: "GET", params });
    vi.mocked(apiRequest).mockRejectedValueOnce(new Error("读取失败"));
    await expect(documentJobsApi.listReviewBlocks("job-a")).rejects.toThrow("读取失败");
  });

  it("源页从零开始转为一开始，多 span 去重，未知页不从预览位置猜测", () => {
    expect(documentReviewSourcePagesText(spans(0))).toBe("源 PDF 第 1 页");
    expect(documentReviewSourcePagesText(spans(20))).toBe("源 PDF 第 21 页");
    expect(documentReviewSourcePagesText(spans(null))).toBe("源 PDF 页码未知");
    expect(documentReviewSourcePagesText([])).toBe("源 PDF 页码未知");
    const item = block("source-pages");
    item.source_spans = spans(20, 0, 20, null);
    expect(documentReviewSourcePagesText(item.source_spans)).toBe("源 PDF 第 1、21 页；部分源页未知");
    expect(item.location.preview_page_index).toBe(77);
  });

  it("受控码使用固定建议，未知码和对象原型名使用安全通用建议", () => {
    const flag = (code: string) => ({ code, severity: "warning", table_id: null } as const);
    expect(documentReviewFlagSuggestion(flag("caption_binding_uncertain"))).toBe("题注归属尚不确定，请对照源 PDF 检查题注与图片、表格的对应关系。");
    expect(documentReviewFlagSuggestion(flag("caption_reassociated"))).toBe("题注已按现有规则重新整理，可对照源 PDF 确认对应关系。");
    expect(documentReviewFlagSuggestion(flag("image_group_uncertain"))).toContain("图片分组尚不确定");
    expect(documentReviewFlagSuggestion(flag("docx_unstyled_heading_candidates:2"))).toContain("标题层级与样式");
    for (const code of ["future_code", "constructor", "__proto__", "<img onerror=alert(1)>"]) {
      expect(documentReviewFlagSuggestion(flag(code))).toBe("该提示尚无专用建议，请对照源 PDF 检查此块在 Word 中的内容与排版。");
    }
  });

  it("SFC 由现有 Vite 配置正常编译", () => {
    expect(JobDetailPage.setup).toBeTypeOf("function");
  });
});

describe("任务详情的只读复核提示", () => {
  it("首屏只取一页，主动追加沿同一快照使用游标，区分总提示数和已加载严重度", async () => {
    const page = setupPage();
    vi.mocked(apiRequest)
      .mockResolvedValueOnce(reviewResponse(makeJob(), { total: 3, next_cursor: "cursor-2" }))
      .mockResolvedValueOnce(reviewResponse(makeJob(), { total: 3, items: [block("block-b", "warning"), block("block-c")], next_cursor: null }));
    await page.loadReviewBlocks();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job-a/review/blocks", method: "GET", params: { limit: 50, problem: "flagged" },
    });
    expect(page.reviewHintSummary.value).toContain("已加载 1 / 共有 3 个提示位置");
    expect(page.reviewHintCounts.value).toEqual({ blocker: 0, warning: 0, info: 1 });
    expect(page.reviewHintNotice.value).toContain("已加载位置仅含信息提示");
    await page.loadReviewBlocks(true);
    expect(apiRequest).toHaveBeenCalledTimes(2);
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job-a/review/blocks", method: "GET", params: { limit: 50, problem: "flagged", cursor: "cursor-2" },
    });
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["block-a", "block-b", "block-c"]);
    expect(page.reviewHintCounts.value).toEqual({ blocker: 0, warning: 1, info: 2 });
    expect(page.reviewHintSummary.value).toContain("已加载 3 / 共有 3 个提示位置");
    expect(page.reviewHintNotice.value).toContain("包含警告或阻断提示");
    await page.loadReviewBlocks(true);
    expect(apiRequest).toHaveBeenCalledTimes(2);
  });

  it("只有信息提示保持完成语义，警告才升级复核提醒，后端动作和正式状态保持原值", async () => {
    const page = setupPage();
    const before = JSON.parse(JSON.stringify(page.job.value));
    await page.loadReviewBlocks();
    expect(page.dispositionAlertType.value).toBe("success");
    expect(page.dispositionTitle.value).toBe("任务已完成");
    expect(page.reviewHintsHaveWarnings.value).toBe(false);
    expect(page.downloadHint.value).toBe("当前不可下载：当前结果不可下载。");
    expect(page.actionSummaries.value.find((item) => item.key === "download")?.enabled).toBe(false);
    expect(page.job.value?.available_actions.publish?.eligible).toBe(true);
    expect(page.actionSummaries.value.find((item) => item.key === "publish")?.enabled).toBe(false);
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { items: [block("warn", "warning")] }));
    await page.loadReviewBlocks();
    expect(page.dispositionAlertType.value).toBe("warning");
    expect(page.dispositionTitle.value).toBe("任务已完成，存在需复核的警告提示");
    expect(page.job.value).toEqual(before);
    page.job.value!.available_actions.download.enabled = true;
    expect(page.downloadHint.value).toBe("后端当前允许获取下载链接；下载分类与警告以当次签发结果为准。");
    expect(page.actionSummaries.value.find((item) => item.key === "download")?.enabled).toBe(true);
    expect(page.actionSummaries.value.find((item) => item.key === "publish")?.enabled).toBe(false);
  });

  it.each(["not_ready", "unavailable"] as const)("%s 不显示零风险或成功复核结论", async (availability) => {
    const page = setupPage();
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { availability, items: [], total: 0 }));
    await page.loadReviewBlocks();
    expect(page.reviewHintsAvailable.value).toBe(false);
    expect(page.reviewHintSummary.value).toBe("提示位置数量尚未确认");
    expect(page.reviewHintNotice.value).toContain("不能据此判断内容是否存在风险");
    expect(page.dispositionAlertType.value).toBe("info");
    expect(page.dispositionTitle.value).toBe("任务已完成，复核提示尚未确认");
  });

  it("完整读取零提示仍不表示复核通过，未知信息码也不授予动作", async () => {
    const page = setupPage();
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { total: 0, items: [] }));
    await page.loadReviewBlocks();
    expect(page.reviewHintSummary.value).toContain("已加载 0 / 共有 0 个提示位置");
    expect(page.reviewHintNotice.value).toBe("当前来源未返回带提示的位置；这不代表已完成人工复核。");
    const unknown = block("unknown");
    unknown.flags[0].code = "future_code";
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { items: [unknown] }));
    await page.loadReviewBlocks();
    expect(page.reviewHintItems.value[0].flags[0].code).toBe("future_code");
    expect(page.reviewHintNotice.value).toContain("不代表正式复核通过");
    expect(page.job.value?.review_status).toBe("unreviewed");
    expect(page.actionSummaries.value.find((item) => item.key === "download")?.enabled).toBe(false);
  });

  it("追加失败后清除旧清单并显示错误，刷新只重新读取第一页", async () => {
    const page = setupPage();
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { total: 2, next_cursor: "cursor-2" }));
    await page.loadReviewBlocks();
    vi.mocked(apiRequest).mockRejectedValueOnce(new Error("提示读取失败"));
    await page.loadReviewBlocks(true);
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksError.value?.message).toBe("提示读取失败");
    expect(page.reviewHintSummary.value).toBe("提示位置数量尚未确认");
    expect(page.reviewHintNotice.value).toContain("提示读取失败");
    expect(page.dispositionAlertType.value).toBe("info");
    await page.loadReviewBlocks();
    expect(page.reviewBlocksError.value).toBeNull();
    expect(page.reviewHintsAvailable.value).toBe(true);
    expect(apiRequest).toHaveBeenLastCalledWith({
      url: "/api/v1/document-jobs/job-a/review/blocks", method: "GET", params: { limit: 50, problem: "flagged" },
    });
  });

  it.each(["snapshot", "checksum", "revision", "receipt"])("追加的 %s 变化清除旧清单，禁止拼接", async (changed) => {
    const page = setupPage();
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { total: 2, next_cursor: "cursor-2" }));
    await page.loadReviewBlocks();
    const next = reviewResponse(makeJob(), { items: [block("block-b")] });
    if (changed === "snapshot") next.content_snapshot.snapshot_id = "sha256:snapshot-b";
    if (changed === "checksum") next.source.result_sha256 = "sha256:word-b";
    if (changed === "revision") next.source.file_review_source_revision = 1;
    if (changed === "receipt") next.source.receipt_sha256 = "sha256:receipt-b";
    vi.mocked(apiRequest).mockResolvedValueOnce(next);
    await page.loadReviewBlocks(true);
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksConflict.value).toBe(true);
    expect(page.reviewHintItems.value).toEqual([]);
    expect(page.reviewHintSummary.value).toBe("提示位置数量尚未确认");
    expect(page.reviewHintNotice.value).toContain("请刷新提示后再复核");
    expect(page.reviewBlocksLoading.value).toBe(false);
  });

  it.each(["job", "generation", "ir", "result", "pdf"])("首次响应的 %s 来源冲突也不能显示", async (changed) => {
    const page = setupPage();
    const response = reviewResponse();
    if (changed === "job") response.job_id = "job-b";
    if (changed === "generation") response.source.generation = 1;
    if (changed === "ir") response.source.ir_file_id = "ir-b";
    if (changed === "result") response.source.result_file_id = "word-b";
    if (changed === "pdf") response.content_snapshot.source_pdf_file_id = "pdf-b";
    vi.mocked(apiRequest).mockResolvedValueOnce(response);
    await page.loadReviewBlocks();
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksConflict.value).toBe(true);
    expect(page.dispositionAlertType.value).toBe("info");
  });

  it.each(snapshotBindings)("$name 遵循后端 source/final/basis 快照投影", async (binding) => {
    const page = setupPage();
    const target = makeJob({
      mode: binding.mode, translation_mode: binding.translation_mode,
      source_document_ir_file_id: binding.source_document_ir_file_id, document_ir_file_id: binding.document_ir_file_id,
      status: "running", stage: "ir_converting", result_file_id: null,
    });
    page.job.value = target;
    const response = reviewResponse(target);
    response.content_snapshot = { ...response.content_snapshot, ...binding.snapshot };
    if (binding.snapshot.basis === "none") {
      response.availability = "not_ready";
      response.items = [];
      response.total = 0;
    }
    vi.mocked(apiRequest).mockResolvedValueOnce(response);
    await page.loadReviewBlocks();
    expect(page.reviewBlocksConflict.value).toBe(false);
    expect(page.reviewBlocks.value?.content_snapshot).toEqual(response.content_snapshot);
    expect(page.reviewBlocks.value?.availability).toBe(response.availability);
  });

  it("旧详情缺源 IR 字段时保持来源未确认，显式 null 到达后才允许绑定", async () => {
    const page = setupPage();
    const legacyJob = makeJob();
    delete legacyJob.source_document_ir_file_id;
    page.job.value = legacyJob;
    await page.loadReviewBlocks();
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksConflict.value).toBe(true);
    expect(page.reviewHintSummary.value).toBe("提示位置数量尚未确认");
    page.job.value = { ...legacyJob, source_document_ir_file_id: null };
    expect(page.reviewBlocksConflict.value).toBe(false);
    await page.loadReviewBlocks();
    expect(page.reviewHintsAvailable.value).toBe(true);
    expect(page.reviewBlocksConflict.value).toBe(false);
  });

  it.each(snapshotBindings.filter((binding) => binding.snapshot.basis === "final"))(
    "$name 拒绝不匹配的源 IR、最终 IR 和 basis", async (binding) => {
      const page = setupPage();
      const target = makeJob({
        mode: binding.mode, translation_mode: binding.translation_mode,
        source_document_ir_file_id: binding.source_document_ir_file_id, document_ir_file_id: binding.document_ir_file_id,
      });
      page.job.value = target;
      for (const field of ["source_ir_file_id", "final_ir_file_id", "basis"] as const) {
        const response = reviewResponse(target);
        response.content_snapshot = { ...response.content_snapshot, ...binding.snapshot };
        if (field === "basis") response.content_snapshot.basis = "source";
        else response.content_snapshot[field] = "unexpected-ir";
        vi.mocked(apiRequest).mockResolvedValueOnce(response);
        await page.loadReviewBlocks();
        expect(page.reviewBlocks.value, field).toBeNull();
        expect(page.reviewBlocksConflict.value, field).toBe(true);
      }
    },
  );
});

describe("复核读取的请求竞态", () => {
  it.each(["success", "error"])("旧%s与旧finally不能结束新刷新的加载状态", async (outcome) => {
    const page = setupPage();
    const older = deferred<DocumentReviewBlocksResponse>();
    const newer = deferred<DocumentReviewBlocksResponse>();
    vi.mocked(apiRequest).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.loadReviewBlocks();
    const second = page.loadReviewBlocks();
    if (outcome === "success") older.resolve(reviewResponse());
    else older.reject(new Error("旧请求失败"));
    await first;
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksError.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    newer.resolve(reviewResponse(makeJob(), { items: [block("new")] }));
    await second;
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["new"]);
    expect(page.reviewBlocksLoading.value).toBe(false);
  });

  it.each([
    ["retry_count", 1], ["source_document_ir_file_id", "source-ir-b"], ["document_ir_file_id", "ir-b"],
    ["result_file_id", "word-b"], ["source_file_id", "pdf-b"],
  ] as const)("同任务%s变化同步清除旧数据，并阻止旧追加响应与finally", async (field, value) => {
    const page = setupPage();
    vi.mocked(apiRequest).mockResolvedValueOnce(reviewResponse(makeJob(), { total: 2, next_cursor: "cursor-2" }));
    await page.loadReviewBlocks();
    const older = deferred<DocumentReviewBlocksResponse>();
    const newer = deferred<DocumentReviewBlocksResponse>();
    vi.mocked(apiRequest).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.loadReviewBlocks(true);
    page.job.value = { ...page.job.value!, [field]: value };
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(false);
    const second = page.loadReviewBlocks();
    older.resolve(reviewResponse());
    await first;
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    newer.resolve(reviewResponse(page.job.value!, { items: [block("current")] }));
    await second;
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["current"]);
    expect(page.reviewBlocksLoading.value).toBe(false);
  });

  it("路由 A→B→A 的旧响应不能回填，旧finally不能结束返回后的新请求", async () => {
    const page = setupPage();
    const older = deferred<DocumentReviewBlocksResponse>();
    const newer = deferred<DocumentReviewBlocksResponse>();
    vi.mocked(apiRequest).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.loadReviewBlocks();
    page.jobId.value = "job-b";
    page.resetPageStateForRouteChange();
    page.jobId.value = "job-a";
    page.resetPageStateForRouteChange();
    page.job.value = makeJob();
    const second = page.loadReviewBlocks();
    older.resolve(reviewResponse());
    await first;
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    newer.resolve(reviewResponse(makeJob(), { items: [block("returned")] }));
    await second;
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["returned"]);
  });

  it("卸载后的响应与finally失效，禁止再次发起读取", async () => {
    const page = setupPage();
    const pending = deferred<DocumentReviewBlocksResponse>();
    vi.mocked(apiRequest).mockReturnValueOnce(pending.promise);
    const first = page.loadReviewBlocks();
    page.dispose();
    pending.resolve(reviewResponse());
    await first;
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    await page.loadReviewBlocks();
    expect(apiRequest).toHaveBeenCalledTimes(1);
  });

  it("loadAll 初次接入提示读取，智能轮询换代后重读第一页", async () => {
    const page = setupPage();
    const firstJob = makeJob();
    const nextJob = makeJob({ retry_count: 1, document_ir_file_id: "ir-next", result_file_id: "word-next" });
    vi.mocked(apiRequest)
      .mockResolvedValueOnce(firstJob).mockResolvedValueOnce(reviewResponse(firstJob))
      .mockResolvedValueOnce(nextJob).mockResolvedValueOnce(reviewResponse(nextJob, { items: [block("next-generation")] }));
    await page.loadAll();
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["block-a"]);
    await page.loadAll({ secondary: "smart" });
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["next-generation"]);
    const reviewCalls = vi.mocked(apiRequest).mock.calls.filter(([request]) => request.url?.endsWith("/review/blocks"));
    expect(reviewCalls).toHaveLength(2);
    expect(reviewCalls.map(([request]) => request.params)).toEqual([{ limit: 50, problem: "flagged" }, { limit: 50, problem: "flagged" }]);
  });

  it("同代安装源 IR 后 smart 重读，旧 not_ready 响应与 finally 不得覆盖新读取", async () => {
    const page = setupPage();
    const initialJob = makeJob({
      mode: "en2zh_pdf_to_word", translation_mode: "en2zh", status: "running", stage: "ir_converting",
      source_document_ir_file_id: null, document_ir_file_id: null, result_file_id: null,
    });
    const sourceInstalledJob = { ...initialJob, source_document_ir_file_id: "source-ir-installed" };
    const oldNotReady = reviewResponse(initialJob, { availability: "not_ready", items: [], total: 0 });
    oldNotReady.content_snapshot = {
      ...oldNotReady.content_snapshot, source_ir_file_id: null, final_ir_file_id: null, basis: "none",
    };
    const current = reviewResponse(sourceInstalledJob, { items: [block("source-installed")] });
    current.content_snapshot = {
      ...current.content_snapshot, snapshot_id: "sha256:source-installed",
      source_ir_file_id: "source-ir-installed", final_ir_file_id: null, basis: "source",
    };
    page.job.value = initialJob;
    const older = deferred<DocumentReviewBlocksResponse>();
    const newer = deferred<DocumentReviewBlocksResponse>();
    const newReadStarted = deferred<void>();
    vi.mocked(apiRequest).mockReturnValueOnce(older.promise).mockResolvedValueOnce(sourceInstalledJob).mockImplementationOnce(() => {
      newReadStarted.resolve(undefined);
      return newer.promise;
    });
    const first = page.loadReviewBlocks();
    const smart = page.loadAll({ secondary: "smart" });
    await newReadStarted.promise;
    expect(page.job.value?.retry_count).toBe(initialJob.retry_count);
    expect(page.job.value?.document_ir_file_id).toBeNull();
    expect(page.job.value?.source_document_ir_file_id).toBe("source-ir-installed");
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    older.resolve(oldNotReady);
    await first;
    expect(page.reviewBlocks.value).toBeNull();
    expect(page.reviewBlocksLoading.value).toBe(true);
    expect(page.reviewBlocksError.value).toBeNull();
    newer.resolve(current);
    await smart;
    expect(page.reviewHintItems.value.map((item) => item.block_id)).toEqual(["source-installed"]);
    expect(page.reviewBlocksLoading.value).toBe(false);
    const reviewCalls = vi.mocked(apiRequest).mock.calls.filter(([request]) => request.url?.endsWith("/review/blocks"));
    expect(reviewCalls).toHaveLength(2);
    expect(reviewCalls.map(([request]) => request.params)).toEqual([{ limit: 50, problem: "flagged" }, { limit: 50, problem: "flagged" }]);
  });
});
