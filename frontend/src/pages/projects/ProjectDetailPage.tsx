import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Code2,
  PlayCircle,
  Globe,
  BarChart3,
  Settings,
  ExternalLink,
} from "lucide-react";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import type { Project, ProjectDashboard } from "@/types";

interface QuickLinkProps {
  to: string;
  icon: React.ElementType;
  label: string;
  count?: number;
  permission?: string;
}

function QuickLink({ to, icon: Icon, label, count }: QuickLinkProps) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 bg-card border rounded-xl p-4 hover:border-primary transition-colors group"
    >
      <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div className="flex-1">
        <p className="font-medium text-sm group-hover:text-primary transition-colors">{label}</p>
        {count !== undefined && (
          <p className="text-xs text-muted-foreground">{count} items</p>
        )}
      </div>
      <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </Link>
  );
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiGet<Project>(`/api/v1/projects/${projectId}`),
    enabled: !!projectId,
  });

  const { data: dash } = useQuery({
    queryKey: ["dashboard", projectId],
    queryFn: () => apiGet<ProjectDashboard>(`/api/v1/projects/${projectId}/dashboard`),
    enabled: !!projectId,
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 bg-muted animate-pulse rounded w-1/3" />
        <div className="h-24 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 bg-muted animate-pulse rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!project) {
    return <div className="text-center py-16 text-muted-foreground">Project not found.</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <StatusBadge status={project.status} />
          </div>
          {project.description && (
            <p className="text-muted-foreground text-sm mt-1">{project.description}</p>
          )}
          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
            <span className="bg-muted px-2 py-0.5 rounded">{project.system_type}</span>
            {project.base_url && (
              <a
                href={project.base_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary underline-offset-2 hover:underline"
              >
                {project.base_url}
              </a>
            )}
            <span>Created {new Date(project.created_at).toLocaleDateString()}</span>
          </div>
        </div>
        <RoleGate permission="project:update">
          <Link
            to={`/projects/${projectId}/settings`}
            className="flex items-center gap-2 px-3 py-1.5 border rounded-lg text-sm hover:bg-accent transition-colors"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
        </RoleGate>
      </div>

      {/* Stats */}
      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Requirements", value: dash.total_requirements },
            { label: "Pending Reqs", value: dash.pending_requirements },
            { label: "Test Scripts", value: dash.total_scripts },
            { label: "Approved Scripts", value: dash.approved_scripts },
            { label: "Active Cycles", value: dash.active_cycles },
            { label: "Pass Rate", value: `${dash.pass_rate.toFixed(0)}%` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-card border rounded-xl p-3 text-center">
              <p className="text-xl font-bold">{value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Quick links */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Navigate
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <QuickLink
            to={`/projects/${projectId}/requirements`}
            icon={FileText}
            label="Requirements"
            count={dash?.total_requirements}
            permission="requirement:read"
          />
          <QuickLink
            to={`/projects/${projectId}/scripts`}
            icon={Code2}
            label="Test Scripts"
            count={dash?.total_scripts}
            permission="script:read"
          />
          <QuickLink
            to={`/projects/${projectId}/cycles`}
            icon={PlayCircle}
            label="Test Cycles"
            count={dash?.total_cycles}
            permission="cycle:read"
          />
          <QuickLink
            to={`/projects/${projectId}/crawler`}
            icon={Globe}
            label="Crawler"
            permission="crawler:read"
          />
          <QuickLink
            to={`/projects/${projectId}/reports`}
            icon={BarChart3}
            label="Reports"
            permission="report:read"
          />
          <RoleGate permission="project:update">
            <QuickLink
              to={`/projects/${projectId}/settings`}
              icon={Settings}
              label="Settings"
              permission="project:update"
            />
          </RoleGate>
        </div>
      </div>
    </div>
  );
}
