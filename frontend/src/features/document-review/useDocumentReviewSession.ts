// 文件：frontend/src/features/document-review/useDocumentReviewSession.ts
// 用途：统一文档复核工作台（/jobs/:jobId/review）的单数据源 Owner，统筹质量、块详情、表格参考图、预览页与复核提交。
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { RouteLocationNormalizedLoaded, Router } from "vue-router";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobResponse,
  DocumentJobReviewStatus,
  DocumentJobTableReferenceListResponse,
  DocumentJobTableReferenceResponse,
  DocumentPreviewResponse,
  DocumentQualityPagesResponse,
  DocumentQualityResponse,
  DocumentQualitySourceResponse,
  DocumentQualityTableItemResponse,
  DocumentQualityTablesResponse,
  DocumentReviewBlockDetailResponse,
  DocumentReviewBlockFlagResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewBlocksResponse,
  DocumentReviewHistoryResponse,
  DocumentReviewUpdateRequest,
  QualityIssue,
  ReviewExpectedSourceRequest,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { documentJobModeSupportsTranslationQa, getJobSourceFilename } from "@/utils/format";
import { openDownloadLink } from "@/utils/download";
import { isEditableShortcutTarget } from "@/utils/keyboardShortcuts";
import {
  buildExpectedSource,
  isTableSemanticsConflictReason,
  languagePairFromJobMode,
} from "./documentReviewFormat";

export type ReviewOutlineFilter = {
  problem: "all" | "flagged";
  blockType: "" | DocumentReviewBlockItemResponse["block_type"];
  severity: "all" | DocumentReviewBlockFlagResponse["severity"];
  sourcePageIndex: number | null;
};

