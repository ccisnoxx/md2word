// frontend/src/stores/auth.ts: Pinia store for JWT auth and current user state.
import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { authApi } from "@/api/auth";
import type { AuthLoginRequest, AuthTokenResponse, CurrentUserResponse } from "@/api/types";
import { clearStoredToken, getStoredToken, setStoredToken } from "@/utils/authStorage";

function userFromTokenResponse(response: AuthTokenResponse): CurrentUserResponse {
  return {
    id: response.user_id,
    username: response.username,
    role: response.role,
    tenant_id: response.tenant_id,
    company_id: response.company_id,
    display_name: null,
  };
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getStoredToken());
  const user = ref<CurrentUserResponse | null>(null);
  const bootstrapped = ref(false);

  const isAuthenticated = computed(() => Boolean(token.value));

  async function login(payload: AuthLoginRequest): Promise<void> {
    const response = await authApi.login(payload);
    token.value = response.access_token;
    user.value = userFromTokenResponse(response);
    setStoredToken(response.access_token);
    bootstrapped.value = true;
  }

  async function loadCurrentUser(): Promise<CurrentUserResponse | null> {
    if (!token.value) {
      bootstrapped.value = true;
      return null;
    }
    user.value = await authApi.me();
    bootstrapped.value = true;
    return user.value;
  }

  function logout(): void {
    token.value = null;
    user.value = null;
    bootstrapped.value = true;
    clearStoredToken();
  }

  return {
    token,
    user,
    bootstrapped,
    isAuthenticated,
    login,
    loadCurrentUser,
    logout,
  };
});
