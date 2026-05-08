import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiGet, apiPost } from "@/services/api";
import { ScriptEditor } from "@/components/ui/ScriptEditor";
import { FileUploadZone } from "@/components/ui/FileUploadZone";
import apiClient from "@/services/api";
import type { TestAssignment, TestScript } from "@/types";
import { useState, useId } from "react";

const schema = z.object({
  status: z.enum(["PASSED", "FAILED", "BLOCKED", "SKIPPED"] as const),
  notes: z.string().optional(),
  duration_seconds: z.coerce.number().optional(),
});

type FormData = z.infer<typeof schema>;
type ExecutionStatus = "PASSED" | "FAILED" | "BLOCKED" | "SKIPPED";

const RESULT_STYLES: Record<ExecutionStatus, string> = {
  PASSED: "border-green-400 bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  FAILED: "border-red-400 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  BLOCKED: "border-orange-400 bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  SKIPPED: "border-gray-300 bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

function ResultRadio({
  value,
  register,
  checked,
}: {
  value: ExecutionStatus;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: any;
  checked: boolean;
}) {
  const baseClass = "border-2 rounded-lg p-2 text-center text-xs font-medium transition-colors";
  const checkedClass = checked ? RESULT_STYLES[value] : "border-border hover:bg-accent";
  return (
    <label className="cursor-pointer">
      <input {...register("status")} type="radio" value={value} className="sr-only" />
      <div className={`${baseClass} ${checkedClass}`}>{value}</div>
    </label>
  );
}

export function ExecuteTestPage() {
  const { projectId, cycleId, assignmentId } = useParams<{
    projectId: string;
    cycleId: string;
    assignmentId: string;
  }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);

  const { data: assignment } = useQuery({
    queryKey: ["assignment", assignmentId],
    queryFn: () =>
      apiGet<TestAssignment>(
        `/api/v1/projects/${projectId}/cycles/${cycleId}/executions/${assignmentId}`
      ),
    enabled: !!assignmentId,
  });

  const { data: script } = useQuery({
    queryKey: ["script", assignment?.script_id],
    queryFn: () =>
      apiGet<TestScript>(
        `/api/v1/projects/${projectId}/test-scripts/${assignment!.script_id}`
      ),
    enabled: !!assignment?.script_id,
  });

  const { data: scriptContent } = useQuery({
    queryKey: ["script-content", assignment?.script_id],
    queryFn: () =>
      apiGet<{ content: string }>(
        `/api/v1/projects/${projectId}/test-scripts/${assignment!.script_id}/content`
      ),
    enabled: !!assignment?.script_id,
  });

  const { register, handleSubmit, control } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { status: "PASSED" },
  });
  const selectedStatus = useWatch({ control, name: "status" });

  const submitResult = useMutation({
    mutationFn: async (data: FormData) => {
      const result = await apiPost(
        `/api/v1/projects/${projectId}/cycles/${cycleId}/executions/${assignmentId}/results`,
        { ...data, notes: data.notes || null, duration_seconds: data.duration_seconds || null }
      );

      // Upload evidence files if any
      if (evidenceFiles.length > 0) {
        for (const file of evidenceFiles) {
          const fd = new FormData();
          fd.append("file", file);
          await apiClient.post(
            `/api/v1/projects/${projectId}/cycles/${cycleId}/executions/${assignmentId}/evidence`,
            fd,
            { headers: { "Content-Type": "multipart/form-data" } }
          );
        }
      }

      return result;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignments", cycleId] });
      navigate(`/projects/${projectId}/cycles/${cycleId}`);
    },
  });

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Execute Test</h1>
        {script && <p className="text-muted-foreground text-sm mt-1">{script.title}</p>}
      </div>

      {script && scriptContent && (
        <div>
          <h2 className="font-medium text-sm mb-2">Script</h2>
          <ScriptEditor
            value={scriptContent.content}
            format={script.format}
            readOnly
            height="300px"
          />
        </div>
      )}

      <form onSubmit={handleSubmit((d) => submitResult.mutate(d))} className="space-y-5">
        <div>
          <label className="block text-sm font-medium mb-1">Result *</label>
          <div className="grid grid-cols-4 gap-2">
            {(["PASSED", "FAILED", "BLOCKED", "SKIPPED"] as const).map((s) => (
              <ResultRadio key={s} value={s} register={register} checked={selectedStatus === s} />
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Duration (seconds)</label>
          <input
            {...register("duration_seconds")}
            type="number"
            min="0"
            className="w-32 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="0"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Notes</label>
          <textarea
            {...register("notes")}
            rows={4}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
            placeholder="Describe what happened, any issues encountered…"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Evidence (optional)</label>
          <FileUploadZone
            accept="image/*,.pdf,.png,.jpg,.jpeg,.gif,.webp"
            multiple
            onFiles={setEvidenceFiles}
          />
        </div>

        {submitResult.isError && (
          <p className="text-sm text-red-600">Failed to submit result. Please try again.</p>
        )}

        <div className="flex gap-3">
          <button type="button" onClick={() => navigate(-1)} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitResult.isPending}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {submitResult.isPending ? "Submitting…" : "Submit Result"}
          </button>
        </div>
      </form>
    </div>
  );
}
