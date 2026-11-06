import { afterEach, describe, expect, it, vi } from "vitest";
import { createRenderer, nextTick, reactive, ref } from "vue";

import { documentJobsApi } from "@/api/documentJobs";
import type { DocumentJobConfigSummaryResponse, DocumentJobResponse } from "@/api/types";
import type { Router } from "vue-router";
import type { useAuthStore } from "@/stores/auth";
import { useJobDetailData } from "./useJobDetailData";
import { useJobDetailResources } from "./useJobDetailResources";
import { useJobDetailActions } from "./useJobDetailActions";

vi.mock("@/api/documentJobs", () => ({ documentJobsApi: {
  get: vi.fn(), listEvents: vi.fn(), listFiles: vi.fn(), getCallbackMessageSummary: vi.fn(),
  listTranslationBatches: vi.fn(), listReviewBlocks: vi.fn(), getConfigSummary: vi.fn(),
  retry: vi.fn(), clone: vi.fn(),
} }));
vi.mock("element-plus", () => ({ ElMessage: { success: vi.fn(), warning: vi.fn() }, ElMessageBox: { confirm: vi.fn() } }));

function job(overrides: Partial<DocumentJobResponse> = {}): DocumentJobResponse {
  return {
    id: "job-a", status: "running", mode: "direct_pdf_to_word", retry_count: 0,
    source_file_id: "pdf-a", source_document_ir_file_id: null, document_ir_file_id: null,
    result_file_id: null, request_snapshot: {}, ...overrides,
  } as DocumentJobResponse;
}

