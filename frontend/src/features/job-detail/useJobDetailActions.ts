import { computed, nextTick, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type {
  DocumentFileSummaryResponse,
  DocumentJobCloneRequest,
  DocumentJobConfigSummaryResponse,
  DocumentJobRetryRequest,
  DocumentJobResponse,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { formatDateTime, documentJobDownloadNotice, shouldShowDocumentJobAction } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { copyDownloadLink, openDownloadLink, type DownloadLinkNotice } from "@/utils/download";
import { configVersionId, findConfigOption } from "@/utils/configOptions";
import { usesTranslationResources } from "./jobDetailFormat";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailResources } from "./useJobDetailResources";
import type { Router } from "vue-router";
import type { useAuthStore } from "@/stores/auth";

export function useJobDetailActions(
  data: Pick<JobDetailData, "job" | "error" | "loadAll">,
  resources: Pick<
    JobDetailResources,
    | "termRuleProposalSetId"
    | "termRuleProposalVersion"
    | "translationTermProposalSetId"
    | "translationTermProposalVersion"
  >,
  router: Router,
  auth: ReturnType<typeof useAuthStore>,
) {
  const { job, error, loadAll } = data;

  const {
    termRuleProposalSetId,
    termRuleProposalVersion,
    translationTermProposalSetId,
    translationTermProposalVersion,
  } = resources;

  const downloadLoading = ref(false);
  const downloadingFileId = ref<string | null>(null);

  const retryLoading = ref(false);
  const cloneLoading = ref(false);
  const cancelLoading = ref(false);
  const archiveLoading = ref(false);
  const unarchiveLoading = ref(false);
  const deleteLoading = ref(false);
  const retryDialogVisible = ref(false);
  const cloneDialogVisible = ref(false);
  const configError = ref<ApiClientError | null>(null);

  const configLoading = ref(false);
  const configSummary = ref<DocumentJobConfigSummaryResponse | null>(null);

  const lastDownloadLink = ref<DownloadLinkNotice | null>(null);

  type RetryStrategy = "keep_original" | "use_latest_term_assets" | "select_term_assets";

  type CloneConfigStrategy = NonNullable<DocumentJobCloneRequest["config_strategy"]>;

  const retryDialog = reactive({
    job: null as DocumentJobResponse | null,
    reason: "frontend retry",
    strategy: "keep_original" as RetryStrategy,
    termRuleVersion: "",
    translationTermVersion: "",
  });

  const cloneDialog = reactive({
    job: null as DocumentJobResponse | null,
    reason: "frontend clone",
    strategy: "keep_source_snapshot" as CloneConfigStrategy,
    templateVersion: "",
    termRuleVersion: "",
    translationTermVersion: "",
    translationProfileVersion: "",
  });

  const isAdmin = computed(() => auth.user?.role === "admin");
  const selectedRetryTermRuleOption = computed(() =>
    findConfigOption(configSummary.value?.options.term_rule_sets || [], retryDialog.termRuleVersion),
  );

  const selectedRetryTranslationTermOption = computed(() =>
    findConfigOption(configSummary.value?.options.translation_term_sets || [], retryDialog.translationTermVersion),
  );

  const selectedCloneTemplateOption = computed(() =>
    findConfigOption(configSummary.value?.options.templates || [], cloneDialog.templateVersion),
  );

  const selectedCloneTermRuleOption = computed(() =>
    findConfigOption(configSummary.value?.options.term_rule_sets || [], cloneDialog.termRuleVersion),
  );

  const selectedCloneTranslationTermOption = computed(() =>
    findConfigOption(configSummary.value?.options.translation_term_sets || [], cloneDialog.translationTermVersion),
  );

  const selectedCloneTranslationProfileOption = computed(() =>
    findConfigOption(configSummary.value?.options.translation_profiles || [], cloneDialog.translationProfileVersion),
  );

  function openRetryDialog(target: DocumentJobResponse): void {
    retryDialog.job = target;
    retryDialog.reason = "frontend retry";
    retryDialog.strategy = "keep_original";
    retryDialog.termRuleVersion = "";
    retryDialog.translationTermVersion = "";
    retryDialogVisible.value = true;
    if (isAdmin.value && !configSummary.value) {
      void loadConfigSummary();
    }
  }

  function openCloneDialog(target: DocumentJobResponse): void {
    cloneDialog.job = target;
    cloneDialog.reason = "frontend clone";
    cloneDialog.strategy = "keep_source_snapshot";
    cloneDialog.templateVersion = "";
    cloneDialog.termRuleVersion = "";
    cloneDialog.translationTermVersion = "";
    cloneDialog.translationProfileVersion = "";
    cloneDialogVisible.value = true;
    if (isAdmin.value && !configSummary.value) {
      void loadConfigSummary();
    }
  }

  function proposalBaseQuery(tab: "new" | "translation-new"): Record<string, string> {
    if (!job.value) {
      return { tab };
    }
    return {
      tab,
      source_job_id: job.value.id,
      source_file_id: job.value.source_file_id,
    };
  }

  function appendQueryValue(query: Record<string, string>, key: string, value?: string | null): void {
    if (value) {
      query[key] = value;
    }
  }

  function openTermRuleProposal(): void {
    const query = proposalBaseQuery("new");
    appendQueryValue(query, "observed_term_rule_set_id", termRuleProposalSetId.value);
    appendQueryValue(query, "observed_term_rule_version", termRuleProposalVersion.value);
    void router.push({ name: "term-proposals", query });
  }

  function openTranslationTermProposal(): void {
    const query = proposalBaseQuery("translation-new");
    appendQueryValue(query, "observed_translation_term_set_id", translationTermProposalSetId.value);
    appendQueryValue(query, "observed_translation_term_version", translationTermProposalVersion.value);
    void router.push({ name: "term-proposals", query });
  }

  function openTranslationQa(): void {
    if (!job.value) {
      return;
    }
    void router.push({ name: "job-translation-qa", params: { jobId: job.value.id } });
  }

  async function handleDownload(target: DocumentJobResponse): Promise<void> {
    downloadLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.createDownloadUrl(target.id);
      lastDownloadLink.value = {
        label: `任务 ${target.id} 的下载链接已生成`,
        url: response.download_url,
        expiresAt: response.expires_at,
        fileName: response.file.original_filename,
        notice: documentJobDownloadNotice(response),
      };
      await nextTick();
      const opened = openDownloadLink(response.download_url);
      if (opened) {
        ElMessage.warning(`${lastDownloadLink.value.notice}。下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
      } else {
        ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      downloadLoading.value = false;
    }
  }

  async function handleFileDownload(file: DocumentFileSummaryResponse): Promise<void> {
    if (!job.value) {
      return;
    }
    downloadingFileId.value = file.id;
    error.value = null;
    try {
      const response = await documentJobsApi.createDownloadUrl(job.value.id, file.id);
      lastDownloadLink.value = {
        label: `${file.original_filename} 的下载链接已生成`,
        url: response.download_url,
        expiresAt: response.expires_at,
        fileName: response.file.original_filename,
        notice: documentJobDownloadNotice(response, response.file.file_type === "generated_word"),
      };
      await nextTick();
      const opened = openDownloadLink(response.download_url);
      if (opened) {
        if (lastDownloadLink.value.notice) {
          ElMessage.warning(`${lastDownloadLink.value.notice}。下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
        } else {
          ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
        }
      } else {
        ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
      }
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      downloadingFileId.value = null;
    }
  }

  async function copyLastDownloadLink(): Promise<void> {
    if (!lastDownloadLink.value) {
      return;
    }
    const copied = await copyDownloadLink(lastDownloadLink.value.url);
    if (copied) {
      ElMessage.success("下载链接已复制。");
      return;
    }
    ElMessage.warning("当前浏览器不支持自动复制。");
  }

  function handleRetry(target: DocumentJobResponse): void {
    openRetryDialog(target);
  }

  function handleClone(target: DocumentJobResponse): void {
    openCloneDialog(target);
  }

  async function handleCancel(target: DocumentJobResponse): Promise<void> {
    try {
      await ElMessageBox.confirm(
        "取消会将任务标记为 canceled 并停止后续处理；如果任务已进入外部服务，系统不承诺强制中断该外部处理。文件和事件记录会保留。",
        "取消任务",
        {
          confirmButtonText: "确认取消",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    cancelLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.cancel(target.id);
      job.value = response.job;
      ElMessage.success("任务已取消。");
      await loadAll();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cancelLoading.value = false;
    }
  }

  async function handleArchive(target: DocumentJobResponse): Promise<void> {
    try {
      await ElMessageBox.confirm(
        "归档只会把终态任务从默认列表隐藏，不会删除源文件、结果文件或事件记录。开启列表的“含归档”后仍可查看。",
        "归档任务",
        {
          confirmButtonText: "确认归档",
          cancelButtonText: "返回",
          type: "info",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    archiveLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.archive(target.id);
      job.value = response.job;
      ElMessage.success("任务已归档。");
      await loadAll();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      archiveLoading.value = false;
    }
  }

  async function handleUnarchive(target: DocumentJobResponse): Promise<void> {
    try {
      await ElMessageBox.confirm(
        "取消归档会让任务重新出现在默认列表中，不会修改源文件、结果文件或事件记录。",
        "取消归档",
        {
          confirmButtonText: "确认取消归档",
          cancelButtonText: "返回",
          type: "info",
        },
      );
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
      return;
    }
    unarchiveLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.unarchive(target.id);
      job.value = response.job;
      ElMessage.success("任务已取消归档。");
      await loadAll();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      unarchiveLoading.value = false;
    }
  }

  async function handleDelete(target: DocumentJobResponse): Promise<void> {
    if (!shouldShowDocumentJobAction(target, "delete")) {
      return;
    }
    deleteLoading.value = true;
    error.value = null;
    try {
      const preview = await documentJobsApi.previewDelete(target.id);
      const deleteCount = preview.totals.delete || 0;
      const keepCount = preview.totals.keep || 0;
      await ElMessageBox.confirm(
        `删除任务会隐藏该任务并清理可安全删除的关联文件。将删除 ${deleteCount} 个文件，保留 ${keepCount} 个文件；任务元数据（metadata）、事件和审计记录（audit）会保留。`,
        "删除任务",
        {
          confirmButtonText: "确认删除",
          cancelButtonText: "返回",
          type: "warning",
        },
      );
      await documentJobsApi.delete(target.id, {
        preview_hash: preview.preview_hash,
      });
      ElMessage.success("任务已删除。");
      await router.push({ name: "jobs" });
    } catch (caught) {
      if (caught === "cancel" || caught === "close") {
        return;
      }
      error.value = normalizeApiError(caught);
    } finally {
      deleteLoading.value = false;
    }
  }

  async function submitRetryDialog(): Promise<void> {
    if (!retryDialog.job) {
      return;
    }
    await submitRetry(retryDialog.job, buildRetryPayload());
    retryDialogVisible.value = false;
  }

  async function submitCloneDialog(): Promise<void> {
    if (!cloneDialog.job) {
      return;
    }
    cloneLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.clone(cloneDialog.job.id, buildClonePayload());
      cloneDialogVisible.value = false;
      ElMessage.success("已创建新任务。");
      await router.push({ name: "job-detail", params: { jobId: response.job_id } });
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      cloneLoading.value = false;
    }
  }

  function buildRetryPayload(): DocumentJobRetryRequest {
    const payload: DocumentJobRetryRequest = {
      reason: retryDialog.reason || "frontend retry",
    };
    if (!isAdmin.value) {
      return payload;
    }
    if (retryDialog.strategy === "use_latest_term_assets") {
      payload.use_latest_term_assets = true;
      return payload;
    }
    if (retryDialog.strategy !== "select_term_assets") {
      return payload;
    }
    if (selectedRetryTermRuleOption.value) {
      payload.term_rule_set_id = selectedRetryTermRuleOption.value.resource_id;
      payload.term_rule_set_version = selectedRetryTermRuleOption.value.version;
    }
    if (usesTranslationResources(retryDialog.job) && selectedRetryTranslationTermOption.value) {
      payload.translation_term_set_id = selectedRetryTranslationTermOption.value.resource_id;
      payload.translation_term_version = selectedRetryTranslationTermOption.value.version;
    }
    return payload;
  }

  function buildClonePayload(): DocumentJobCloneRequest {
    const payload: DocumentJobCloneRequest = {
      reason: cloneDialog.reason || "frontend clone",
      config_strategy: cloneDialog.strategy,
    };
    if (!isAdmin.value || cloneDialog.strategy !== "select_published_versions") {
      return payload;
    }
    if (selectedCloneTemplateOption.value) {
      payload.template_version_id = configVersionId(selectedCloneTemplateOption.value);
    }
    if (selectedCloneTermRuleOption.value) {
      payload.term_rule_set_id = selectedCloneTermRuleOption.value.resource_id;
      payload.term_rule_set_version = selectedCloneTermRuleOption.value.version;
    }
    if (usesTranslationResources(cloneDialog.job) && selectedCloneTranslationTermOption.value) {
      payload.translation_term_set_id = selectedCloneTranslationTermOption.value.resource_id;
      payload.translation_term_version = selectedCloneTranslationTermOption.value.version;
    }
    if (usesTranslationResources(cloneDialog.job) && selectedCloneTranslationProfileOption.value) {
      payload.translation_profile_id = selectedCloneTranslationProfileOption.value.resource_id;
      payload.translation_profile_version = selectedCloneTranslationProfileOption.value.version;
    }
    return payload;
  }

  async function submitRetry(
    target: DocumentJobResponse,
    payload: Parameters<typeof documentJobsApi.retry>[1],
  ): Promise<void> {
    retryLoading.value = true;
    error.value = null;
    try {
      const response = await documentJobsApi.retry(target.id, payload);
      job.value = response.job;
      ElMessage.success("已提交重试。");
      await loadAll();
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      retryLoading.value = false;
    }
  }

  async function loadConfigSummary(): Promise<void> {
    configLoading.value = true;
    configError.value = null;
    try {
      configSummary.value = await documentJobsApi.getConfigSummary();
    } catch (caught) {
      configError.value = normalizeApiError(caught);
    } finally {
      configLoading.value = false;
    }
  }

  function resetForRouteChange(): void {
    configError.value = null;
    lastDownloadLink.value = null;
    retryDialogVisible.value = false;
    cloneDialogVisible.value = false;
  }

  return {
    downloadLoading,
    downloadingFileId,
    retryLoading,
    cloneLoading,
    cancelLoading,
    archiveLoading,
    unarchiveLoading,
    deleteLoading,
    retryDialogVisible,
    cloneDialogVisible,
    configError,
    configLoading,
    configSummary,
    lastDownloadLink,
    retryDialog,
    cloneDialog,
    isAdmin,
    openRetryDialog,
    openCloneDialog,
    openTermRuleProposal,
    openTranslationTermProposal,
    openTranslationQa,
    handleDownload,
    handleFileDownload,
    copyLastDownloadLink,
    handleRetry,
    handleClone,
    handleCancel,
    handleArchive,
    handleUnarchive,
    handleDelete,
    submitRetryDialog,
    submitCloneDialog,
    resetForRouteChange,
  };
}

export type JobDetailActions = ReturnType<typeof useJobDetailActions>;
