import { computed, reactive } from "vue";
import { documentJobsApi } from "@/api/documentJobs";
import { useJobDetailData } from "@/features/job-detail/useJobDetailData";
import { useJobsList } from "@/features/jobs/useJobsList";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deferred } from "./pageRequestTestSupport";

const hooks = vi.hoisted(() => ({
  mounted: [] as Array<() => Promise<void>>,
  unmount: [] as Array<() => void>,
  watches: [] as Array<(...args: any[]) => any>,
}));
vi.mock("vue", async (importOriginal) => ({
  ...await importOriginal<typeof import("vue")>(),
  onMounted: (callback: () => Promise<void>) => hooks.mounted.push(callback),
  onBeforeUnmount: (callback: () => void) => hooks.unmount.push(callback),
  watch: (_source: unknown, callback: (...args: any[]) => any) => hooks.watches.push(callback),
}));
vi.mock("@/api/documentJobs", () => ({ documentJobsApi: {
  list: vi.fn(), get: vi.fn(), listEvents: vi.fn(), listFiles: vi.fn(), getCallbackMessageSummary: vi.fn(),
  listTranslationBatches: vi.fn(), listReviewBlocks: vi.fn(),
} }));

afterEach(() => vi.unstubAllGlobals());

type Request = (...args: any[]) => Promise<any>;

function setupJobs() {
  hooks.unmount.length = 0;
  const route = reactive({ query: {}, fullPath: "/jobs" });
  const router = { push: vi.fn(), replace: vi.fn() };
  const list = vi.mocked(documentJobsApi).list as unknown as ReturnType<typeof vi.fn<Request>>;
  list.mockReset();
  const state = useJobsList(route as never, router as never, { onResultReset: vi.fn() });
  state.selectedJobs.value = ["selected"] as never;
  state.searchKeyword.value = "old";
  return { ...state, list, unmount: () => hooks.unmount.forEach((callback) => callback()) };
}

function listResponse(id: string) {
  return { items: [id], total: 1, summary: { [id]: 1 }, translation_qa_summary: { approved: 1 } };
}

describe("useJobsList 请求轮次", () => {
  it.each([false, true])("加载期间接受新筛选，后台请求=%s", async (background) => {
    const page = setupJobs();
    const older = deferred<unknown>();
    const newer = deferred<unknown>();
    page.list.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.loadJobs({ background });
    page.searchKeyword.value = "new";
    page.page.value = 2;
    const second = page.loadJobs();
    expect(page.list).toHaveBeenCalledTimes(2);
    expect(page.list.mock.calls[1][0]).toMatchObject({ q: "new", page: 2 });
    newer.resolve(listResponse("new"));
    await second;
    const refreshedAt = page.lastRefreshedAt.value;
    page.selectedJobs.value = ["new selection"] as never;
    older.resolve(listResponse("old"));
    await first;
    expect(page.jobs.value).toEqual(["new"]);
    expect(page.filteredSummary.value).toEqual({ new: 1 });
    expect(page.selectedJobs.value).toEqual(["new selection"]);
    expect(page.lastRefreshedAt.value).toBe(refreshedAt);
    expect(page.loading.value).toBe(false);
    expect(page.backgroundRefreshing.value).toBe(false);
  });

  it("旧错误和 finally 不得清掉新请求的加载状态，后台重复请求合并", async () => {
    const page = setupJobs();
    const older = deferred<unknown>();
    const newer = deferred<unknown>();
    page.list.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.loadJobs({ background: true });
    await page.loadJobs({ background: true });
    expect(page.list).toHaveBeenCalledTimes(1);
    const second = page.loadJobs();
    older.reject(new Error("旧错误"));
    await first;
    expect(page.error.value).toBeNull();
    expect(page.loading.value).toBe(true);
    expect(page.backgroundRefreshing.value).toBe(false);
    newer.reject(new Error("当前错误"));
    await second;
    expect(page.error.value).toMatchObject({ message: "当前错误" });
    expect(page.loading.value).toBe(false);
  });

  it.each(["success", "error"])("卸载使待处理的%s和后续请求失效", async (outcome) => {
    const page = setupJobs();
    const pending = deferred<unknown>();
    page.list.mockReturnValue(pending.promise);
    const request = page.loadJobs();
    page.unmount();
    if (outcome === "success") pending.resolve(listResponse("late"));
    else pending.reject(new Error("卸载后的错误"));
    await request;
    expect(page.jobs.value).toEqual([]);
    expect(page.error.value).toBeNull();
    expect(page.loading.value).toBe(true);
    await page.loadJobs();
    expect(page.list).toHaveBeenCalledTimes(1);
  });
});

