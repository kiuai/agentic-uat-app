import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import { getAccessToken } from "./auth";
import type { ApiError } from "@/types";

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// ── Request interceptor: attach Bearer token + tenant header ─────────────────

apiClient.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  config.headers.Authorization = `Bearer ${token}`;

  // Inject tenant header from authStore (lazy import to avoid circular deps)
  try {
    const { useAuthStore } = await import("@/store/authStore");
    const tenantId = useAuthStore.getState().tenantId;
    if (tenantId) {
      config.headers["X-Tenant-ID"] = tenantId;
    }
  } catch {
    // authStore not yet initialised — proceed without header
  }

  return config;
});

// ── Response interceptor: 401 redirect, 429 retry, error normalisation ───────

const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status: number | undefined = error.response?.status;

    if (status === 401) {
      window.location.href = "/login";
      return Promise.reject(normaliseError(error));
    }

    // Retry once on 429 with exponential back-off
    const config = error.config as AxiosRequestConfig & { _retryCount?: number };
    if (status === 429) {
      config._retryCount = (config._retryCount ?? 0) + 1;
      if (config._retryCount <= 3) {
        const retryAfter = Number(error.response?.headers?.["retry-after"] ?? 0);
        const delay = retryAfter > 0 ? retryAfter * 1000 : 2 ** config._retryCount * 500;
        await sleep(delay);
        return apiClient(config);
      }
    }

    return Promise.reject(normaliseError(error));
  }
);

function normaliseError(error: unknown): ApiError {
  // Already an ApiError shape
  if (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    "title" in error
  ) {
    return error as ApiError;
  }

  // Axios error with backend RFC 9457 body
  const axiosErr = error as { response?: { status?: number; data?: Partial<ApiError> } };
  if (axiosErr?.response) {
    const { status, data } = axiosErr.response;
    return {
      status: status ?? 0,
      title: data?.title ?? httpTitle(status ?? 0),
      detail: data?.detail ?? "An unexpected error occurred.",
      type: data?.type ?? "about:blank",
    };
  }

  return { status: 0, title: "Network Error", detail: String(error), type: "about:blank" };
}

function httpTitle(status: number): string {
  const titles: Record<number, string> = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
  };
  return titles[status] ?? "Error";
}

export default apiClient;

export function apiGet<T>(url: string, config?: AxiosRequestConfig) {
  return apiClient.get<T>(url, config).then((r) => r.data);
}

export function apiPost<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
  return apiClient.post<T>(url, data, config).then((r) => r.data);
}

export function apiPatch<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
  return apiClient.patch<T>(url, data, config).then((r) => r.data);
}

export function apiDelete(url: string, config?: AxiosRequestConfig) {
  return apiClient.delete(url, config);
}

export function apiPut<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
  return apiClient.put<T>(url, data, config).then((r) => r.data);
}

export { normaliseError };
