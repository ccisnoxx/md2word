// 文件库搜索 owner：筛选、排序、分页与只读搜索结果。
import { reactive, ref, type Ref } from "vue";

import { filesApi } from "@/api/files";
import type {
  FileLibrarySearchQuery,
  FileLibrarySearchResponse,
  FileLibrarySort,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type LibraryFilters = {
  q: string;
  status: string;
  file_type: string;
  storage_provider: string;
  job_id: string;
};

type LibraryFilterKey = "q" | "status" | "file_type" | "storage_provider" | "job_id";

export function useRetentionLibrary(
  error: Ref<ApiClientError | null>,
) {
  const librarySearch = ref<FileLibrarySearchResponse | null>(null);
  const libraryLoading = ref(false);

  const libraryFilters = reactive<LibraryFilters>({
    q: "",
    status: "",
    file_type: "",
    storage_provider: "",
    job_id: "",
  });

  const librarySort = ref<FileLibrarySort>("created_at_desc");
  const libraryPage = ref(1);
  const libraryPageSize = ref(50);

  // 按当前筛选读取只读文件库搜索结果。
  async function loadFileLibrarySearch(): Promise<void> {
    libraryLoading.value = true;
    error.value = null;
    try {
      librarySearch.value = await filesApi.searchLibrary(buildLibrarySearchQuery());
    } catch (caught) {
      error.value = normalizeApiError(caught);
    } finally {
      libraryLoading.value = false;
    }
  }

  // 应用文件库筛选条件并回到第一页。
  function applyLibrarySearch(): void {
    libraryPage.value = 1;
    void loadFileLibrarySearch();
  }

  // 重置文件库筛选条件并重新读取第一页。
  function resetLibrarySearch(): void {
    libraryFilters.q = "";
    libraryFilters.status = "";
    libraryFilters.file_type = "";
    libraryFilters.storage_provider = "";
    libraryFilters.job_id = "";
    librarySort.value = "created_at_desc";
    libraryPage.value = 1;
    void loadFileLibrarySearch();
  }

  // 改变文件库页大小时回到第一页，避免页码越界。
  function handleLibraryPageSizeChange(): void {
    libraryPage.value = 1;
    void loadFileLibrarySearch();
  }

  // 生成后端文件库搜索 query，空字符串不发送。
  function buildLibrarySearchQuery(): FileLibrarySearchQuery {
    const params: FileLibrarySearchQuery = {
      page: libraryPage.value,
      page_size: libraryPageSize.value,
      sort: librarySort.value,
    };
    addLibraryTrimmedParam(params, "q", libraryFilters.q);
    addLibraryTrimmedParam(params, "status", libraryFilters.status);
    addLibraryTrimmedParam(params, "file_type", libraryFilters.file_type);
    addLibraryTrimmedParam(params, "storage_provider", libraryFilters.storage_provider);
    addLibraryTrimmedParam(params, "job_id", libraryFilters.job_id);
    return params;
  }

  // 给文件库查询参数做统一 trim，空字符串不发送。
  function addLibraryTrimmedParam(params: FileLibrarySearchQuery, key: LibraryFilterKey, value: string): void {
    const normalized = value.trim();
    if (normalized) {
      Object.assign(params, { [key]: normalized });
    }
  }

  return {
    librarySearch,
    libraryLoading,
    libraryFilters,
    librarySort,
    libraryPage,
    libraryPageSize,
    loadFileLibrarySearch,
    applyLibrarySearch,
    resetLibrarySearch,
    handleLibraryPageSizeChange,
    buildLibrarySearchQuery,
    addLibraryTrimmedParam,
  };
}

export type RetentionLibrary = ReturnType<typeof useRetentionLibrary>;
