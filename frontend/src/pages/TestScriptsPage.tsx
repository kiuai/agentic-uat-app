import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTestScripts, useSubmitScriptForReview, useApproveScript, useRejectScript } from "@/hooks/useTestScripts";
import type { ScriptFormat, TestScript } from "@/types";

const FORMAT_LABELS: Record<ScriptFormat, string> = {
  playwright_ts: "Playwright TS",
  playwright_js: "Playwright JS",
  selenium_python: "Selenium",
  pytest: "Pytest",
  robot_framework: "Robot Framework",
  gherkin: "Gherkin",
};

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  IN_REVIEW: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  LOCKED: "bg-blue-100 text-blue-700",
};

function ScriptActions({ projectId, script }: { projectId: string; script: TestScript }) {
  const [rejectComment, setRejectComment] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const submit = useSubmitScriptForReview(projectId, script.id);
  const approve = useApproveScript(projectId, script.id);
  const reject = useRejectScript(projectId, script.id);

  if (script.status === "DRAFT") {
    return (
      <button
        onClick={() => submit.mutate()}
        disabled={submit.isPending}
        className="text-xs bg-yellow-100 text-yellow-800 px-3 py-1 rounded hover:bg-yellow-200 disabled:opacity-50"
      >
        {submit.isPending ? "Submitting…" : "Submit for Review"}
      </button>
    );
  }

  if (script.status === "IN_REVIEW") {
    return (
      <div className="flex flex-col gap-2 items-end">
        <div className="flex gap-2">
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="text-xs bg-green-100 text-green-800 px-3 py-1 rounded hover:bg-green-200 disabled:opacity-50"
          >
            {approve.isPending ? "Approving…" : "Approve"}
          </button>
          <button
            onClick={() => setShowRejectForm(!showRejectForm)}
            className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200"
          >
            Reject
          </button>
        </div>
        {showRejectForm && (
          <div className="flex gap-2 w-full max-w-sm">
            <input
              value={rejectComment}
              onChange={(e) => setRejectComment(e.target.value)}
              placeholder="Rejection reason (required)"
              className="flex-1 border rounded px-2 py-1 text-xs"
            />
            <button
              onClick={() => {
                if (!rejectComment.trim()) return;
                reject.mutate(rejectComment);
                setShowRejectForm(false);
              }}
              disabled={reject.isPending || !rejectComment.trim()}
              className="text-xs bg-destructive text-destructive-foreground px-3 py-1 rounded disabled:opacity-50"
            >
              Confirm
            </button>
          </div>
        )}
      </div>
    );
  }

  return null;
}

export function TestScriptsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [selectedScript, setSelectedScript] = useState<TestScript | null>(null);
  const [selectedFormat, setSelectedFormat] = useState<ScriptFormat>("playwright_ts");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: scripts, isLoading } = useTestScripts(projectId!, {
    status: statusFilter || undefined,
  });

  const handleSelectScript = (script: TestScript) => {
    setSelectedScript(script);
    const firstFormat = Object.keys(script.scripts)[0] as ScriptFormat | undefined;
    if (firstFormat) setSelectedFormat(firstFormat);
  };

  return (
    <div className="flex gap-4 h-full">
      {/* Script list */}
      <div className="w-80 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Test Scripts</h2>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded px-3 py-1.5 text-sm w-full"
        >
          <option value="">All statuses</option>
          {["DRAFT", "IN_REVIEW", "APPROVED", "REJECTED", "LOCKED"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : (
          <div className="space-y-2 overflow-y-auto flex-1">
            {scripts?.map((script) => (
              <button
                key={script.id}
                onClick={() => handleSelectScript(script)}
                className={`w-full text-left bg-card border rounded-lg p-3 hover:border-primary transition-colors ${
                  selectedScript?.id === script.id ? "border-primary bg-primary/5" : ""
                }`}
              >
                <p className="font-medium text-sm truncate">{script.title}</p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[script.status]}`}
                  >
                    {script.status}
                  </span>
                  <span className="text-xs text-muted-foreground">v{script.version}</span>
                  {script.tags.slice(0, 2).map((tag) => (
                    <span key={tag} className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))}
            {scripts?.length === 0 && (
              <p className="text-muted-foreground text-sm">
                No scripts yet. Generate from requirements.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Script viewer */}
      {selectedScript && (
        <div className="flex-1 bg-card border rounded-lg p-4 flex flex-col min-w-0">
          <div className="flex items-start justify-between mb-3 gap-3">
            <div className="min-w-0">
              <h3 className="font-medium truncate">{selectedScript.title}</h3>
              {selectedScript.description && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {selectedScript.description}
                </p>
              )}
            </div>
            <ScriptActions projectId={projectId!} script={selectedScript} />
          </div>

          {/* Format tabs */}
          <div className="flex gap-2 mb-3 flex-wrap">
            {(Object.keys(selectedScript.scripts) as ScriptFormat[]).map((fmt) => (
              <button
                key={fmt}
                onClick={() => setSelectedFormat(fmt)}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  selectedFormat === fmt
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary hover:bg-secondary/80"
                }`}
              >
                {FORMAT_LABELS[fmt] ?? fmt}
              </button>
            ))}
          </div>

          <pre className="flex-1 bg-muted rounded p-4 text-xs overflow-auto font-mono whitespace-pre leading-relaxed min-h-0">
            {selectedScript.scripts[selectedFormat] ?? "Format not available for this script."}
          </pre>

          {selectedScript.approved_by && (
            <p className="text-xs text-muted-foreground mt-2">
              Approved {selectedScript.approved_at ? new Date(selectedScript.approved_at).toLocaleDateString() : ""}
            </p>
          )}
        </div>
      )}

      {!selectedScript && !isLoading && (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm">Select a script to view its content</p>
        </div>
      )}
    </div>
  );
}
