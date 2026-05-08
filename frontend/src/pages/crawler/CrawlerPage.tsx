import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Globe, Loader2, RefreshCw, X } from "lucide-react";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import { usePolling } from "@/hooks/usePolling";
import type { CrawlJob } from "@/types";

const schema = z.object({
  target_url: z.string().url("Enter a valid URL"),
  max_pages: z.coerce.number().int().min(1).max(500).default(50),
});

type FormData = z.infer<typeof schema>;

function JobRow({
  job,
  onCancel,
}: {
  job: CrawlJob;
  projectId: string;
  onCancel: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg text-sm">
      <StatusBadge status={job.status} />
      <div className="flex-1 min-w-0">
        <p className="font-mono text-xs truncate">{job.id.slice(0, 12)}…</p>
        <p className="text-xs text-muted-foreground">
          {new Date(job.created_at).toLocaleString()}
          {job.completed_at && ` → ${new Date(job.completed_at).toLocaleString()}`}
        </p>
      </div>
      {job.error_message && (
        <p className="text-xs text-red-600 max-w-xs truncate">{job.error_message}</p>
      )}
      {["PENDING", "PROCESSING"].includes(job.status) && (
        <>
          <Loader2 className="h-4 w-4 animate-spin text-blue-600 shrink-0" />
          <RoleGate permission="crawler:cancel">
            <button
              onClick={() => onCancel(job.id)}
              className="text-muted-foreground hover:text-red-600 transition-colors"
              title="Cancel"
            >
              <X className="h-4 w-4" />
            </button>
          </RoleGate>
        </>
      )}
    </div>
  );
}

export function CrawlerPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const qc = useQueryClient();

  const { data: jobs, refetch, isLoading } = useQuery({
    queryKey: ["crawler-jobs", projectId],
    queryFn: () => apiGet<CrawlJob[]>(`/api/v1/projects/${projectId}/crawl-jobs`),
    enabled: !!projectId,
    staleTime: 10_000,
  });

  const hasActiveJobs = jobs?.some((j) => ["PENDING", "PROCESSING"].includes(j.status));

  usePolling(() => refetch(), {
    interval: 3000,
    enabled: !!hasActiveJobs,
  });

  const { register, handleSubmit, formState: { errors }, reset } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { max_pages: 50 },
  });

  const trigger = useMutation({
    mutationFn: (data: FormData) =>
      apiPost<CrawlJob>(`/api/v1/projects/${projectId}/crawl`, {
        target_url: data.target_url,
        max_pages: data.max_pages,
        crawler_type: "WEB",
        generate_scripts: true,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["crawler-jobs", projectId] });
      reset();
    },
  });

  // Cancel uses POST /crawl-jobs/{id}/cancel (not DELETE)
  const cancel = useMutation({
    mutationFn: (jobId: string) =>
      apiPost(`/api/v1/crawl-jobs/${jobId}/cancel`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crawler-jobs", projectId] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Web Crawler</h1>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-sm hover:bg-accent transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <RoleGate permission="crawler:create">
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <Globe className="h-4 w-4" />
            New Crawl Job
          </h2>
          <form onSubmit={handleSubmit((d) => trigger.mutate(d))} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Target URL *</label>
              <input
                {...register("target_url")}
                type="url"
                placeholder="https://app.example.com"
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              {errors.target_url && (
                <p className="text-xs text-red-600 mt-1">{errors.target_url.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Max Pages</label>
              <input
                {...register("max_pages")}
                type="number"
                min="1"
                max="500"
                className="w-32 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>

            {trigger.isError && <p className="text-xs text-red-600">Failed to start crawl.</p>}

            <button
              type="submit"
              disabled={trigger.isPending || !!hasActiveJobs}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {trigger.isPending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting…
                </span>
              ) : hasActiveJobs ? (
                "Crawl in progress…"
              ) : (
                "Start Crawl"
              )}
            </button>
          </form>
        </div>
      </RoleGate>

      <div>
        <h2 className="font-semibold mb-3">Crawl History</h2>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse bg-muted rounded-lg" />
            ))}
          </div>
        ) : !jobs?.length ? (
          <p className="text-sm text-muted-foreground">No crawl jobs yet.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                projectId={projectId!}
                onCancel={(id) => cancel.mutate(id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
