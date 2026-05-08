import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import type { Project, Job, TestScript, ProjectDashboard } from "@/types";
import { FolderKanban, Code2, PlayCircle, Cpu, Plus } from "lucide-react";

function StatCard({
  label,
  value,
  icon: Icon,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ElementType;
  sub?: string;
}) {
  return (
    <div className="bg-card border rounded-xl p-5 flex gap-4">
      {Icon && (
        <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      )}
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold mt-0.5">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function ProjectDashboardCard({ project }: { project: Project }) {
  const { data: dash } = useQuery({
    queryKey: ["dashboard", project.id],
    queryFn: () => apiGet<ProjectDashboard>(`/api/v1/projects/${project.id}/dashboard`),
    staleTime: 60_000,
  });

  const chartData = dash
    ? [
        { name: "Passed", value: Math.round(dash.pass_rate), fill: "#22c55e" },
        { name: "Remaining", value: 100 - Math.round(dash.pass_rate), fill: "#e5e7eb" },
      ]
    : [];

  return (
    <Link
      to={`/projects/${project.id}`}
      className="bg-card border rounded-xl p-5 hover:border-primary transition-colors block"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate">{project.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{project.system_type}</p>
        </div>
        <StatusBadge status={project.status} className="ml-2 shrink-0" />
      </div>

      {dash ? (
        <div className="grid grid-cols-3 gap-2 text-center text-xs mt-3">
          <div>
            <p className="text-lg font-bold">{dash.total_requirements}</p>
            <p className="text-muted-foreground">Requirements</p>
          </div>
          <div>
            <p className="text-lg font-bold">{dash.approved_scripts}</p>
            <p className="text-muted-foreground">Scripts</p>
          </div>
          <div>
            <p className="text-lg font-bold">{dash.pass_rate.toFixed(0)}%</p>
            <p className="text-muted-foreground">Pass rate</p>
          </div>
        </div>
      ) : (
        <div className="h-12 bg-muted animate-pulse rounded mt-3" />
      )}
    </Link>
  );
}

function RecentJobsTable({ projectId }: { projectId: string }) {
  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => apiGet<Job[]>(`/api/v1/projects/${projectId}/generation-jobs`),
    staleTime: 30_000,
  });

  if (!jobs?.length) return null;

  return (
    <div className="space-y-1">
      {jobs.slice(0, 4).map((job) => (
        <div key={job.id} className="flex items-center gap-3 text-sm py-1">
          <StatusBadge status={job.status} />
          <span className="font-mono text-xs text-muted-foreground flex-1 truncate">
            {job.id.slice(0, 8)}…
          </span>
          <span className="text-xs text-muted-foreground shrink-0">
            {new Date(job.created_at).toLocaleDateString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function ApprovalQueue({ projectId, projectName }: { projectId: string; projectName: string }) {
  const { data: scripts } = useQuery({
    queryKey: ["scripts", projectId, "IN_REVIEW"],
    queryFn: () =>
      apiGet<TestScript[]>(`/api/v1/projects/${projectId}/test-scripts?status_filter=IN_REVIEW`),
    staleTime: 30_000,
  });

  if (!scripts?.length) return null;

  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase font-medium mb-1">{projectName}</p>
      <div className="space-y-1">
        {scripts.slice(0, 3).map((s) => (
          <Link
            key={s.id}
            to={`/projects/${projectId}/scripts/${s.id}`}
            className="flex items-center gap-2 text-sm hover:text-primary transition-colors py-0.5"
          >
            <span className="h-2 w-2 rounded-full bg-yellow-400 shrink-0" />
            <span className="truncate">{s.title}</span>
          </Link>
        ))}
        {scripts.length > 3 && (
          <Link
            to={`/projects/${projectId}/scripts`}
            className="text-xs text-primary hover:underline"
          >
            +{scripts.length - 3} more
          </Link>
        )}
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiGet<Project[]>("/api/v1/projects"),
    staleTime: 60_000,
  });

  const activeProjects = projects?.filter((p) => p.status === "ACTIVE") ?? [];
  const archivedCount = (projects?.length ?? 0) - activeProjects.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-0.5">Welcome back to KAATS</p>
        </div>
        <RoleGate permission="project:create">
          <Link
            to="/projects/new"
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Project
          </Link>
        </RoleGate>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active Projects"
          value={isLoading ? "—" : activeProjects.length}
          icon={FolderKanban}
          sub={archivedCount > 0 ? `${archivedCount} archived` : undefined}
        />
        <StatCard label="Total Scripts" value="—" icon={Code2} sub="Across all projects" />
        <StatCard label="Active Cycles" value="—" icon={PlayCircle} sub="In progress" />
        <StatCard label="AI Jobs Today" value="—" icon={Cpu} sub="Generation runs" />
      </div>

      {/* Projects grid */}
      {!isLoading && activeProjects.length > 0 && (
        <section>
          <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide mb-3">
            Active Projects
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {activeProjects.map((p) => (
              <ProjectDashboardCard key={p.id} project={p} />
            ))}
          </div>
        </section>
      )}

      {!isLoading && activeProjects.length === 0 && (
        <div className="text-center py-16 border rounded-xl bg-card">
          <FolderKanban className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium">No projects yet</p>
          <p className="text-sm text-muted-foreground mt-1 mb-4">
            Create your first project to get started.
          </p>
          <RoleGate permission="project:create">
            <Link
              to="/projects/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              New Project
            </Link>
          </RoleGate>
        </div>
      )}

      {/* Bottom panels */}
      {activeProjects.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-card border rounded-xl p-5">
            <h2 className="font-semibold mb-4">Recent AI Jobs</h2>
            {activeProjects.length === 0 ? (
              <p className="text-sm text-muted-foreground">No projects.</p>
            ) : (
              <div className="space-y-4">
                {activeProjects.slice(0, 2).map((p) => (
                  <div key={p.id}>
                    <p className="text-xs text-muted-foreground uppercase mb-1">{p.name}</p>
                    <RecentJobsTable projectId={p.id} />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-card border rounded-xl p-5">
            <h2 className="font-semibold mb-4">Scripts Awaiting Approval</h2>
            <div className="space-y-3">
              {activeProjects.slice(0, 3).map((p) => (
                <ApprovalQueue key={p.id} projectId={p.id} projectName={p.name} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
