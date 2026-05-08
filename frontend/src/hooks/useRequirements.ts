import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/services/api";
import type { Requirement } from "@/types";

export const requirementKeys = {
  list: (projectId: string) => ["requirements", projectId] as const,
  detail: (projectId: string, reqId: string) => ["requirements", projectId, reqId] as const,
};

export function useRequirements(projectId: string) {
  return useQuery({
    queryKey: requirementKeys.list(projectId),
    queryFn: () => apiGet<Requirement[]>(`/api/v1/projects/${projectId}/requirements`),
    enabled: !!projectId,
  });
}

export function useRequirement(projectId: string, reqId: string) {
  return useQuery({
    queryKey: requirementKeys.detail(projectId, reqId),
    queryFn: () => apiGet<Requirement>(`/api/v1/projects/${projectId}/requirements/${reqId}`),
    enabled: !!(projectId && reqId),
  });
}

export function useCreateRequirement(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      content_text?: string;
      description?: string;
      source_type?: string;
      priority?: string;
    }) => apiPost<Requirement>(`/api/v1/projects/${projectId}/requirements`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: requirementKeys.list(projectId) }),
  });
}

export function useUploadRequirement(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, title, domainCode }: { file: File; title: string; domainCode?: string }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title);
      if (domainCode) form.append("domain_code", domainCode);
      return apiPost<Requirement>(`/api/v1/projects/${projectId}/requirements/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: requirementKeys.list(projectId) }),
  });
}

export function useUpdateRequirement(projectId: string, reqId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<{ title: string; description: string; priority: string }>) =>
      apiPatch<Requirement>(`/api/v1/projects/${projectId}/requirements/${reqId}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: requirementKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: requirementKeys.detail(projectId, reqId) });
    },
  });
}

export function useDeleteRequirement(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reqId: string) =>
      apiDelete(`/api/v1/projects/${projectId}/requirements/${reqId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: requirementKeys.list(projectId) }),
  });
}
