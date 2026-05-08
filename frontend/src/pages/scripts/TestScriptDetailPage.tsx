import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Download, CheckCircle, XCircle, Loader2, History } from "lucide-react";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ScriptEditor } from "@/components/ui/ScriptEditor";
import { RoleGate } from "@/components/ui/RoleGate";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import type { TestScript, TestScriptVersion, ScriptExport } from "@/types";

export function TestScriptDetailPage() {
  const { projectId, scriptId } = useParams<{ projectId: string; scriptId: string }>();
  const qc = useQueryClient();
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);
  const [exportFormat, setExportFormat] = useState("gherkin");

  const { data: script, isLoading } = useQuery({
    queryKey: ["script", scriptId],
    queryFn: () => apiGet<TestScript>(`/api/v1/projects/${projectId}/test-scripts/${scriptId}`),
    enabled: !!scriptId,
  });

  const { data: versions } = useQuery({
    queryKey: ["script-versions", scriptId],
    queryFn: () =>
      apiGet<TestScriptVersion[]>(
        `/api/v1/projects/${projectId}/test-scripts/${scriptId}/versions`
      ),
    enabled: !!scriptId,
  });

  const { data: scriptContent } = useQuery({
    queryKey: ["script-content", scriptId],
    queryFn: () =>
      apiGet<{ content: string }>(
        `/api/v1/projects/${projectId}/test-scripts/${scriptId}/content`
      ),
    enabled: !!scriptId,
  });

  const approve = useMutation({
    mutationFn: () =>
      apiPost(`/api/v1/projects/${projectId}/test-scripts/${scriptId}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["script", scriptId] }),
  });

  const reject = useMutation({
    mutationFn: () =>
      apiPost(`/api/v1/projects/${projectId}/test-scripts/${scriptId}/reject`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["script", scriptId] }),
  });

  const exportScript = useMutation({
    mutationFn: () =>
      apiPost<ScriptExport>(
        `/api/v1/projects/${projectId}/test-scripts/${scriptId}/export`,
        { format: exportFormat }
      ),
    onSuccess: (data) => {
      if (data.download_url) {
        window.open(data.download_url, "_blank");
      } else if (data.content) {
        const blob = new Blob([data.content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${script?.title ?? "script"}.${exportFormat}`;
        a.click();
        URL.revokeObjectURL(url);
      }
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-muted animate-pulse rounded w-1/2" />
        <div className="h-96 bg-muted animate-pulse rounded" />
      </div>
    );
  }

  if (!script) return <div className="text-muted-foreground">Script not found.</div>;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/projects/${projectId}/scripts`} className="hover:text-foreground">
          Scripts
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium">{script.title}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold">{script.title}</h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <StatusBadge status={script.status} />
            <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded">{script.format}</span>
            <span className="text-xs text-muted-foreground">v{script.current_version}</span>
            {script.is_ai_generated && (
              <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded">
                AI generated
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Export */}
          <div className="flex items-center gap-1 border rounded-lg overflow-hidden">
            <select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              className="px-2 py-1.5 text-xs bg-background border-r focus:outline-none"
            >
              {["gherkin", "playwright_ts", "playwright_js", "selenium_python", "pytest", "robot_framework"].map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
            <button
              onClick={() => exportScript.mutate()}
              disabled={exportScript.isPending}
              className="flex items-center gap-1 px-3 py-1.5 text-xs hover:bg-accent transition-colors"
            >
              <Download className="h-3 w-3" />
              Export
            </button>
          </div>

          {/* Approve / Reject */}
          <RoleGate permission="script:approve">
            {script.status === "IN_REVIEW" && (
              <>
                <button
                  onClick={() => setConfirmApprove(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 transition-colors"
                >
                  <CheckCircle className="h-3 w-3" />
                  Approve
                </button>
                <button
                  onClick={() => setConfirmReject(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-red-300 text-red-600 rounded-lg text-xs font-medium hover:bg-red-50 transition-colors"
                >
                  <XCircle className="h-3 w-3" />
                  Reject
                </button>
              </>
            )}
          </RoleGate>
        </div>
      </div>

      {/* Script editor */}
      <ScriptEditor
        value={scriptContent?.content ?? "// Loading script content…"}
        format={script.format}
        readOnly
        height="480px"
      />

      {/* Version history */}
      {versions && versions.length > 0 && (
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <History className="h-4 w-4" />
            Version History
          </h2>
          <div className="space-y-2">
            {versions.map((v) => (
              <div key={v.id} className="flex items-center gap-3 text-sm py-1.5 border-b last:border-0">
                <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">v{v.version_number}</span>
                {v.change_summary && <p className="flex-1 text-muted-foreground">{v.change_summary}</p>}
                {v.is_ai_generated && (
                  <span className="text-xs text-purple-600">AI</span>
                )}
                <span className="text-xs text-muted-foreground shrink-0">
                  {new Date(v.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmApprove}
        onOpenChange={setConfirmApprove}
        title="Approve Script"
        description="Mark this script as approved? This will allow it to be used in test cycles."
        confirmLabel="Approve"
        onConfirm={() => approve.mutate()}
      />
      <ConfirmDialog
        open={confirmReject}
        onOpenChange={setConfirmReject}
        title="Reject Script"
        description="Reject this script and return it to draft status?"
        confirmLabel="Reject"
        destructive
        onConfirm={() => reject.mutate()}
      />
    </div>
  );
}
