import { useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { apiPost } from "@/services/api";
import { useState } from "react";
import { useJob } from "@/hooks/useJobs";
import type { Job } from "@/types";

export function CrawlerPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [targetUrl, setTargetUrl] = useState("");
  const [crawlerType, setCrawlerType] = useState<"WEB" | "SAP_FIORI">("WEB");
  const [jobId, setJobId] = useState<string | null>(null);

  const { data: jobStatus } = useJob(jobId ?? "", { enabled: !!jobId });

  const triggerCrawl = useMutation({
    mutationFn: () =>
      apiPost<Job>(`/api/v1/projects/${projectId}/crawl-jobs`, {
        crawler_type: crawlerType,
        target_url: crawlerType === "WEB" ? targetUrl : undefined,
        launchpad_url: crawlerType === "SAP_FIORI" ? targetUrl : undefined,
        max_pages: 50,
        generate_scripts: true,
      }),
    onSuccess: (job) => setJobId(job.id),
  });

  return (
    <div>
      <h2 className="text-xl font-bold mb-6">Web / SAP Fiori Crawler</h2>
      <div className="bg-card border rounded-lg p-6 max-w-2xl">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Crawler Type</label>
            <div className="flex gap-2 mt-1">
              {(["WEB", "SAP_FIORI"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setCrawlerType(type)}
                  className={`px-4 py-2 rounded text-sm ${
                    crawlerType === type ? "bg-primary text-primary-foreground" : "bg-secondary"
                  }`}
                >
                  {type === "WEB" ? "Web UI" : "SAP Fiori"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">
              {crawlerType === "SAP_FIORI" ? "Launchpad URL" : "Target URL"}
            </label>
            <input
              type="url"
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
              placeholder={crawlerType === "SAP_FIORI" ? "https://fiori.example.com/..." : "https://app.example.com"}
              className="w-full border rounded px-3 py-2 text-sm mt-1"
            />
          </div>

          <button
            onClick={() => triggerCrawl.mutate()}
            disabled={!targetUrl || triggerCrawl.isPending}
            className="bg-primary text-primary-foreground px-6 py-2 rounded text-sm font-medium disabled:opacity-50 w-full"
          >
            {triggerCrawl.isPending ? "Submitting..." : "Start Crawl"}
          </button>
        </div>

        {jobStatus && (
          <div className="mt-4 p-3 bg-muted rounded text-sm">
            <p className="font-medium">Job Status: <span className={
              jobStatus.status === "COMPLETED" ? "text-green-600" :
              jobStatus.status === "FAILED" ? "text-red-600" : "text-yellow-600"
            }>{jobStatus.status}</span></p>
            {jobStatus.error_message && (
              <p className="text-destructive mt-1 text-xs">{jobStatus.error_message}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
