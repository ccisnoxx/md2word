// File: frontend/src/api/users.ts
// Purpose: Wrap Admin internal user management APIs.
import { apiRequest } from "@/api/client";
import type {
  InternalUserCreateRequest,
  InternalUserListQuery,
  InternalUserListResponse,
  InternalUserResetPasswordRequest,
  InternalUserResponse,
  InternalUserUpdateRequest,
} from "@/api/types";

export const internalUsersApi = {
  list(params: InternalUserListQuery = {}): Promise<InternalUserListResponse> {
    return apiRequest<InternalUserListResponse>({
      url: "/api/v1/users",
      method: "GET",
      params,
    });
  },

  create(payload: InternalUserCreateRequest): Promise<InternalUserResponse> {
    return apiRequest<InternalUserResponse>({
      url: "/api/v1/users",
      method: "POST",
      data: payload,
    });
  },

  update(userId: string, payload: InternalUserUpdateRequest): Promise<InternalUserResponse> {
    return apiRequest<InternalUserResponse>({
      url: `/api/v1/users/${userId}`,
      method: "PATCH",
      data: payload,
    });
  },

  resetPassword(userId: string, payload: InternalUserResetPasswordRequest): Promise<InternalUserResponse> {
    return apiRequest<InternalUserResponse>({
      url: `/api/v1/users/${userId}/reset-password`,
      method: "POST",
      data: payload,
    });
  },
};
