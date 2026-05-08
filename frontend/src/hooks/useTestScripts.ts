import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/services/api";
import type { TestScript } from "@/types";

export const scriptKeys = {
  list: (projectId: string, filters?: Record<string, string>) =>
    ["test-scripts", projectId, filters] as const,
  detail: (projectId: string, scriptId: string) => ["test-scripts", projectId, scriptId] as const,
};

export function useTestScripts(
  projectId: string,
  filters?: { status?: string; domainCode?: string }
) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status_filter", filters.status);
  if (filters?.domainCode) params.set("domain_code", filters.domainCode);
  const query = params.toString();

  return useQuery({
    queryKey: scriptKeys.list(projectId, filters),
    queryFn: () =>
      apiGet<TestScript[]>(
        `/api/v1/projects/${projectId}/test-scripts${query ? `?${query}` : ""}`
      ),
    enabled: !!projectId,
  });
}

export function useTestScript(projectId: string, scriptId: string) {
  return useQuery({
    queryKey: scriptKeys.detail(projectId, scriptId),
    queryFn: () => apiGet<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}`),
    enabled: !!(projectId && scriptId),
  });
}

export function useSubmitScriptForReview(projectId: string, scriptId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}/submit-review`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scriptKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: scriptKeys.detail(projectId, scriptId) });
    },
  });
}

export function useApproveScript(projectId: string, scriptId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (comments?: string) =>
      apiPost<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}/approve`, {
        comments,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scriptKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: scriptKeys.detail(projectId, scriptId) });
    },
  });
}

export function useRejectScript(projectId: string, scriptId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (comments: string) =>
      apiPost<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}/reject`, {
        comments,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scriptKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: scriptKeys.detail(projectId, scriptId) });
    },
  });
}

export function useUpdateScript(projectId: string, scriptId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<{ title: string; description: string; tags: string[] }>) =>
      apiPatch<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scriptKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: scriptKeys.detail(projectId, scriptId) });
    },
  });
}

export function useDeleteScript(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scriptId: string) =>
      apiDelete(`/api/v1/projects/${projectId}/test-scripts/${scriptId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: scriptKeys.list(projectId) }),
  });
}