// 无 DOM 的 Vue renderer 仍执行真实挂载、watch 和卸载 hooks。
const renderer = createRenderer<object, object>({
  patchProp: () => {}, insert: () => {}, remove: () => {}, createElement: () => ({}),
  createText: () => ({}), createComment: () => ({}), setText: () => {}, setElementText: () => {},
  parentNode: () => null, nextSibling: () => null,
});
const disposers: Array<() => void> = [];
afterEach(() => {
  disposers.splice(0).forEach((dispose) => dispose());
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("任务详情真实生命周期", () => {
  it("只创建一个轮询，隐藏暂停、恢复重启，卸载移除监听且旧响应不落地", async () => {
    vi.useFakeTimers();
    const document = Object.assign(new EventTarget(), { hidden: false });
    const addListener = vi.spyOn(document, "addEventListener");
    const removeListener = vi.spyOn(document, "removeEventListener");
    vi.stubGlobal("document", document);
    vi.stubGlobal("window", { setInterval, clearInterval });
    vi.mocked(documentJobsApi.get).mockResolvedValue(job());
    vi.mocked(documentJobsApi.listEvents).mockResolvedValue({ items: [] } as never);
    vi.mocked(documentJobsApi.listFiles).mockResolvedValue({ files: [] } as never);
    vi.mocked(documentJobsApi.getCallbackMessageSummary).mockResolvedValue({} as never);
    vi.mocked(documentJobsApi.listReviewBlocks).mockResolvedValue({
      job_id: "job-a", source: { generation: 0, ir_file_id: null, result_file_id: null },
      content_snapshot: { source_pdf_file_id: "pdf-a", source_ir_file_id: null, final_ir_file_id: null, basis: "none" },
      availability: "not_ready", items: [],
    } as never);
    const route = reactive({ params: { jobId: "job-a" }, query: {}, fullPath: "/jobs/job-a" });
    let data!: ReturnType<typeof useJobDetailData>;
    const app = renderer.createApp({ setup() {
      data = useJobDetailData(route, { onRetryRequested: vi.fn(), onRouteReset: vi.fn() });
      return () => null;
    } });
    app.mount({});
    let mounted = true;
    disposers.push(() => { if (mounted) app.unmount(); });
    await vi.waitFor(() => expect(data.reviewBlocks.value).not.toBeNull());
    await nextTick();
    expect(addListener).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(4000);
    expect(documentJobsApi.get).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(1);
    document.hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    expect(vi.getTimerCount()).toBe(0);
    document.hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    expect(vi.getTimerCount()).toBe(1);
    let resolve!: (value: DocumentJobResponse) => void;
    vi.mocked(documentJobsApi.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const pending = data.loadJob();
    app.unmount();
    mounted = false;
    expect(removeListener).toHaveBeenCalledWith("visibilitychange", addListener.mock.calls[0][1]);
    expect(vi.getTimerCount()).toBe(0);
    resolve(job({ status: "succeeded" }));
    await pending;
    expect(data.job.value?.status).toBe("running");
  });
});

function setupActions(role: "admin" | "operator") {
  const data = { job: ref<DocumentJobResponse | null>(job({ status: "failed" })), jobId: ref("job-a"), error: ref(null), loadAll: vi.fn() };
  const router = { push: vi.fn() } as unknown as Router;
  const auth = reactive({ user: { role } }) as unknown as ReturnType<typeof useAuthStore>;
  const actions = useJobDetailActions(data, useJobDetailResources(data), router, auth);
  actions.configSummary.value = { options: {
    templates: [{ resource_id: "template", version: "v1" }],
    term_rule_sets: [{ resource_id: "rule", version: "v1" }],
    translation_term_sets: [{ resource_id: "translation", version: "v1" }],
    translation_profiles: [{ resource_id: "profile", version: "v1" }],
  } } as DocumentJobConfigSummaryResponse;
  return { data, actions, router };
}

describe("任务动作共享数据与配置权限", () => {
  it("operator 重试不发送管理员资源，返回任务写入唯一 job 并刷新", async () => {
    const { data, actions } = setupActions("operator");
    actions.openRetryDialog(data.job.value!);
    actions.retryDialog.strategy = "select_term_assets";
    actions.retryDialog.termRuleVersion = "rule@v1";
    actions.retryDialog.translationTermVersion = "translation@v1";
    const next = job({ retry_count: 1 });
    vi.mocked(documentJobsApi.retry).mockResolvedValue({ job: next } as never);
    await actions.submitRetryDialog();
    expect(documentJobsApi.retry).toHaveBeenCalledWith("job-a", { reason: "frontend retry" });
    expect(data.job.value).toEqual(next);
    expect(data.loadAll).toHaveBeenCalledOnce();
    expect(actions.retryDialogVisible.value).toBe(false);
    expect(documentJobsApi.getConfigSummary).not.toHaveBeenCalled();
  });

  it("admin direct 克隆只发送非翻译资源，清理路由时关闭动作弹窗", async () => {
    const { data, actions, router } = setupActions("admin");
    actions.openCloneDialog(data.job.value!);
    actions.cloneDialog.strategy = "select_published_versions";
    actions.cloneDialog.templateVersion = "template@v1";
    actions.cloneDialog.termRuleVersion = "rule@v1";
    actions.cloneDialog.translationTermVersion = "translation@v1";
    actions.cloneDialog.translationProfileVersion = "profile@v1";
    vi.mocked(documentJobsApi.clone).mockResolvedValue({ job_id: "job-new" } as never);
    await actions.submitCloneDialog();
    expect(documentJobsApi.clone).toHaveBeenCalledWith("job-a", {
      reason: "frontend clone", config_strategy: "select_published_versions",
      template_version_id: "template@v1", term_rule_set_id: "rule", term_rule_set_version: "v1",
    });
    expect(router.push).toHaveBeenCalledWith({ name: "job-detail", params: { jobId: "job-new" } });
    actions.openRetryDialog(data.job.value!);
    actions.openCloneDialog(data.job.value!);
    actions.resetForRouteChange();
    expect(actions.retryDialogVisible.value || actions.cloneDialogVisible.value).toBe(false);
    expect(data.job.value?.retry_count).toBe(0);
  });
});
