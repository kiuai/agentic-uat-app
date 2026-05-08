import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/services/api";
import type { Project, SystemType } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name is required").max(120),
  description: z.string().optional(),
  system_type: z.enum(["WEB", "SAP_FIORI", "API", "MOBILE", "DESKTOP"] as const),
  base_url: z.string().url("Must be a valid URL").optional().or(z.literal("")),
});

type FormData = z.infer<typeof schema>;

const SYSTEM_TYPES: SystemType[] = ["WEB", "SAP_FIORI", "API", "MOBILE", "DESKTOP"];

export function NewProjectPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { system_type: "WEB" },
  });

  const create = useMutation({
    mutationFn: (data: FormData) =>
      apiPost<Project>("/api/v1/projects", {
        ...data,
        base_url: data.base_url || null,
        description: data.description || null,
      }),
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
  });

  const onSubmit = (data: FormData) => create.mutate(data);

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">New Project</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Create a new KAATS project for your application under test.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">
            Project Name <span className="text-red-500">*</span>
          </label>
          <input
            {...register("name")}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="My Application"
          />
          {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            {...register("description")}
            rows={3}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
            placeholder="Optional project description…"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">
            System Type <span className="text-red-500">*</span>
          </label>
          <select
            {...register("system_type")}
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 bg-background"
          >
            {SYSTEM_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Base URL</label>
          <input
            {...register("base_url")}
            type="url"
            className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="https://app.example.com"
          />
          {errors.base_url && (
            <p className="text-xs text-red-600 mt-1">{errors.base_url.message}</p>
          )}
        </div>

        {create.isError && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
            Failed to create project. Please try again.
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="px-4 py-2 border rounded-lg text-sm hover:bg-accent transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || create.isPending}
            className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {create.isPending ? "Creating…" : "Create Project"}
          </button>
        </div>
      </form>
    </div>
  );
}
