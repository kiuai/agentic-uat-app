import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiGet, apiPatch, apiDelete } from "@/services/api";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { RoleGate } from "@/components/ui/RoleGate";
import type { Project, SystemType } from "@/types";
import { useState } from "react";

const schema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  system_type: z.enum(["WEB", "SAP_FIORI", "API", "MOBILE", "DESKTOP"] as const),
  base_url: z.string().url().optional().or(z.literal("")),
  status: z.enum(["ACTIVE", "ARCHIVED"] as const),
});

type FormData = z.infer<typeof schema>;

export function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiGet<Project>(`/api/v1/projects/${projectId}`),
    enabled: !!projectId,
  });

  const { register, handleSubmit, formState: { errors, isDirty } } = useForm<FormData>({
    resolver: zodResolver(schema),
    values: project
      ? {
          name: project.name,
          description: project.description ?? "",
          system_type: project.system_type,
          base_url: project.base_url ?? "",
          status: project.status,
        }
      : undefined,
  });

  const update = useMutation({
    mutationFn: (data: FormData) =>
      apiPatch<Project>(`/api/v1/projects/${projectId}`, {
        ...data,
        description: data.description || null,
        base_url: data.base_url || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", projectId] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const del = useMutation({
    mutationFn: () => apiDelete(`/api/v1/projects/${projectId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate("/projects");
    },
  });

  if (isLoading) return <div className="h-32 bg-muted animate-pulse rounded" />;
  if (!project) return <div className="text-muted-foreground">Project not found.</div>;

  return (
    <div className="max-w-xl space-y-8">
      <h1 className="text-2xl font-bold">Project Settings</h1>

      <form onSubmit={handleSubmit((d) => update.mutate(d))} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <input {...register("name")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea {...register("description")} rows={3} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">System Type</label>
          <select {...register("system_type")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
            {(["WEB", "SAP_FIORI", "API", "MOBILE", "DESKTOP"] as SystemType[]).map((t) => (
              <option key={t} value={t}>{t.replace("_", " ")}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Base URL</label>
          <input {...register("base_url")} type="url" className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          {errors.base_url && <p className="text-xs text-red-600 mt-1">{errors.base_url.message}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Status</label>
          <select {...register("status")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
            <option value="ACTIVE">Active</option>
            <option value="ARCHIVED">Archived</option>
          </select>
        </div>

        {update.isSuccess && <p className="text-sm text-green-600">Settings saved.</p>}
        {update.isError && <p className="text-sm text-red-600">Failed to save.</p>}

        <button
          type="submit"
          disabled={!isDirty || update.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {update.isPending ? "Saving…" : "Save Changes"}
        </button>
      </form>

      <RoleGate permission="project:delete">
        <div className="border border-red-200 rounded-xl p-5 space-y-3">
          <h2 className="font-semibold text-red-700">Danger Zone</h2>
          <p className="text-sm text-muted-foreground">
            Deleting this project is irreversible. All data will be permanently removed.
          </p>
          <button
            onClick={() => setConfirmDelete(true)}
            className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Delete Project
          </button>
        </div>
      </RoleGate>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete Project"
        description={`Are you sure you want to delete "${project.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={() => del.mutate()}
      />
    </div>
  );
}
