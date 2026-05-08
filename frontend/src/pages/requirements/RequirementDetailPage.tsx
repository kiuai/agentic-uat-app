import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, AlertTriangle, XCircle, Zap, Loader2 } from "lucide-react";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import type { Requirement, QualityCheckResult, TestScript } from "@/types";

function QualityCard({ result }: { result: QualityCheckResult }) {
  const icon =
    result.verdict === "TESTABLE" ? (
      <CheckCircle className="h-5 w-5 text-green-600" />
    ) : result.verdict === "NEEDS_IMPROVEMENT" ? (
      <AlertTriangle className="h-5 w-5 text-yellow-600" />
    ) : (
      <XCircle className="h-5 w-5 text-red-600" />
    );

  const bg =
    result.verdict === "TESTABLE"
      ? "bg-green-50 border-green-200"
      : result.verdict === "NEEDS_IMPROVEMENT"
      ? "bg-yellow-50 border-yellow-200"
      : "bg-red-50 border-red-200";

  return (
    <div className={`rounded-xl border p-4 ${bg}`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-semibold">{result.verdict.replace(/_/g, " ")}</span>
        <span className="ml-auto text-sm font-mono">Score: {result.score}/100</span>
      </div>
      {result.issues.length > 0 && (
        <ul className="text-sm space-y-1 mt-2">
          {result.issues.map((issue, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className="text-muted-foreground mt-0.5">•</span>
              {issue}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RequirementDetailPage() {
  const { projectId, requirementId } = useParams<{
    projectId: string;
    requirementId: string;
  }>();
  const qc = useQueryClient();

  const { data: req, isLoading } = useQuery({
    queryKey: ["requirement", requirementId],
    queryFn: () => apiGet<Requirement>(`/api/v1/projects/${projectId}/requirements/${requirementId}`),
    enabled: !!requirementId,
  });

  const { data: scripts } = useQuery({
    queryKey: ["scripts", projectId, "requirement", requirementId],
    queryFn: () =>
      apiGet<TestScript[]>(
        `/api/v1/projects/${projectId}/test-scripts?requirement_id=${requirementId}`
      ),
    enabled: !!requirementId,
  });

  const qualityCheck = useMutation({
    mutationFn: () =>
      apiGet<QualityCheckResult>(
        `/api/v1/projects/${projectId}/requirements/${requirementId}/quality-check`
      ),
  });

  const generateScripts = useMutation({
    mutationFn: () =>
      apiPost(`/api/v1/projects/${projectId}/requirements/${requirementId}/generate-scripts`, {
        output_formats: ["gherkin", "playwright_ts"],
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scripts", projectId] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-muted animate-pulse rounded w-1/2" />
        <div className="h-40 bg-muted animate-pulse rounded" />
      </div>
    );
  }

  if (!req) return <div className="text-muted-foreground">Requirement not found.</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/projects/${projectId}/requirements`} className="hover:text-foreground">
          Requirements
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium truncate">{req.title}</span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{req.title}</h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <StatusBadge status={req.status} />
            <span className="text-xs bg-muted px-2 py-0.5 rounded">{req.priority}</span>
            <span className="text-xs bg-muted px-2 py-0.5 rounded">{req.source_type}</span>
            {req.business_domain && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                {req.business_domain}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      {req.content_text && (
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-3">Content</h2>
          <p className="text-sm whitespace-pre-wrap text-muted-foreground">{req.content_text}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 flex-wrap">
        <button
          onClick={() => qualityCheck.mutate()}
          disabled={qualityCheck.isPending}
          className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-50"
        >
          {qualityCheck.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle className="h-4 w-4" />
          )}
          Quality Check
        </button>

        <RoleGate permission="ai:generate">
          <button
            onClick={() => generateScripts.mutate()}
            disabled={generateScripts.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {generateScripts.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" />
                Generate Scripts
              </>
            )}
          </button>
        </RoleGate>
      </div>

      {/* Quality result */}
      {qualityCheck.data && <QualityCard result={qualityCheck.data} />}
      {generateScripts.isSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3">
          Script generation job started. Check AI Jobs for progress.
        </div>
      )}

      {/* Linked scripts */}
      {scripts && scripts.length > 0 && (
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-3">Linked Test Scripts ({scripts.length})</h2>
          <div className="space-y-2">
            {scripts.map((s) => (
              <Link
                key={s.id}
                to={`/projects/${projectId}/scripts/${s.id}`}
                className="flex items-center justify-between p-3 border rounded-lg hover:border-primary transition-colors"
              >
                <div>
                  <p className="text-sm font-medium">{s.title}</p>
                  <p className="text-xs text-muted-foreground">{s.format}</p>
                </div>
                <StatusBadge status={s.status} />
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
