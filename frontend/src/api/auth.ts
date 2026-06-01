// frontend/src/api/auth.ts: Auth endpoints for login and current-user recovery.
import { apiRequest } from "@/api/client";
import type { AuthLoginRequest, AuthTokenResponse, CurrentUserResponse } from "@/api/types";

export const authApi = {
  login(payload: AuthLoginRequest): Promise<AuthTokenResponse> {
    return apiRequest<AuthTokenResponse>({
      url: "/api/v1/auth/login",
      method: "POST",
      data: payload,
    });
  },

  me(): Promise<CurrentUserResponse> {
    return apiRequest<CurrentUserResponse>({
      url: "/api/v1/auth/me",
      method: "GET",
    });
  },
};