export function useDocumentReviewSession(
  route: Pick<RouteLocationNormalizedLoaded, "params" | "query" | "fullPath">,
  router: Pick<Router, "push" | "replace">,
  options: {
    isOverlayOpen?: () => boolean;
  } = {},
) {
  const jobId = computed(() => String(route.params.jobId || ""));

  const job = ref<DocumentJobResponse | null>(null);
  const quality = ref<DocumentQualityResponse | null>(null);
  const blocksResponse = ref<DocumentReviewBlocksResponse | null>(null);
  const tablesResponse = ref<DocumentQualityTablesResponse | null>(null);
  const pagesResponse = ref<DocumentQualityPagesResponse | null>(null);
  const previewResponse = ref<DocumentPreviewResponse | null>(null);
  const tableReferencesResponse = ref<DocumentJobTableReferenceListResponse | null>(null);

  const selectedBlockId = ref<string>("");
  const blockDetail = ref<DocumentReviewBlockDetailResponse | null>(null);

  const reviewHistory = ref<DocumentReviewHistoryResponse | null>(null);
  const reviewHistoryOpen = ref(false);
  const reviewHistoryLoading = ref(false);
  const reviewHistoryError = ref<ApiClientError | null>(null);

  const loading = ref(false);
  const blocksLoading = ref(false);
  const blockDetailLoading = ref(false);
  const submittingReview = ref(false);
  const openingSourcePdf = ref(false);
  const downloadingDraft = ref(false);

  const pageError = ref<ApiClientError | null>(null);
  const blocksError = ref<ApiClientError | null>(null);
  const blockDetailError = ref<ApiClientError | null>(null);
  const previewError = ref<ApiClientError | null>(null);
  const tablesError = ref<ApiClientError | null>(null);
  const pagesError = ref<ApiClientError | null>(null);
  const reviewSubmitError = ref<ApiClientError | null>(null);
  const reviewConflictActive = ref(false);

  const outlineFilter = reactive<ReviewOutlineFilter>({
    problem: "all",
    blockType: "",
    severity: "all",
    sourcePageIndex: null,
  });

  const reviewForm = reactive<{
    status: DocumentJobReviewStatus;
    issueType: QualityIssue | null;
    note: string;
    acknowledgeTableSemantics: boolean;
  }>({
    status: "unreviewed",
    issueType: null,
    note: "",
    acknowledgeTableSemantics: false,
  });

  // Word 预览页控制状态
  const activePreviewPageIndex = ref<number>(0);
  const previewZoom = ref<number>(100);
  const previewImageUrls = reactive<Record<string, string>>({});
  const previewImageLoading = reactive<Record<string, boolean>>({});
  const previewImageErrors = reactive<Record<string, string>>({});

  // 表格参考图 ObjectURL 缓存（卸载或切任务时全部 revokeObjectURL）
  const tableRefObjectUrls = reactive<Record<string, string>>({});
  const tableRefLoading = reactive<Record<string, boolean>>({});
  const tableRefErrors = reactive<Record<string, string>>({});

  let disposed = false;
  let sessionSeq = 0;
  let blocksSeq = 0;
  let detailSeq = 0;
  let historySeq = 0;

  const isTranslationJob = computed(() => Boolean(job.value && documentJobModeSupportsTranslationQa(job.value.mode)));
  const languagePair = computed(() => languagePairFromJobMode(job.value?.mode));
  const sourceFilename = computed(() => (job.value ? getJobSourceFilename(job.value) : jobId.value || "文档复核"));

  const observedSource = computed<DocumentQualitySourceResponse | null>(() =>
    quality.value?.source ?? blocksResponse.value?.source ?? previewResponse.value?.source ?? null,
  );

  const expectedSource = computed<ReviewExpectedSourceRequest | null>(() =>
    observedSource.value ? buildExpectedSource(observedSource.value) : null,
  );

  const contentSnapshotId = computed<string | null>(() => blocksResponse.value?.content_snapshot.snapshot_id ?? null);
  const sourcePdfFileId = computed<string | null>(
    () => blocksResponse.value?.content_snapshot.source_pdf_file_id ?? job.value?.source_file_id ?? null,
  );

  const blocks = computed<DocumentReviewBlockItemResponse[]>(() => blocksResponse.value?.items ?? []);
  const selectedBlock = computed<DocumentReviewBlockItemResponse | null>(
    () => blocks.value.find((item) => item.block_id === selectedBlockId.value) ?? blockDetail.value?.block ?? null,
  );

  const availableSourcePages = computed<number[]>(() => {
    const pages = new Set<number>();
    for (const item of blocks.value) {
      for (const span of item.source_spans) {
        if (span.source_page_index !== null) {
          pages.add(span.source_page_index);
        }
      }
    }
    return Array.from(pages).sort((a, b) => a - b);
  });

  const currentSourcePageNumber = computed<number | null>(() => {
    const spans = selectedBlock.value?.source_spans ?? [];
    for (const span of spans) {
      if (span.source_page_index !== null) {
        return span.source_page_index + 1;
      }
    }
    return null;
  });

  const previewPages = computed(() => previewResponse.value?.items ?? []);
  const currentPreviewPage = computed(() =>
    previewPages.value.find((item) => item.page_index === activePreviewPageIndex.value)
    ?? previewPages.value[0]
    ?? null,
  );
  const currentPreviewImageUrl = computed(() =>
    currentPreviewPage.value ? previewImageUrls[currentPreviewPage.value.file_id] || "" : "",
  );
  const currentPreviewImageLoading = computed(() =>
    currentPreviewPage.value ? Boolean(previewImageLoading[currentPreviewPage.value.file_id]) : false,
  );
  const currentPreviewImageError = computed(() =>
    currentPreviewPage.value ? previewImageErrors[currentPreviewPage.value.file_id] || "" : "",
  );

  const tableItemsById = computed<Record<string, DocumentQualityTableItemResponse>>(() => {
    const map: Record<string, DocumentQualityTableItemResponse> = {};
    for (const item of tablesResponse.value?.items ?? []) {
      map[item.table_id] = item;
    }
    return map;
  });

  const selectedBlockTables = computed<DocumentQualityTableItemResponse[]>(() => {
    const fromParts = (blockDetail.value?.items ?? [])
      .map((part) => part.table)
      .filter((item): item is DocumentQualityTableItemResponse => Boolean(item));
    const seen = new Set(fromParts.map((item) => item.table_id));
    for (const tableId of selectedBlock.value?.table_ids ?? []) {
      const matched = tableItemsById.value[tableId];
      if (matched && !seen.has(matched.table_id)) {
        seen.add(matched.table_id);
        fromParts.push(matched);
      }
    }
    return fromParts;
  });

  const selectedBlockReferences = computed<DocumentJobTableReferenceResponse[]>(() => {
    const list: DocumentJobTableReferenceResponse[] = [];
    const seen = new Set<string>();
    for (const part of blockDetail.value?.items ?? []) {
      if (part.reference) {
        const key = `${part.reference.fragment_id}:${part.reference.asset_id || ""}`;
        if (!seen.has(key)) {
          seen.add(key);
          list.push(part.reference);
        }
      }
    }
    if (selectedBlock.value) {
      for (const refItem of tableReferencesResponse.value?.items ?? []) {
        if (refItem.block_id === selectedBlock.value.block_id) {
          const key = `${refItem.fragment_id}:${refItem.asset_id || ""}`;
          if (!seen.has(key)) {
            seen.add(key);
            list.push(refItem);
          }
        }
      }
    }
    return list;
  });

  const tableSemanticsReportSha256 = computed<string | null>(
    () => tablesResponse.value?.report?.report_sha256 ?? null,
  );

  const tableSemanticsFindingsCount = computed<number>(() => {
    let count = 0;
    for (const item of tablesResponse.value?.items ?? []) {
      count += item.value_column_findings?.length ?? 0;
      count += item.unresolved_value_columns?.length ?? 0;
    }
    return count;
  });

  const currentReview = computed(() => quality.value?.review ?? null);
  const hasTableSemanticsConflict = computed(() =>
    isTableSemanticsConflictReason(currentReview.value?.validity_reason ?? null),
  );
  const needsTableSemanticsConfirmation = computed(() =>
    tableSemanticsFindingsCount.value > 0 || hasTableSemanticsConflict.value,
  );
  const mustTickTableSemanticsToApprove = computed(() =>
    reviewForm.status === "approved" && needsTableSemanticsConfirmation.value,
  );
  const canSubmitReview = computed(() => {
    if (!expectedSource.value || submittingReview.value || loading.value) {
      return false;
    }
    if (mustTickTableSemanticsToApprove.value) {
      return Boolean(reviewForm.acknowledgeTableSemantics && tableSemanticsReportSha256.value);
    }
    return true;
  });

  const effectiveActions = computed(() => quality.value?.available_actions ?? job.value?.available_actions ?? null);
  const canRequestNewGeneration = computed(() => effectiveActions.value?.new_generation?.enabled === true);
  const newGenerationDisabledReason = computed(
    () => effectiveActions.value?.new_generation?.disabled_reason ?? "",
  );

  function revokeAllTableRefUrls(): void {
    for (const key of Object.keys(tableRefObjectUrls)) {
      const url = tableRefObjectUrls[key];
      if (url && typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(url);
      }
      delete tableRefObjectUrls[key];
      delete tableRefLoading[key];
      delete tableRefErrors[key];
    }
  }

  function clearPreviewImageCache(): void {
    for (const key of Object.keys(previewImageUrls)) {
      delete previewImageUrls[key];
    }
    for (const key of Object.keys(previewImageLoading)) {
      delete previewImageLoading[key];
    }
    for (const key of Object.keys(previewImageErrors)) {
      delete previewImageErrors[key];
    }
  }

  function syncReviewFormFromServer(): void {
    const serverReview = quality.value?.review;
    if (!serverReview) {
      return;
    }
    reviewForm.status = serverReview.status;
    reviewForm.issueType = serverReview.issue_type;
    reviewForm.note = serverReview.note || "";
    const ackHash = serverReview.binding?.acknowledged_table_semantics_report_sha256 ?? null;
    reviewForm.acknowledgeTableSemantics = Boolean(
      ackHash && tableSemanticsReportSha256.value && ackHash === tableSemanticsReportSha256.value,
    );
  }

  async function ensurePreviewPageImage(pageIndex: number): Promise<void> {
    const pageItem = previewPages.value.find((item) => item.page_index === pageIndex);
    if (!pageItem) {
      return;
    }
    const fileId = pageItem.file_id;
    if (previewImageUrls[fileId] || previewImageLoading[fileId]) {
      return;
    }
    const targetJobId = jobId.value;
    previewImageLoading[fileId] = true;
    previewImageErrors[fileId] = "";
    try {
      const response = await documentJobsApi.createDownloadUrl(targetJobId, fileId);
      if (!disposed && targetJobId === jobId.value) {
        previewImageUrls[fileId] = response.download_url;
      }
    } catch (caught) {
      if (!disposed && targetJobId === jobId.value) {
        previewImageErrors[fileId] = normalizeApiError(caught).message;
      }
    } finally {
      if (!disposed && targetJobId === jobId.value) {
        previewImageLoading[fileId] = false;
      }
    }
  }

  async function loadTableReferenceImages(refs: DocumentJobTableReferenceResponse[]): Promise<void> {
    const targetJobId = jobId.value;
    const loadable = refs.filter(
      (item) => item.availability === "available" && item.display_supported && item.content_path,
    );
    await Promise.all(
      loadable.map(async (item) => {
        const path = item.content_path!;
        if (tableRefObjectUrls[path] || tableRefLoading[path]) {
          return;
        }
        tableRefLoading[path] = true;
        tableRefErrors[path] = "";
        try {
          const blob = await documentJobsApi.getTableReferenceContentBlob(path);
          if (disposed || targetJobId !== jobId.value) {
            return;
          }
          if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
            tableRefObjectUrls[path] = URL.createObjectURL(blob);
          }
        } catch (caught) {
          if (!disposed && targetJobId === jobId.value) {
            tableRefErrors[path] = normalizeApiError(caught).message;
          }
        } finally {
          if (!disposed && targetJobId === jobId.value) {
            tableRefLoading[path] = false;
          }
        }
      }),
    );
  }

  async function loadBlockDetail(blockId: string, append = false): Promise<void> {
    const targetJobId = jobId.value;
    const snapshotId = contentSnapshotId.value;
    if (!targetJobId || !blockId || !snapshotId) {
      return;
    }
    const seq = ++detailSeq;
    const cursor = append ? blockDetail.value?.next_cursor ?? undefined : undefined;
    if (append && !cursor) {
      return;
    }
    blockDetailLoading.value = true;
    blockDetailError.value = null;
    if (!append) {
      blockDetail.value = null;
    }
    try {
      const response = await documentJobsApi.getReviewBlockDetail(targetJobId, blockId, {
        snapshot_id: snapshotId,
        limit: 50,
        ...(cursor ? { cursor } : {}),
      });
      if (disposed || seq !== detailSeq || targetJobId !== jobId.value) {
        return;
      }
      blockDetail.value = append && blockDetail.value
        ? { ...response, items: [...blockDetail.value.items, ...response.items] }
        : response;
      void loadTableReferenceImages(selectedBlockReferences.value);
    } catch (caught) {
      if (!disposed && seq === detailSeq && targetJobId === jobId.value) {
        blockDetailError.value = normalizeApiError(caught);
      }
    } finally {
      if (!disposed && seq === detailSeq && targetJobId === jobId.value) {
        blockDetailLoading.value = false;
      }
    }
  }

  function syncPreviewToBlock(block: DocumentReviewBlockItemResponse | null): void {
    if (!block || !previewPages.value.length) {
      return;
    }
    // 严格只使用后端返回的 preview_page_index，绝不把 source_page_index 当作 Word 预览页码。
    const targetPreviewIndex = block.location.preview_page_index;
    if (targetPreviewIndex !== null) {
      const matched = previewPages.value.find((item) => item.page_index === targetPreviewIndex);
      if (matched) {
        activePreviewPageIndex.value = matched.page_index;
        void ensurePreviewPageImage(matched.page_index);
      }
    }
  }

  async function selectBlock(blockId: string, syncQuery = true): Promise<void> {
    if (!blockId) {
      selectedBlockId.value = "";
      blockDetail.value = null;
      return;
    }
    selectedBlockId.value = blockId;
    if (syncQuery && route.query.block !== blockId) {
      void router.replace({
        query: { ...route.query, block: blockId },
      });
    }
    const block = blocks.value.find((item) => item.block_id === blockId) ?? null;
    syncPreviewToBlock(block);
    await loadBlockDetail(blockId, false);
  }

  function stepBlock(delta: 1 | -1): void {
    if (!blocks.value.length) {
      return;
    }
    const currentIndex = blocks.value.findIndex((item) => item.block_id === selectedBlockId.value);
    const nextIndex = currentIndex === -1
      ? 0
      : Math.min(Math.max(currentIndex + delta, 0), blocks.value.length - 1);
    const nextBlock = blocks.value[nextIndex];
    if (nextBlock && nextBlock.block_id !== selectedBlockId.value) {
      void selectBlock(nextBlock.block_id);
    }
  }

  function setPreviewPageIndex(pageIndex: number): void {
    const matched = previewPages.value.find((item) => item.page_index === pageIndex);
    if (!matched) {
      return;
    }
    activePreviewPageIndex.value = matched.page_index;
    void ensurePreviewPageImage(matched.page_index);
  }

  function stepPreviewPage(delta: 1 | -1): void {
    if (!previewPages.value.length) {
      return;
    }
    const idx = previewPages.value.findIndex((item) => item.page_index === activePreviewPageIndex.value);
    const nextIdx = idx === -1 ? 0 : Math.min(Math.max(idx + delta, 0), previewPages.value.length - 1);
    const nextPage = previewPages.value[nextIdx];
    if (nextPage) {
      setPreviewPageIndex(nextPage.page_index);
    }
  }

  async function loadBlocks(append = false): Promise<void> {
    const targetJobId = jobId.value;
    if (!targetJobId) {
      return;
    }
    const seq = ++blocksSeq;
    const cursor = append ? blocksResponse.value?.next_cursor ?? undefined : undefined;
    if (append && !cursor) {
      return;
    }
    blocksLoading.value = true;
    blocksError.value = null;
    try {
      const response = await documentJobsApi.listReviewBlocks(targetJobId, {
        limit: 50,
        problem: outlineFilter.problem,
        severity: outlineFilter.severity,
        ...(outlineFilter.blockType ? { block_type: outlineFilter.blockType } : {}),
        ...(outlineFilter.sourcePageIndex !== null ? { source_page_index: outlineFilter.sourcePageIndex } : {}),
        ...(cursor ? { cursor } : {}),
      });
      if (disposed || seq !== blocksSeq || targetJobId !== jobId.value) {
        return;
      }
      blocksResponse.value = append && blocksResponse.value
        ? { ...response, items: [...blocksResponse.value.items, ...response.items] }
        : response;

      if (!append) {
        const queryBlockId = typeof route.query.block === "string" ? route.query.block.trim() : "";
        const preferred =
          (queryBlockId && response.items.find((item) => item.block_id === queryBlockId)?.block_id)
          || (selectedBlockId.value && response.items.find((item) => item.block_id === selectedBlockId.value)?.block_id)
          || response.items[0]?.block_id
          || "";
        if (preferred) {
          await selectBlock(preferred, false);
        } else {
          selectedBlockId.value = "";
          blockDetail.value = null;
        }
      }
    } catch (caught) {
      if (!disposed && seq === blocksSeq && targetJobId === jobId.value) {
        blocksError.value = normalizeApiError(caught);
      }
    } finally {
      if (!disposed && seq === blocksSeq && targetJobId === jobId.value) {
        blocksLoading.value = false;
      }
    }
  }

  async function loadAll(preserveDraft = false): Promise<void> {
    const targetJobId = jobId.value;
    if (!targetJobId) {
      return;
    }
    const seq = ++sessionSeq;
    loading.value = true;
    pageError.value = null;
    blocksError.value = null;
    tablesError.value = null;
    pagesError.value = null;
    previewError.value = null;
    reviewSubmitError.value = null;
    reviewConflictActive.value = false;
    clearPreviewImageCache();

    try {
      const [jobRes, qualityRes, tablesRes, pagesRes, previewRes, tableRefsRes] = await Promise.allSettled([
        documentJobsApi.get(targetJobId),
        documentJobsApi.getQuality(targetJobId),
        documentJobsApi.listQualityTables(targetJobId, { limit: 100 }),
        documentJobsApi.listQualityPages(targetJobId, { limit: 100 }),
        documentJobsApi.getPreview(targetJobId, { limit: 100 }),
        documentJobsApi.listTableReferences(targetJobId),
      ]);

      if (disposed || seq !== sessionSeq || targetJobId !== jobId.value) {
        return;
      }

      if (jobRes.status === "fulfilled") {
        job.value = jobRes.value;
      } else {
        pageError.value = normalizeApiError(jobRes.reason);
      }

      if (qualityRes.status === "fulfilled") {
        quality.value = qualityRes.value;
      } else if (!pageError.value) {
        pageError.value = normalizeApiError(qualityRes.reason);
      }

      if (tablesRes.status === "fulfilled") {
        tablesResponse.value = tablesRes.value;
      } else {
        tablesResponse.value = null;
        tablesError.value = normalizeApiError(tablesRes.reason);
      }

      if (pagesRes.status === "fulfilled") {
        pagesResponse.value = pagesRes.value;
      } else {
        pagesResponse.value = null;
        pagesError.value = normalizeApiError(pagesRes.reason);
      }

      if (previewRes.status === "fulfilled") {
        previewResponse.value = previewRes.value;
        if (previewRes.value.items.length > 0) {
          const firstPage = previewRes.value.items[0].page_index;
          activePreviewPageIndex.value = firstPage;
          void ensurePreviewPageImage(firstPage);
        }
      } else {
        previewResponse.value = null;
        previewError.value = normalizeApiError(previewRes.reason);
      }

      if (tableRefsRes.status === "fulfilled") {
        tableReferencesResponse.value = tableRefsRes.value;
      } else {
        tableReferencesResponse.value = null;
      }

      if (!preserveDraft) {
        syncReviewFormFromServer();
      }

      await loadBlocks(false);
    } finally {
      if (!disposed && seq === sessionSeq && targetJobId === jobId.value) {
        loading.value = false;
      }
    }
  }

  async function submitReview(): Promise<boolean> {
    if (!expectedSource.value) {
      ElMessage.warning("尚未获取到当前主件来源，请先刷新工作台。");
      return false;
    }
    if (mustTickTableSemanticsToApprove.value && (!reviewForm.acknowledgeTableSemantics || !tableSemanticsReportSha256.value)) {
      ElMessage.warning("请先勾选确认已核对表格语义归属报告后再批准复核。");
      return false;
    }
    const targetJobId = jobId.value;
    submittingReview.value = true;
    reviewSubmitError.value = null;
    reviewConflictActive.value = false;

    const payload: DocumentReviewUpdateRequest = {
      status: reviewForm.status,
      issue_type: reviewForm.issueType,
      note: reviewForm.note.trim() || null,
      expected_source: expectedSource.value,
      // 后端约束：非 approved 状态严禁携带 acknowledged_table_semantics_report_sha256。
      ...(reviewForm.status === "approved" && reviewForm.acknowledgeTableSemantics && tableSemanticsReportSha256.value
        ? { acknowledged_table_semantics_report_sha256: tableSemanticsReportSha256.value }
        : {}),
    };

    try {
      const response = await documentJobsApi.submitReview(targetJobId, payload);
      if (disposed || targetJobId !== jobId.value) {
        return false;
      }
      if (quality.value) {
        quality.value = {
          ...quality.value,
          source: response.source,
          review: response.review,
          available_actions: response.available_actions,
          states: {
            ...quality.value.states,
            review_status: response.review.status,
          },
        };
      }
      if (job.value) {
        job.value = {
          ...job.value,
          review_status: response.review.status,
          available_actions: {
            ...job.value.available_actions,
            ...response.available_actions,
          },
        };
      }
      ElMessage.success(`复核结论已提交（第 #${response.accepted_sequence} 次记录）。`);
      return true;
    } catch (caught) {
      if (disposed || targetJobId !== jobId.value) {
        return false;
      }
      const normalized = normalizeApiError(caught);
      reviewSubmitError.value = normalized;
      if (normalized.status === 409) {
        // 409 冲突时保留用户已填状态与备注，绝不自动覆盖或盲目重试。
        reviewConflictActive.value = true;
      }
      return false;
    } finally {
      if (!disposed && targetJobId === jobId.value) {
        submittingReview.value = false;
      }
    }
  }

  async function loadReviewHistory(append = false): Promise<void> {
    const targetJobId = jobId.value;
    if (!targetJobId) {
      return;
    }
    const cursor = append ? reviewHistory.value?.next_cursor ?? undefined : undefined;
    if (append && !cursor) {
      return;
    }
    const seq = ++historySeq;
    reviewHistoryLoading.value = true;
    reviewHistoryError.value = null;
    try {
      const response = await documentJobsApi.listReviewHistory(targetJobId, {
        limit: 50,
        ...(cursor ? { cursor } : {}),
      });
      if (disposed || seq !== historySeq || targetJobId !== jobId.value) {
        return;
      }
      reviewHistory.value = append && reviewHistory.value
        ? { ...response, items: [...reviewHistory.value.items, ...response.items] }
        : response;
    } catch (caught) {
      if (!disposed && seq === historySeq && targetJobId === jobId.value) {
        reviewHistoryError.value = normalizeApiError(caught);
      }
    } finally {
      if (!disposed && seq === historySeq && targetJobId === jobId.value) {
        reviewHistoryLoading.value = false;
      }
    }
  }

  function openReviewHistory(): void {
    reviewHistoryOpen.value = true;
    void loadReviewHistory(false);
  }

  async function openSourcePdf(): Promise<void> {
    const fileId = sourcePdfFileId.value;
    if (!fileId || !jobId.value) {
      ElMessage.warning("当前任务暂无可打开的源 PDF 文件。");
      return;
    }
    openingSourcePdf.value = true;
    try {
      const response = await documentJobsApi.createDownloadUrl(jobId.value, fileId);
      const pageNum = currentSourcePageNumber.value;
      const targetUrl = pageNum ? `${response.download_url}#page=${pageNum}` : response.download_url;
      const opened = openDownloadLink(targetUrl);
      if (!opened) {
        ElMessage.warning("浏览器拦截了新窗口，请允许弹窗后重试打开源 PDF。");
      }
    } catch (caught) {
      ElMessage.error(normalizeApiError(caught).message);
    } finally {
      openingSourcePdf.value = false;
    }
  }

  async function downloadInternalDraft(): Promise<void> {
    if (!jobId.value) {
      return;
    }
    downloadingDraft.value = true;
    try {
      const response = await documentJobsApi.createDownloadUrl(jobId.value);
      const opened = openDownloadLink(response.download_url);
      if (opened) {
        ElMessage.warning("已打开内部草稿 Word 下载链接（仅供内部核对，非正式发布件）。");
      } else {
        ElMessage.warning("浏览器拦截了新窗口，请前往详情页查看下载链接。");
      }
    } catch (caught) {
      ElMessage.error(normalizeApiError(caught).message);
    } finally {
      downloadingDraft.value = false;
    }
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (options.isOverlayOpen?.() || reviewHistoryOpen.value) {
      return;
    }
    if (isEditableShortcutTarget(event.target)) {
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "j") {
      event.preventDefault();
      stepBlock(1);
    } else if (key === "k") {
      event.preventDefault();
      stepBlock(-1);
    }
  }

  watch(
    () => [outlineFilter.problem, outlineFilter.blockType, outlineFilter.severity, outlineFilter.sourcePageIndex],
    () => {
      if (!loading.value && jobId.value) {
        void loadBlocks(false);
      }
    },
  );

  watch(
    () => reviewForm.status,
    (nextStatus) => {
      if (nextStatus !== "approved") {
        reviewForm.acknowledgeTableSemantics = false;
      }
    },
  );

  watch(jobId, (nextJobId, prevJobId) => {
    if (!nextJobId || nextJobId === prevJobId) {
      return;
    }
    revokeAllTableRefUrls();
    clearPreviewImageCache();
    selectedBlockId.value = "";
    blockDetail.value = null;
    reviewHistory.value = null;
    void loadAll(false);
  });

  onMounted(() => {
    if (typeof window !== "undefined") {
      window.addEventListener("keydown", handleKeydown);
    }
    void loadAll(false);
  });

  onBeforeUnmount(() => {
    disposed = true;
    if (typeof window !== "undefined") {
      window.removeEventListener("keydown", handleKeydown);
    }
    revokeAllTableRefUrls();
    clearPreviewImageCache();
  });

  return {
    jobId,
    job,
    quality,
    blocksResponse,
    tablesResponse,
    pagesResponse,
    previewResponse,
    tableReferencesResponse,
    blocks,
    selectedBlockId,
    selectedBlock,
    blockDetail,
    selectedBlockTables,
    selectedBlockReferences,
    availableSourcePages,
    currentSourcePageNumber,
    isTranslationJob,
    languagePair,
    sourceFilename,
    observedSource,
    expectedSource,
    contentSnapshotId,
    outlineFilter,
    reviewForm,
    currentReview,
    tableSemanticsReportSha256,
    tableSemanticsFindingsCount,
    hasTableSemanticsConflict,
    needsTableSemanticsConfirmation,
    mustTickTableSemanticsToApprove,
    canSubmitReview,
    effectiveActions,
    canRequestNewGeneration,
    newGenerationDisabledReason,
    previewPages,
    activePreviewPageIndex,
    currentPreviewPage,
    currentPreviewImageUrl,
    currentPreviewImageLoading,
    currentPreviewImageError,
    previewZoom,
    tableRefObjectUrls,
    tableRefLoading,
    tableRefErrors,
    reviewHistory,
    reviewHistoryOpen,
    reviewHistoryLoading,
    reviewHistoryError,
    loading,
    blocksLoading,
    blockDetailLoading,
    submittingReview,
    openingSourcePdf,
    downloadingDraft,
    pageError,
    blocksError,
    blockDetailError,
    previewError,
    tablesError,
    pagesError,
    reviewSubmitError,
    reviewConflictActive,
    loadAll,
    loadBlocks,
    loadBlockDetail,
    selectBlock,
    stepBlock,
    setPreviewPageIndex,
    stepPreviewPage,
    submitReview,
    openReviewHistory,
    loadReviewHistory,
    openSourcePdf,
    downloadInternalDraft,
  };
}

export type DocumentReviewSession = ReturnType<typeof useDocumentReviewSession>;
