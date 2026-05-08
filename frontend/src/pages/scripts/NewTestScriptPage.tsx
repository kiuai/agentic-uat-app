import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiGet, apiPost } from "@/services/api";
import { ScriptEditor } from "@/components/ui/ScriptEditor";
import type { Requirement, TestScript, ScriptFormat } from "@/types";
import { useState } from "react";

const schema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  requirement_id: z.string().uuid("Select a requirement"),
  format: z.enum(["playwright_ts", "playwright_js", "selenium_python", "pytest", "robot_framework", "gherkin"] as const),
});

type FormData = z.infer<typeof schema>;

const FORMATS: ScriptFormat[] = [
  "gherkin", "playwright_ts", "playwright_js", "selenium_python", "pytest", "robot_framework",
];

export function NewTestScriptPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [content, setContent] = useState("// Write your test script here\n");

  const { data: requirements } = useQuery({
    queryKey: ["requirements", projectId, "all"],
    queryFn: () => apiGet<Requirement[]>(`/api/v1/projects/${projectId}/requirements?limit=200`),
    enabled: !!projectId,
  });

  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { format: "gherkin" },
  });

  const format = watch("format");

  const create = useMutation({
    mutationFn: (data: FormData) =>
      apiPost<TestScript>(`/api/v1/projects/${projectId}/test-scripts`, {
        ...data,
        description: data.description || null,
        content,
      }),
    onSuccess: (script) => {
      qc.invalidateQueries({ queryKey: ["scripts", projectId] });
      navigate(`/projects/${projectId}/scripts/${script.id}`);
    },
  });

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">New Test Script</h1>

      <form onSubmit={handleSubmit((d) => create.mutate(d))} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input {...register("title")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            {errors.title && <p className="text-xs text-red-600 mt-1">{errors.title.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Requirement *</label>
            <select {...register("requirement_id")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              <option value="">Select a requirement</option>
              {requirements?.map((r) => (
                <option key={r.id} value={r.id}>{r.title}</option>
              ))}
            </select>
            {errors.requirement_id && <p className="text-xs text-red-600 mt-1">{errors.requirement_id.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Format *</label>
            <select {...register("format")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
              {FORMATS.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea {...register("description")} rows={2} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Script Content</label>
          <ScriptEditor
            value={content}
            onChange={setContent}
            format={format}
            height="360px"
          />
        </div>

        {create.isError && <p className="text-sm text-red-600">Failed to create script.</p>}

        <div className="flex gap-3">
          <button type="button" onClick={() => navigate(-1)} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
          <button type="submit" disabled={create.isPending} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
            {create.isPending ? "Creating…" : "Create Script"}
          </button>
        </div>
      </form>
    </div>
  );
}