const detailLoaders = [
  { loader: "loadJob", api: "get", data: "job", loading: "loading", error: "error", response: (id: string) => ({ id, mode: "en2zh_pdf_to_word", status: "running", retry_count: 0 }) },
  { loader: "loadEvents", api: "listEvents", data: "events", loading: "eventsLoading", error: "eventsError", response: (id: string) => ({ items: [id] }) },
  { loader: "loadFiles", api: "listFiles", data: "files", loading: "filesLoading", error: "filesError", response: (id: string) => ({ files: [id] }) },
  { loader: "loadCallbackSummary", api: "getCallbackMessageSummary", data: "callbackSummary", loading: "callbackSummaryLoading", error: "callbackSummaryError", response: (id: string) => ({ id }) },
  { loader: "loadTranslationBatches", api: "listTranslationBatches", data: "translationBatches", loading: "translationBatchesLoading", error: "translationBatchesError", response: (id: string) => ({ items: [id], generation: 0, execution: { outcome: id } }) },
] as const;

function setupDetail(_includeLifecycle = false) {
  hooks.mounted.length = 0;
  hooks.unmount.length = 0;
  hooks.watches.length = 0;
  const api = vi.mocked(documentJobsApi) as unknown as Record<string, ReturnType<typeof vi.fn<Request>>>;
  for (const item of detailLoaders) {
    api[item.api].mockReset().mockResolvedValue(item.response("default") as never);
  }
  api.listReviewBlocks.mockReset().mockResolvedValue({} as never);
  const ticks: Array<() => void> = [];
  const browser = {
    setInterval: vi.fn((callback: () => void) => { ticks.push(callback); return ticks.length; }),
    clearInterval: vi.fn(),
  };
  vi.stubGlobal("window", browser);
  vi.stubGlobal("document", { hidden: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  const route = reactive({ params: { jobId: "job-a" }, query: { retry: "" }, fullPath: "/jobs/job-a" });
  const openRetryDialog = vi.fn();
  const data = useJobDetailData(route, { onRetryRequested: openRetryDialog, onRouteReset: vi.fn() });
  data.job.value = detailLoaders[0].response("job-a") as never;
  const state: Record<string, any> = {
    ...data,
    jobId: computed({ get: () => route.params.jobId, set: (value) => { route.params.jobId = value; } }),
  };
  return {
    state, route, functions: data, api, browser, ticks,
    mounted: [...hooks.mounted], watchCallbacks: [...hooks.watches], openRetryDialog,
    unmount: () => hooks.unmount.forEach((callback) => callback()),
  };
}

describe("JobDetailPage 请求轮次", () => {
  it.each(detailLoaders)("$loader 的旧成功不能覆盖同一任务的新成功", async (item) => {
    const page = setupDetail();
    const older = deferred<unknown>();
    const newer = deferred<unknown>();
    page.api[item.api].mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.functions[item.loader]();
    const second = page.functions[item.loader]();
    newer.resolve(item.response("new"));
    await second;
    const latest = page.state[item.data].value;
    older.resolve(item.response("old"));
    await first;
    expect(page.state[item.data].value).toEqual(latest);
    expect(page.state[item.loading].value).toBe(false);
  });

  it.each(detailLoaders)("$loader 的旧错误和 finally 不影响新请求", async (item) => {
    const page = setupDetail();
    const older = deferred<unknown>();
    const newer = deferred<unknown>();
    page.api[item.api].mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const first = page.functions[item.loader]();
    const second = page.functions[item.loader]();
    older.reject(new Error("旧错误"));
    await first;
    expect(page.state[item.error].value).toBeNull();
    expect(page.state[item.loading].value).toBe(true);
    newer.reject(new Error("当前错误"));
    await second;
    expect(page.state[item.error].value).toMatchObject({ message: "当前错误" });
    expect(page.state[item.loading].value).toBe(false);
  });

  it.each(["job", "events"])("新 loadAll 使等待%s的旧加载链停止，不再发起子请求", async (stage) => {
    const page = setupDetail();
    const pending = deferred<unknown>();
    const enteredEvents = deferred<void>();
    if (stage === "job") page.api.get.mockReturnValueOnce(pending.promise);
    else page.api.listEvents.mockImplementationOnce(() => {
      enteredEvents.resolve(undefined);
      return pending.promise;
    });
    const first = page.functions.loadAll();
    if (stage === "events") await enteredEvents.promise;
    const second = page.functions.loadAll();
    await second;
    const counts = Object.fromEntries(Object.entries(page.api).map(([name, api]) => [name, api.mock.calls.length]));
    pending.resolve(stage === "job" ? detailLoaders[0].response("old") : { items: ["old"] });
    await first;
    expect(Object.fromEntries(Object.entries(page.api).map(([name, api]) => [name, api.mock.calls.length]))).toEqual(counts);
  });

  it.each(detailLoaders)("路由 A→B→A 使 $loader 的旧响应失效", async (item) => {
    const page = setupDetail();
    const pending = deferred<unknown>();
    page.api[item.api].mockReturnValueOnce(pending.promise);
    const first = page.functions[item.loader]();
    page.state.jobId.value = "job-b";
    page.functions.resetPageStateForRouteChange();
    page.state.jobId.value = "job-a";
    page.functions.resetPageStateForRouteChange();
    const resetValue = page.state[item.data].value;
    pending.resolve(item.response("late"));
    await first;
    expect(page.state[item.data].value).toEqual(resetValue);
    expect(page.state[item.loading].value).toBe(false);
  });

  it.each(detailLoaders)("卸载使 $loader 的响应与清理失效，禁止再发起请求", async (item) => {
    const page = setupDetail();
    const pending = deferred<unknown>();
    page.api[item.api].mockReturnValueOnce(pending.promise);
    const before = page.state[item.data].value;
    const first = page.functions[item.loader]();
    page.unmount();
    pending.resolve(item.response("late"));
    await first;
    expect(page.state[item.data].value).toEqual(before);
    expect(page.state[item.loading].value).toBe(true);
    await page.functions[item.loader]();
    expect(page.api[item.api]).toHaveBeenCalledTimes(1);
  });

  it("慢轮询跨多个 tick 仍能落地，手动刷新可接管进行中的轮询", async () => {
    const page = setupDetail();
    const slow = deferred<unknown>();
    const oldPoll = deferred<unknown>();
    const manual = deferred<unknown>();
    page.api.get.mockReturnValueOnce(slow.promise).mockReturnValueOnce(oldPoll.promise).mockReturnValueOnce(manual.promise);
    page.functions.syncPolling();
    const tick = page.ticks[0];
    tick();
    tick();
    tick();
    expect(page.api.get).toHaveBeenCalledTimes(1);
    slow.resolve(detailLoaders[0].response("slow"));
    await vi.waitFor(() => {
      expect(page.state.job.value.id).toBe("slow");
      expect(page.state.loading.value || page.state.eventsLoading.value || page.state.callbackSummaryLoading.value).toBe(false);
    });
    tick();
    const manualRefresh = page.functions.loadAll();
    expect(page.api.get).toHaveBeenCalledTimes(3);
    manual.resolve(detailLoaders[0].response("manual"));
    await manualRefresh;
    expect(page.state.job.value.id).toBe("manual");
    oldPoll.resolve(detailLoaders[0].response("old-poll"));
    page.unmount();
  });

  it.each(["mounted", "route"])("同路由手动刷新保留 %s 的 retry 弹窗意图", async (entry) => {
    const page = setupDetail(true);
    const pendingEvents = deferred<unknown>();
    const enteredEvents = deferred<void>();
    const failedJob = { ...detailLoaders[0].response("job-a"), status: "failed" };
    page.route.query.retry = "1";
    page.api.get.mockResolvedValue(failedJob as never);
    page.api.listEvents.mockImplementationOnce(() => {
      enteredEvents.resolve(undefined);
      return pendingEvents.promise;
    });
    const initial = entry === "mounted" ? page.mounted[0]() : page.watchCallbacks[2]("job-a", "old");
    await enteredEvents.promise;
    await page.functions.loadAll();
    pendingEvents.resolve({ items: ["old"] });
    await initial;
    expect(page.openRetryDialog).toHaveBeenCalledOnce();
    expect(page.openRetryDialog).toHaveBeenCalledWith(failedJob);
    expect(page.api.listFiles).toHaveBeenCalledTimes(1);
    expect(page.api.getCallbackMessageSummary).toHaveBeenCalledTimes(1);
  });

  it.each(["mounted", "route"])("路由 A→B→A 后 %s 的旧入口不得消费新路由的 retry 意图", async (entry) => {
    const page = setupDetail(true);
    const pendingEvents = deferred<unknown>();
    const enteredEvents = deferred<void>();
    page.route.query.retry = "1";
    page.api.get.mockResolvedValue({ ...detailLoaders[0].response("job-a"), status: "failed" } as never);
    page.api.listEvents.mockImplementationOnce(() => {
      enteredEvents.resolve(undefined);
      return pendingEvents.promise;
    });
    const initial = entry === "mounted" ? page.mounted[0]() : page.watchCallbacks[2]("job-a", "old");
    await enteredEvents.promise;
    page.state.jobId.value = "job-b";
    page.functions.resetPageStateForRouteChange();
    page.state.jobId.value = "job-a";
    page.functions.resetPageStateForRouteChange();
    page.state.job.value = { ...detailLoaders[0].response("job-a"), status: "failed" };
    pendingEvents.resolve({ items: ["old"] });
    await initial;
    expect(page.openRetryDialog).not.toHaveBeenCalled();
    expect(page.api.listFiles).not.toHaveBeenCalled();
  });

  it.each(["mounted", "route"])("卸载后的 %s continuation 不得重启轮询或发起子请求", async (entry) => {
    const page = setupDetail(true);
    const pending = deferred<unknown>();
    page.api.get.mockReturnValueOnce(pending.promise);
    page.route.query.retry = "1";
    const request = entry === "mounted" ? page.mounted[0]() : page.watchCallbacks[2]("job-a", "old");
    page.state.job.value = { ...detailLoaders[0].response("job-a"), status: "failed" };
    page.unmount();
    pending.resolve(detailLoaders[0].response("job-a"));
    await request;
    expect(page.browser.setInterval).not.toHaveBeenCalled();
    expect(page.api.listEvents).not.toHaveBeenCalled();
    expect(page.openRetryDialog).not.toHaveBeenCalled();
  });
});
