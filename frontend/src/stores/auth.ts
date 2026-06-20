// frontend/src/stores/auth.ts: Pinia store for JWT auth and current user state.
import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { authApi } from "@/api/auth";
import type { AuthLoginRequest, AuthTokenResponse, CurrentUserResponse } from "@/api/types";
import { clearStoredToken, getStoredToken, setStoredToken } from "@/utils/authStorage";

const OPERATOR_PERMISSIONS = [
  "document_jobs:read",
  "document_jobs:create",
  "document_jobs:download",
  "document_jobs:retry",
  "document_jobs:cancel",
  "document_jobs:archive",
  "document_jobs:clone",
  "translation_qa:read",
  "translation_qa:write",
  "term_proposals:read",
  "term_proposals:create",
];

const ADMIN_EXTRA_PERMISSIONS = [
  "settings:read",
  "settings:write",
  "system:read",
  "ops:read",
  "ops:write",
  "audit:read",
  "users:manage",
  "files:retention",
  "term_proposals:review",
];

function fallbackPermissions(role: string): string[] {
  const permissions = [...OPERATOR_PERMISSIONS];
  if (role === "admin") {
    permissions.push(...ADMIN_EXTRA_PERMISSIONS);
  }
  return permissions;
}

function normalizeUser(response: CurrentUserResponse): CurrentUserResponse {
  const role = response.role;
  const roles = Array.isArray(response.roles) && response.roles.length ? response.roles : [role];
  const permissions =
    Array.isArray(response.permissions) && response.permissions.length ? response.permissions : fallbackPermissions(role);
  return {
    ...response,
    roles,
    permissions,
  };
}

function userFromTokenResponse(response: AuthTokenResponse): CurrentUserResponse {
  return normalizeUser({
    id: response.user_id,
    username: response.username,
    role: response.role,
    roles: Array.isArray(response.roles) && response.roles.length ? response.roles : [response.role],
    permissions:
      Array.isArray(response.permissions) && response.permissions.length
        ? response.permissions
        : fallbackPermissions(response.role),
    tenant_id: response.tenant_id,
    company_id: response.company_id,
    display_name: null,
  });
}

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(getStoredToken());
  const user = ref<CurrentUserResponse | null>(null);
  const bootstrapped = ref(false);

  const isAuthenticated = computed(() => Boolean(token.value));
  const roles = computed(() => user.value?.roles ?? []);
  const permissions = computed(() => user.value?.permissions ?? []);

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
    user.value = normalizeUser(await authApi.me());
    bootstrapped.value = true;
    return user.value;
  }

  function hasRole(requiredRoles: string | string[]): boolean {
    const expected = Array.isArray(requiredRoles) ? requiredRoles : [requiredRoles];
    return expected.some((role) => roles.value.includes(role));
  }

  function hasPermission(requiredPermissions: string | string[]): boolean {
    const expected = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions];
    return expected.some((permission) => permissions.value.includes(permission));
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
    roles,
    permissions,
    hasRole,
    hasPermission,
    login,
    loadCurrentUser,
    logout,
  };
});
