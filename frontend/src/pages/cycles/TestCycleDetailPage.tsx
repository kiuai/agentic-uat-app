import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Play, Plus, Users } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import type { TestCycle, TestAssignment, TestScript } from "@/types";

const PIE_COLORS: Record<string, string> = {
  PASSED: "#22c55e",
  FAILED: "#ef4444",
  BLOCKED: "#f97316",
  IN_PROGRESS: "#3b82f6",
  NOT_STARTED: "#d1d5db",
  SKIPPED: "#9ca3af",
};

export function TestCycleDetailPage() {
  const { projectId, cycleId } = useParams<{ projectId: string; cycleId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: cycle, isLoading } = useQuery({
    queryKey: ["cycle", cycleId],
    queryFn: () => apiGet<TestCycle>(`/api/v1/projects/${projectId}/cycles/${cycleId}`),
    enabled: !!cycleId,
  });

  const { data: assignments } = useQuery({
    queryKey: ["assignments", cycleId],
    queryFn: () =>
      apiGet<TestAssignment[]>(`/api/v1/projects/${projectId}/cycles/${cycleId}/executions`),
    enabled: !!cycleId,
    staleTime: 30_000,
  });

  const activate = useMutation({
    mutationFn: () =>
      apiPost(`/api/v1/projects/${projectId}/cycles/${cycleId}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cycle", cycleId] }),
  });

  if (isLoading) {
    return <div className="h-40 bg-muted animate-pulse rounded" />;
  }
  if (!cycle) return <div className="text-muted-foreground">Cycle not found.</div>;

  // Build pie data
  const statusCounts: Record<string, number> = {};
  for (const a of assignments ?? []) {
    statusCounts[a.status] = (statusCounts[a.status] ?? 0) + 1;
  }
  const pieData = Object.entries(statusCounts).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to={`/projects/${projectId}/cycles`} className="hover:text-foreground">Cycles</Link>
        <span>/</span>
        <span className="text-foreground font-medium">{cycle.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold">{cycle.name}</h1>
            <StatusBadge status={cycle.status} />
          </div>
          {cycle.description && (
            <p className="text-sm text-muted-foreground mt-1">{cycle.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          {cycle.status === "DRAFT" && (
            <RoleGate permission="cycle:update">
              <button
                onClick={() => activate.mutate()}
                disabled={activate.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                Activate
              </button>
            </RoleGate>
          )}
          <RoleGate permission="assignment:create">
            <Link
              to={`/projects/${projectId}/cycles/${cycleId}/assign`}
              className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm hover:bg-accent"
            >
              <Plus className="h-4 w-4" />
              Add Tests
            </Link>
          </RoleGate>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Donut chart */}
        {pieData.length > 0 && (
          <div className="bg-card border rounded-xl p-5 flex flex-col items-center">
            <h2 className="font-semibold mb-3 self-start">Execution Status</h2>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={PIE_COLORS[entry.name] ?? "#9ca3af"} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend iconType="circle" iconSize={8} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Assignment list */}
        <div className={`bg-card border rounded-xl p-5 ${pieData.length > 0 ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <h2 className="font-semibold mb-3">Assignments ({assignments?.length ?? 0})</h2>
          {!assignments?.length ? (
            <p className="text-sm text-muted-foreground">No assignments yet.</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {assignments.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center gap-3 p-3 border rounded-lg"
                >
                  <StatusBadge status={a.status} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-mono truncate">{a.script_id.slice(0, 8)}…</p>
                    {a.due_date && (
                      <p className="text-xs text-muted-foreground">
                        Due {new Date(a.due_date).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <RoleGate permission="result:create">
                    {["NOT_STARTED", "IN_PROGRESS"].includes(a.status) && (
                      <button
                        onClick={() =>
                          navigate(
                            `/projects/${projectId}/cycles/${cycleId}/execute/${a.id}`
                          )
                        }
                        className="text-xs px-2 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/90"
                      >
                        Execute
                      </button>
                    )}
                  </RoleGate>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
