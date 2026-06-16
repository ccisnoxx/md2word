// frontend/src/api/client.ts: Axios client adapted to this backend's direct-schema responses.
import axios, { AxiosHeaders, type AxiosRequestConfig } from "axios";

import { getStoredToken } from "@/utils/authStorage";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type UnauthorizedHandler = (error: ApiClientError) => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 50_000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers = AxiosHeaders.from(config.headers);
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const clientError = normalizeApiError(error);
    if (clientError.status === 401) {
      unauthorizedHandler?.(clientError);
    }
    return Promise.reject(clientError);
  },
);

export function apiRequest<T>(config: AxiosRequestConfig): Promise<T> {
  return apiClient.request<T, T>(config);
}
