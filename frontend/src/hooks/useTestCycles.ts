import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPatch } from "@/services/api";
import type { Execution, TestCycle } from "@/types";

export const cycleKeys = {
  list: (projectId: string) => ["cycles", projectId] as const,
  detail: (projectId: string, cycleId: string) => ["cycles", projectId, cycleId] as const,
  executions: (projectId: string, cycleId: string) =>
    ["cycles", projectId, cycleId, "executions"] as const,
};

export function useTestCycles(projectId: string) {
  return useQuery({
    queryKey: cycleKeys.list(projectId),
    queryFn: () => apiGet<TestCycle[]>(`/api/v1/projects/${projectId}/cycles`),
    enabled: !!projectId,
  });
}

export function useTestCycle(projectId: string, cycleId: string) {
  return useQuery({
    queryKey: cycleKeys.detail(projectId, cycleId),
    queryFn: () => apiGet<TestCycle>(`/api/v1/projects/${projectId}/cycles/${cycleId}`),
    enabled: !!(projectId && cycleId),
  });
}

export function useCreateTestCycle(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      name: string;
      environment_id: string;
      start_date?: string;
      end_date?: string;
    }) => apiPost<TestCycle>(`/api/v1/projects/${projectId}/cycles`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: cycleKeys.list(projectId) }),
  });
}

export function useActivateCycle(projectId: string, cycleId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<TestCycle>(`/api/v1/projects/${projectId}/cycles/${cycleId}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: cycleKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: cycleKeys.detail(projectId, cycleId) });
    },
  });
}

export function useCloseCycle(projectId: string, cycleId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiPost<TestCycle>(`/api/v1/projects/${projectId}/cycles/${cycleId}/close`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: cycleKeys.list(projectId) });
      qc.invalidateQueries({ queryKey: cycleKeys.detail(projectId, cycleId) });
    },
  });
}

export function useExecutions(projectId: string, cycleId: string) {
  return useQuery({
    queryKey: cycleKeys.executions(projectId, cycleId),
    queryFn: () =>
      apiGet<Execution[]>(`/api/v1/projects/${projectId}/cycles/${cycleId}/executions`),
    enabled: !!(projectId && cycleId),
  });
}

export function useUpdateExecution(projectId: string, cycleId: string, execId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { status: string; notes?: string }) =>
      apiPatch<Execution>(
        `/api/v1/projects/${projectId}/cycles/${cycleId}/executions/${execId}`,
        data
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: cycleKeys.executions(projectId, cycleId) }),
  });
}
