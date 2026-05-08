import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import { getAccessToken } from "./auth";

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach Bearer token to every request
apiClient.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Global error handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired — MSAL will handle re-auth via getAccessToken
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

export default apiClient;

// Typed helper for the API response envelope
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
