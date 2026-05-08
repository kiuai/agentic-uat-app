import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Plus, Search, Upload, FileText } from "lucide-react";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import { PaginatedTable } from "@/components/ui/PaginatedTable";
import type { Requirement, RequirementStatus, RequirementPriority } from "@/types";
import { cn } from "@/utils/cn";

const PRIORITY_COLORS: Record<RequirementPriority, string> = {
  CRITICAL: "text-red-600 font-semibold",
  HIGH: "text-orange-600",
  MEDIUM: "text-yellow-600",
  LOW: "text-gray-500",
};

export function RequirementsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<RequirementStatus | "">("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  params.set("limit", String(pageSize));
  params.set("offset", String((page - 1) * pageSize));

  const { data: requirements, isLoading } = useQuery({
    queryKey: ["requirements", projectId, search, status, page],
    queryFn: () =>
      apiGet<Requirement[]>(
        `/api/v1/projects/${projectId}/requirements?${params}`
      ),
    enabled: !!projectId,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Requirements</h1>
        <div className="flex gap-2">
          <RoleGate permission="requirement:create">
            <Link
              to={`/projects/${projectId}/requirements/import`}
              className="flex items-center gap-2 px-3 py-2 border rounded-lg text-sm hover:bg-accent transition-colors"
            >
              <Upload className="h-4 w-4" />
              Import
            </Link>
          </RoleGate>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search requirements…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as RequirementStatus | ""); setPage(1); }}
          className="px-3 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="PROCESSED">Processed</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      <PaginatedTable
        isLoading={isLoading}
        data={requirements ?? []}
        rowKey={(r) => r.id}
        onRowClick={(r) => navigate(`/projects/${projectId}/requirements/${r.id}`)}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        emptyMessage="No requirements found. Import some to get started."
        columns={[
          {
            key: "title",
            header: "Title",
            cell: (r) => (
              <div>
                <p className="font-medium truncate max-w-xs">{r.title}</p>
                {r.business_domain && (
                  <p className="text-xs text-muted-foreground">{r.business_domain}</p>
                )}
              </div>
            ),
          },
          {
            key: "priority",
            header: "Priority",
            cell: (r) => (
              <span className={cn("text-sm", PRIORITY_COLORS[r.priority])}>
                {r.priority}
              </span>
            ),
            className: "w-24",
          },
          {
            key: "source",
            header: "Source",
            cell: (r) => (
              <span className="text-xs bg-muted px-2 py-0.5 rounded">{r.source_type}</span>
            ),
            className: "w-24",
          },
          {
            key: "status",
            header: "Status",
            cell: (r) => <StatusBadge status={r.status} />,
            className: "w-28",
          },
          {
            key: "date",
            header: "Added",
            cell: (r) => (
              <span className="text-xs text-muted-foreground">
                {new Date(r.created_at).toLocaleDateString()}
              </span>
            ),
            className: "w-28",
          },
        ]}
      />
    </div>
  );
}
