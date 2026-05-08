import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/services/api";
import {
  useRequirements,
  useCreateRequirement,
  useUploadRequirement,
  useDeleteRequirement,
} from "@/hooks/useRequirements";
import type { Job, Requirement } from "@/types";
import { useJob } from "@/hooks/useJobs";

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-700",
  HIGH: "bg-orange-100 text-orange-700",
  MEDIUM: "bg-yellow-100 text-yellow-700",
  LOW: "bg-gray-100 text-gray-600",
};

const STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-gray-100 text-gray-600",
  PROCESSED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
};

function CreateRequirementForm({
  projectId,
  onClose,
}: {
  projectId: string;
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [priority, setPriority] = useState("MEDIUM");
  const create = useCreateRequirement(projectId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await create.mutateAsync({ title, content_text: content, priority });
    onClose();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-card border rounded-lg p-4 mb-4 space-y-3"
    >
      <h3 className="font-medium text-sm">New Requirement</h3>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Requirement title"
        required
        className="w-full border rounded px-3 py-2 text-sm"
      />
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Requirement description / acceptance criteria"
        rows={4}
        className="w-full border rounded px-3 py-2 text-sm font-mono"
      />
      <div className="flex items-center gap-3">
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="border rounded px-3 py-2 text-sm"
        >
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={create.isPending}
          className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          {create.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm text-muted-foreground"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function GenerationJobBanner({ jobId }: { jobId: string }) {
  const { data: job } = useJob(jobId, { enabled: !!jobId, refetchInterval: 3000 });

  if (!job) return null;
  const color =
    job.status === "COMPLETED"
      ? "bg-green-50 border-green-200 text-green-800"
      : job.status === "FAILED"
      ? "bg-red-50 border-red-200 text-red-800"
      : "bg-blue-50 border-blue-200 text-blue-800";

  return (
    <div className={`border rounded-lg p-3 text-sm flex items-center gap-2 ${color}`}>
      {job.status === "PROCESSING" || job.status === "PENDING" ? (
        <span className="animate-spin">⏳</span>
      ) : job.status === "COMPLETED" ? (
        "✅"
      ) : (
        "❌"
      )}
      <span>
        Generation job <code className="font-mono text-xs">{jobId.slice(0, 8)}</code>:{" "}
        <strong>{job.status}</strong>
        {job.status === "COMPLETED" && " — check Test Scripts for results."}
        {job.status === "FAILED" && job.error_message && ` — ${job.error_message}`}
      </span>
    </div>
  );
}

export function RequirementsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: requirements, isLoading } = useRequirements(projectId!);
  const deleteReq = useDeleteRequirement(projectId!);
  const upload = useUploadRequirement(projectId!);
  const qc = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: (requirementIds: string[]) =>
      apiPost<Job>(`/api/v1/projects/${projectId}/generation-jobs`, {
        requirement_ids: requirementIds,
        output_formats: ["playwright_ts", "gherkin"],
        generation_config: { include_assertions: true, include_negative_cases: true },
      }),
    onSuccess: (job) => {
      setPendingJobId(job.id);
      setSelectedIds(new Set());
    },
  });

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const title = file.name.replace(/\.[^.]+$/, "");
    await upload.mutateAsync({ file, title });
    e.target.value = "";
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Requirements</h2>
        <div className="flex items-center gap-2">
          <label className="cursor-pointer bg-secondary text-secondary-foreground px-4 py-2 rounded-md text-sm hover:bg-secondary/80">
            Upload File
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={handleFileUpload}
            />
          </label>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm hover:bg-primary/90"
          >
            + Add Text
          </button>
        </div>
      </div>

      {pendingJobId && <div className="mb-4"><GenerationJobBanner jobId={pendingJobId} /></div>}
      {showCreate && (
        <CreateRequirementForm projectId={projectId!} onClose={() => setShowCreate(false)} />
      )}

      {selectedIds.size > 0 && (
        <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 mb-4 flex items-center justify-between">
          <span className="text-sm font-medium">
            {selectedIds.size} requirement{selectedIds.size > 1 ? "s" : ""} selected
          </span>
          <button
            onClick={() => generate.mutate([...selectedIds])}
            disabled={generate.isPending}
            className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm disabled:opacity-50"
          >
            {generate.isPending ? "Submitting…" : "Generate Tests"}
          </button>
        </div>
      )}

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <div className="space-y-2">
          {requirements?.map((req: Requirement) => (
            <div
              key={req.id}
              onClick={() => toggleSelect(req.id)}
              className={`bg-card border rounded-lg p-4 cursor-pointer transition-colors ${
                selectedIds.has(req.id) ? "border-primary bg-primary/5" : "hover:border-muted-foreground/40"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(req.id)}
                    onChange={() => toggleSelect(req.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="mt-1 shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="font-medium truncate">{req.title}</p>
                    {req.content_text && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {req.content_text}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          STATUS_COLORS[req.status] ?? "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {req.status}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          PRIORITY_COLORS[req.priority ?? "MEDIUM"] ?? ""
                        }`}
                      >
                        {req.priority ?? "MEDIUM"}
                      </span>
                      <span className="text-xs text-muted-foreground">{req.source_type}</span>
                      {req.domain_code && (
                        <span className="text-xs text-muted-foreground">
                          Domain: {req.domain_code}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    generate.mutate([req.id]);
                  }}
                  disabled={generate.isPending}
                  className="shrink-0 text-xs bg-primary/10 text-primary px-3 py-1 rounded hover:bg-primary/20 disabled:opacity-50"
                >
                  Generate
                </button>
              </div>
            </div>
          ))}
          {requirements?.length === 0 && (
            <p className="text-muted-foreground text-sm">
              No requirements yet. Add text or upload a document to get started.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
