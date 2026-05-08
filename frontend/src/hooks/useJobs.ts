import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { Job } from "@/types";

export function useJob(jobId: string, options?: { enabled?: boolean; refetchInterval?: number }) {
  return useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => apiGet<Job>(`/api/v1/jobs/${jobId}`),
    enabled: options?.enabled ?? !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "PROCESSING") {
        return options?.refetchInterval ?? 3000; // Poll every 3s while running
      }
      return false;
    },
  });
}
