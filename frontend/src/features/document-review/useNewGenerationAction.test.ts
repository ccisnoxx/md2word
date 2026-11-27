// 文件：frontend/src/features/document-review/useNewGenerationAction.test.ts
// 用途：验证 Admin 同任务新代与正式发布的 UUID 幂等键保留、503 对账以及按 Tab 懒加载合同。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRenderer, nextTick, ref } from "vue";

import { documentJobsApi } from "@/api/documentJobs";
import type { DocumentJobResponse, DocumentPublicationsResponse, ReviewExpectedSourceRequest } from "@/api/types";
import { useJobPublication } from "@/features/job-detail/useJobPublication";
import { useNewGenerationAction } from "./useNewGenerationAction";

vi.mock("@/api/documentJobs", () => ({
  documentJobsApi: {
    requestNewGeneration: vi.fn(),
    getGenerationRequest: vi.fn(),
    listPublications: vi.fn(),
    publish: vi.fn(),
    createPublicationDownloadUrl: vi.fn(),
  },
}));
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

const renderer = createRenderer<object, object>({
  patchProp: () => {},
  insert: () => {},
  remove: () => {},
  createElement: () => ({}),
  createText: () => ({}),
  createComment: () => ({}),
  setText: () => {},
  setElementText: () => {},
  parentNode: () => null,
  nextSibling: () => null,
});

const expectedSource: ReviewExpectedSourceRequest = {
  generation: 1,
  result_file_id: "file_docx_1",
  result_sha256: `sha256:${"a".repeat(64)}`,
  file_review_source_revision: 2,
  receipt_sha256: `sha256:${"b".repeat(64)}`,
};

const disposers: Array<() => void> = [];

function stubSessionStorage(): Map<string, string> {
  const store = new Map<string, string>();
  vi.stubGlobal("window", {
    sessionStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, val: string) => { store.set(key, val); },
      removeItem: (key: string) => { store.delete(key); },
    },
    open: vi.fn(() => ({ opener: {} })),
  });
  return store;
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
  vi.unstubAllGlobals();
});

describe("useNewGenerationAction 幂等对账", () => {
  it("遇到 503 异常后保留同一 UUID，禁止重复 POST，改为通过 GET 对账确认受理结果", async () => {
    stubSessionStorage();
    const jobId = ref("job_ng_1");
    const onAccepted = vi.fn();
    const action = useNewGenerationAction({ jobId, onAccepted });

    action.open(expectedSource);
    const originalUuid = action.form.requestId;
    expect(originalUuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);

    action.form.note = "  表格需要重跑新代  ";
    vi.mocked(documentJobsApi.requestNewGeneration).mockRejectedValueOnce({
      status: 503,
      code: "service_unavailable",
      generationRequestId: originalUuid,
      accepted: true,
      acceptedGeneration: 2,
      message: "已受理但投递暂不可用",
      raw: {},
    });

    const first = await action.submit();
    expect(first).toBeNull();
    expect(action.form.needsReconcile).toBe(true);
    expect(action.form.requestId).toBe(originalUuid);
    expect(action.canSubmit.value).toBe(false);

    // 重新打开弹窗仍保留同一 UUID，绝不换 key
    action.open(expectedSource);
    expect(action.form.requestId).toBe(originalUuid);
    expect(action.form.needsReconcile).toBe(true);

    vi.mocked(documentJobsApi.getGenerationRequest).mockResolvedValueOnce({
      accepted: true,
      request_id: originalUuid,
      job_id: "job_ng_1",
      accepted_generation: 2,
      accepted_at: "2026-11-27T15:00:00Z",
      source: expectedSource,
      audit_id: "audit_ng_1",
      replayed: true,
      current_generation: 2,
      current_job: {
        id: "job_ng_1",
        status: "queued",
        stage: "uploaded",
        progress: 0,
        retry_count: 2,
        result_file_id: null,
        quality_status: "pending",
        review_status: "unreviewed",
        delivery_status: "internal_draft",
      },
    });

    const reconciled = await action.reconcile();
    expect(documentJobsApi.getGenerationRequest).toHaveBeenCalledWith("job_ng_1", originalUuid);
    expect(reconciled?.accepted_generation).toBe(2);
    expect(action.form.needsReconcile).toBe(false);
    expect(onAccepted).toHaveBeenCalledTimes(1);
  });
});

