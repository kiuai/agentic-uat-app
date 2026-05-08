import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { ScriptCoverageReport } from "@/types";
import { BarChart3, CheckCircle, XCircle } from "lucide-react";

export function CoverageReportPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ["report-coverage", projectId],
    queryFn: () =>
      apiGet<ScriptCoverageReport>(`/api/v1/projects/${projectId}/reports/coverage`),
    enabled: !!projectId,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Coverage Report</h1>
        <div className="flex gap-2 text-sm text-muted-foreground">
          <Link to={`/projects/${projectId}/reports/ai-usage`} className="hover:text-foreground underline-offset-2 hover:underline">
            AI Usage
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse bg-muted rounded-xl" />
          ))}
        </div>
      ) : !data ? (
        <p className="text-muted-foreground">No data available.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-card border rounded-xl p-5 text-center">
              <p className="text-3xl font-bold">{data.total_requirements}</p>
              <p className="text-sm text-muted-foreground mt-1">Total Requirements</p>
            </div>
            <div className="bg-card border rounded-xl p-5 text-center">
              <p className="text-3xl font-bold text-green-600">{data.requirements_with_scripts}</p>
              <p className="text-sm text-muted-foreground mt-1">With Scripts</p>
            </div>
            <div className="bg-card border rounded-xl p-5 text-center">
              <p className="text-3xl font-bold text-primary">{data.coverage_percent}%</p>
              <p className="text-sm text-muted-foreground mt-1">Coverage</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="bg-card border rounded-xl p-5">
            <div className="flex items-center justify-between mb-2 text-sm">
              <span className="font-medium">Script Coverage</span>
              <span className="text-muted-foreground">{data.coverage_percent}%</span>
            </div>
            <div className="h-4 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${data.coverage_percent}%` }}
              />
            </div>
          </div>

          {/* Uncovered requirements */}
          {data.requirements_without_scripts.length > 0 && (
            <div className="bg-card border rounded-xl p-5">
              <h2 className="font-semibold mb-3 flex items-center gap-2 text-orange-600">
                <XCircle className="h-4 w-4" />
                Requirements Without Scripts ({data.requirements_without_scripts.length})
              </h2>
              <ul className="space-y-1 max-h-64 overflow-y-auto">
                {data.requirements_without_scripts.map((r, i) => (
                  <li key={i} className="text-sm text-muted-foreground py-1 border-b last:border-0">
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
