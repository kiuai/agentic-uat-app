import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Plus, Search, Code2 } from "lucide-react";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import { PaginatedTable } from "@/components/ui/PaginatedTable";
import type { TestScript, ScriptStatus } from "@/types";

export function TestScriptsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ScriptStatus | "">("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status_filter", status);
  params.set("limit", String(pageSize));
  params.set("offset", String((page - 1) * pageSize));

  const { data: scripts, isLoading } = useQuery({
    queryKey: ["scripts", projectId, search, status, page],
    queryFn: () =>
      apiGet<TestScript[]>(`/api/v1/projects/${projectId}/test-scripts?${params}`),
    enabled: !!projectId,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Test Scripts</h1>
        <RoleGate permission="script:create">
          <Link
            to={`/projects/${projectId}/scripts/new`}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Script
          </Link>
        </RoleGate>
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search scripts…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as ScriptStatus | ""); setPage(1); }}
          className="px-3 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="IN_REVIEW">In Review</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="LOCKED">Locked</option>
        </select>
      </div>

      <PaginatedTable
        isLoading={isLoading}
        data={scripts ?? []}
        rowKey={(s) => s.id}
        onRowClick={(s) => navigate(`/projects/${projectId}/scripts/${s.id}`)}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        emptyMessage="No test scripts found."
        columns={[
          {
            key: "title",
            header: "Title",
            cell: (s) => (
              <div>
                <p className="font-medium">{s.title}</p>
                {s.is_ai_generated && (
                  <span className="text-xs text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">
                    AI generated
                  </span>
                )}
              </div>
            ),
          },
          {
            key: "format",
            header: "Format",
            cell: (s) => <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded">{s.format}</span>,
            className: "w-36",
          },
          {
            key: "version",
            header: "Version",
            cell: (s) => <span className="text-sm text-muted-foreground">v{s.current_version}</span>,
            className: "w-20",
          },
          {
            key: "status",
            header: "Status",
            cell: (s) => <StatusBadge status={s.status} />,
            className: "w-28",
          },
          {
            key: "date",
            header: "Updated",
            cell: (s) => (
              <span className="text-xs text-muted-foreground">
                {new Date(s.updated_at).toLocaleDateString()}
              </span>
            ),
            className: "w-28",
          },
        ]}
      />
    </div>
  );
}
