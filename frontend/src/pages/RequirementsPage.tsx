import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/services/api";
import type { Requirement } from "@/types";

export function RequirementsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const qc = useQueryClient();

  const { data: requirements, isLoading } = useQuery({
    queryKey: ["requirements", projectId],
    queryFn: () => apiGet<Requirement[]>(`/api/v1/projects/${projectId}/requirements`),
  });

  const generate = useMutation({
    mutationFn: (requirementIds: string[]) =>
      apiPost(`/api/v1/projects/${projectId}/generation-jobs`, {
        requirement_ids: requirementIds,
        output_formats: ["playwright_ts", "gherkin"],
      }),
    onSuccess: () => alert("AI generation job submitted! Check the Test Scripts section."),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">Requirements</h2>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="space-y-2">
          {requirements?.map((req) => (
            <div key={req.id} className="bg-card border rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="font-medium">{req.title}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {req.source_type} · {req.status}
                  {req.domain_code && ` · ${req.domain_code}`}
                </p>
              </div>
              <button
                onClick={() => generate.mutate([req.id])}
                className="text-xs bg-primary/10 text-primary px-3 py-1 rounded hover:bg-primary/20"
              >
                Generate Tests
              </button>
            </div>
          ))}
          {requirements?.length === 0 && (
            <p className="text-muted-foreground text-sm">No requirements yet. Upload one to get started.</p>
          )}
        </div>
      )}
    </div>
  );
}
