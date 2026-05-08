import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiPost } from "@/services/api";
import apiClient from "@/services/api";
import { FileUploadZone } from "@/components/ui/FileUploadZone";
import type { Requirement } from "@/types";

const textSchema = z.object({
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  content_text: z.string().min(10, "Content must be at least 10 characters"),
  priority: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const),
  business_domain: z.string().optional(),
});

type TextForm = z.infer<typeof textSchema>;

type TabType = "text" | "file";

export function ImportRequirementsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabType>("text");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const { register, handleSubmit, formState: { errors } } = useForm<TextForm>({
    resolver: zodResolver(textSchema),
    defaultValues: { priority: "MEDIUM" },
  });

  const createText = useMutation({
    mutationFn: (data: TextForm) =>
      apiPost<Requirement>(`/api/v1/projects/${projectId}/requirements`, {
        ...data,
        source_type: "TEXT",
        description: data.description || null,
        business_domain: data.business_domain || null,
      }),
    onSuccess: (req) => {
      qc.invalidateQueries({ queryKey: ["requirements", projectId] });
      navigate(`/projects/${projectId}/requirements/${req.id}`);
    },
  });

  const uploadFileMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("No file selected");
      const fd = new FormData();
      fd.append("file", uploadFile);
      const ext = uploadFile.name.split(".").pop()?.toUpperCase() as "DOCX" | "PDF";
      fd.append("source_type", ext || "DOCX");
      const res = await apiClient.post<Requirement>(
        `/api/v1/projects/${projectId}/requirements/upload`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return res.data;
    },
    onSuccess: (req) => {
      qc.invalidateQueries({ queryKey: ["requirements", projectId] });
      navigate(`/projects/${projectId}/requirements/${req.id}`);
    },
  });

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Import Requirements</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Add requirements as text or upload a document.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex border-b">
        {(["text", "file"] as TabType[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "text" ? "Enter Text" : "Upload File"}
          </button>
        ))}
      </div>

      {tab === "text" ? (
        <form onSubmit={handleSubmit((d) => createText.mutate(d))} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input {...register("title")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            {errors.title && <p className="text-xs text-red-600 mt-1">{errors.title.message}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea {...register("description")} rows={2} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none" />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Requirement Content *</label>
            <textarea {...register("content_text")} rows={6} placeholder="Describe the requirement in detail…" className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none" />
            {errors.content_text && <p className="text-xs text-red-600 mt-1">{errors.content_text.message}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Priority</label>
              <select {...register("priority")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Business Domain</label>
              <input {...register("business_domain")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" placeholder="e.g. Finance" />
            </div>
          </div>

          {createText.isError && <p className="text-sm text-red-600">Failed to create requirement.</p>}

          <div className="flex gap-3">
            <button type="button" onClick={() => navigate(-1)} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
            <button type="submit" disabled={createText.isPending} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
              {createText.isPending ? "Saving…" : "Save Requirement"}
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-4">
          <FileUploadZone
            accept=".docx,.pdf"
            onFiles={(files) => setUploadFile(files[0] ?? null)}
          />
          {uploadFileMutation.isError && <p className="text-sm text-red-600">Upload failed.</p>}
          <div className="flex gap-3">
            <button type="button" onClick={() => navigate(-1)} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
            <button
              onClick={() => uploadFileMutation.mutate()}
              disabled={!uploadFile || uploadFileMutation.isPending}
              className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {uploadFileMutation.isPending ? "Uploading…" : "Upload & Process"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
