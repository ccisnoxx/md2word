// File: frontend/src/api/savedViews.ts
// Purpose: Provide personal saved_views API wrappers for operations pages.
import { apiRequest } from "@/api/client";
import type {
  SavedViewCreateRequest,
  SavedViewListResponse,
  SavedViewPageKey,
  SavedViewReorderRequest,
  SavedViewResponse,
  SavedViewUpdateRequest,
} from "@/api/types";

export const savedViewsApi = {
  list(pageKey: SavedViewPageKey): Promise<SavedViewListResponse> {
    return apiRequest<SavedViewListResponse>({
      url: "/api/v1/saved-views",
      method: "GET",
      params: { page_key: pageKey },
    });
  },

  create(payload: SavedViewCreateRequest): Promise<SavedViewResponse> {
    return apiRequest<SavedViewResponse>({
      url: "/api/v1/saved-views",
      method: "POST",
      data: payload,
    });
  },

  update(viewId: string, payload: SavedViewUpdateRequest): Promise<SavedViewResponse> {
    return apiRequest<SavedViewResponse>({
      url: `/api/v1/saved-views/${viewId}`,
      method: "PATCH",
      data: payload,
    });
  },

  delete(viewId: string): Promise<void> {
    return apiRequest<void>({
      url: `/api/v1/saved-views/${viewId}`,
      method: "DELETE",
    });
  },

  reorder(payload: SavedViewReorderRequest): Promise<SavedViewListResponse> {
    return apiRequest<SavedViewListResponse>({
      url: "/api/v1/saved-views/reorder",
      method: "POST",
      data: payload,
    });
  },
};