describe("useJobPublication 懒加载与幂等发布", () => {
  it("仅在切入 publication Tab 时加载，遇 503 保留同一幂等键重试发布", async () => {
    stubSessionStorage();
    const jobId = ref("job_pub_1");
    const activeTab = ref("overview");
    const job = ref<DocumentJobResponse | null>({
      id: "job_pub_1",
      retry_count: 1,
      result_file_id: "file_docx_1",
      available_actions: { publish: { enabled: true, eligible: true } },
    } as unknown as DocumentJobResponse);

    const publicationsPayload: DocumentPublicationsResponse = {
      job_id: "job_pub_1",
      expected_source: {
        ...expectedSource,
        review_record_id: "rev_1",
        review_sequence: 1,
        preview_run_id: "prev_1",
        preview_revision: 1,
        quality_summary_sha256: `sha256:${"c".repeat(64)}`,
      },
      preflight_checks: [
        { code: "review", status: "passed", reason_code: null, message: "检查通过。" },
      ],
      items: [],
      download_actions: {},
      available_actions: {
        download: { enabled: true, disabled_reason: null, retryable: false },
        retry: { enabled: false, disabled_reason: null, retryable: false },
        cancel: { enabled: false, disabled_reason: null, retryable: false },
        archive: { enabled: true, disabled_reason: null, retryable: false },
        unarchive: { enabled: false, disabled_reason: null, retryable: false },
        clone: { enabled: true, disabled_reason: null, retryable: false },
        delete: { enabled: false, disabled_reason: null, retryable: false },
        publish: { enabled: true, eligible: true, disabled_reason: null, retryable: false },
        new_generation: { enabled: true, disabled_reason: null, retryable: false },
      },
    };
    vi.mocked(documentJobsApi.listPublications).mockResolvedValue(publicationsPayload);

    const onPublished = vi.fn();
    let pub!: ReturnType<typeof useJobPublication>;
    const app = renderer.createApp({
      setup() {
        pub = useJobPublication({ jobId, job, activeTab, onPublished });
        return () => null;
      },
    });
    app.mount({});
    disposers.push(() => app.unmount());

    await nextTick();
    expect(documentJobsApi.listPublications).not.toHaveBeenCalled();

    activeTab.value = "publication";
    await vi.waitFor(() => expect(pub.publications.value).not.toBeNull());
    expect(pub.publishEnabled.value).toBe(true);

    pub.openPublishDialog();
    const publishUuid = pub.publishForm.requestId;
    pub.publishForm.note = "准予交付客户";

    vi.mocked(documentJobsApi.publish).mockRejectedValueOnce({
      status: 503,
      code: "service_unavailable",
      message: "发布服务暂不可用",
      raw: {},
    });
    expect(await pub.submitPublish()).toBe(false);
    expect(pub.publishForm.ambiguousFailure).toBe(true);
    expect(pub.publishForm.requestId).toBe(publishUuid);

    // 再次提交使用同一 UUID 重放
    vi.mocked(documentJobsApi.publish).mockResolvedValueOnce({
      publication: {
        publication_id: "pub_001",
        job_id: "job_pub_1",
        generation: 1,
        source_file_id: "file_pdf_1",
        source_sha256: `sha256:${"a".repeat(64)}`,
        result_file_id: "file_docx_1",
        result_sha256: `sha256:${"a".repeat(64)}`,
        review_record_id: "rev_1",
        review_sequence: 1,
        preview_run_id: "prev_1",
        published_by: "admin",
        published_at: "2026-11-27T15:10:00Z",
        note: "准予交付客户",
        versions: {
          template: { resource_id: "tpl_1", version: "v1", snapshot_hash: "h1" },
          symbol_rules: { resource_id: "sym_1", version: "v1", snapshot_hash: "h2" },
          renderer_implementation_sha256: "h3",
          translation_status: "not_applicable",
          models: [],
        },
      },
      available_actions: publicationsPayload.available_actions,
    });
    expect(await pub.submitPublish()).toBe(true);
    expect(vi.mocked(documentJobsApi.publish).mock.calls[1][1].request_id).toBe(publishUuid);
    expect(onPublished).toHaveBeenCalledTimes(1);
  });
});
