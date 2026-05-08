import { Link } from "react-router-dom";
import { useProjects } from "@/hooks/useProjects";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { Job, TestScript } from "@/types";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="bg-card border rounded-lg p-6">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

const JOB_STATUS_COLORS: Record<string, string> = {
  PENDING: "bg-gray-100 text-gray-600",
  PROCESSING: "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-gray-100 text-gray-400",
};

function RecentJobsSection({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => apiGet<Job[]>(`/api/v1/projects/${projectId}/generation-jobs`),
    staleTime: 30_000,
  });

  const recent = jobs?.slice(0, 3);
  if (!recent?.length) return null;

  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
        {projectName}
      </p>
      <div className="space-y-1">
        {recent.map((job) => (
          <div key={job.id} className="flex items-center gap-3 text-sm">
            <span
              className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${JOB_STATUS_COLORS[job.status]}`}
            >
              {job.status}
            </span>
            <span className="text-muted-foreground font-mono text-xs truncate">
              {job.id.slice(0, 8)}…
            </span>
            <span className="text-xs text-muted-foreground shrink-0">
              {new Date(job.created_at).toLocaleDateString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalQueueSection({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  const { data: scripts } = useQuery({
    queryKey: ["test-scripts", projectId, { status: "IN_REVIEW" }],
    queryFn: () =>
      apiGet<TestScript[]>(
        `/api/v1/projects/${projectId}/test-scripts?status_filter=IN_REVIEW`
      ),
    staleTime: 30_000,
  });

  if (!scripts?.length) return null;

  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
        {projectName}
      </p>
      <div className="space-y-1">
        {scripts.slice(0, 5).map((script) => (
          <Link
            key={script.id}
            to={`/projects/${projectId}/scripts`}
            className="flex items-center gap-2 text-sm hover:text-primary transition-colors"
          >
            <span className="text-yellow-600 shrink-0">●</span>
            <span className="truncate">{script.title}</span>
          </Link>
        ))}
        {scripts.length > 5 && (
          <p className="text-xs text-muted-foreground">+{scripts.length - 5} more</p>
        )}
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: projects, isLoading } = useProjects();

  const activeProjects = projects?.filter((p) => p.status === "ACTIVE") ?? [];
  const totalProjects = projects?.length ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* KPI row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Active Projects"
          value={isLoading ? "—" : activeProjects.length}
          sub={totalProjects > activeProjects.length ? `${totalProjects - activeProjects.length} archived` : undefined}
        />
        <StatCard label="Pending AI Jobs" value="—" sub="Across all projects" />
        <StatCard label="Scripts Awaiting Approval" value="—" sub="In review" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent generation jobs */}
        <div className="bg-card border rounded-lg p-5">
          <h2 className="font-semibold mb-4">Recent Generation Jobs</h2>
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : activeProjects.length === 0 ? (
            <p className="text-muted-foreground text-sm">No projects yet.</p>
          ) : (
            <div className="space-y-4">
              {activeProjects.slice(0, 3).map((p) => (
                <RecentJobsSection key={p.id} projectId={p.id} projectName={p.name} />
              ))}
            </div>
          )}
        </div>

        {/* Approval queue */}
        <div className="bg-card border rounded-lg p-5">
          <h2 className="font-semibold mb-4">Scripts Awaiting Approval</h2>
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading…</p>
          ) : activeProjects.length === 0 ? (
            <p className="text-muted-foreground text-sm">No projects yet.</p>
          ) : (
            <div className="space-y-4">
              {activeProjects.slice(0, 3).map((p) => (
                <ApprovalQueueSection key={p.id} projectId={p.id} projectName={p.name} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Projects quick-access */}
      {!isLoading && activeProjects.length > 0 && (
        <div className="mt-6">
          <h2 className="font-semibold mb-3">Projects</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {activeProjects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="bg-card border rounded-lg p-4 hover:border-primary transition-colors"
              >
                <p className="font-medium text-sm">{p.name}</p>
                {p.description && (
                  <p className="text-xs text-muted-foreground mt-1 truncate">{p.description}</p>
                )}
                <p className="text-xs text-muted-foreground mt-2">
                  Created {new Date(p.created_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
