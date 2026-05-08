import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { CycleSummaryReport } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  passed: "#22c55e",
  failed: "#ef4444",
  blocked: "#f97316",
  in_progress: "#3b82f6",
  not_started: "#d1d5db",
};

export function CycleSummaryPage() {
  const { projectId, cycleId } = useParams<{ projectId: string; cycleId: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ["report-cycle", cycleId],
    queryFn: () =>
      apiGet<CycleSummaryReport>(
        `/api/v1/projects/${projectId}/reports/cycles/${cycleId}/summary`
      ),
    enabled: !!cycleId,
  });

  if (isLoading) {
    return <div className="h-40 animate-pulse bg-muted rounded-xl" />;
  }

  if (!data) return <p className="text-muted-foreground">No data available.</p>;

  const pieData = [
    { name: "Passed", value: data.passed, fill: STATUS_COLORS.passed },
    { name: "Failed", value: data.failed, fill: STATUS_COLORS.failed },
    { name: "Blocked", value: data.blocked, fill: STATUS_COLORS.blocked },
    { name: "In Progress", value: data.in_progress, fill: STATUS_COLORS.in_progress },
    { name: "Not Started", value: data.not_started, fill: STATUS_COLORS.not_started },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
          <Link to={`/projects/${projectId}/reports`} className="hover:text-foreground">Reports</Link>
          <span>/</span>
          <span>Cycle Summary</span>
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{data.cycle_name}</h1>
          <StatusBadge status={data.status} />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: "Total", value: data.total_assignments, color: "" },
          { label: "Passed", value: data.passed, color: "text-green-600" },
          { label: "Failed", value: data.failed, color: "text-red-600" },
          { label: "Blocked", value: data.blocked, color: "text-orange-600" },
          { label: "Pass Rate", value: `${data.pass_rate}%`, color: "text-primary" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-card border rounded-xl p-4 text-center">
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Chart */}
      {pieData.length > 0 && (
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-3">Execution Breakdown</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={pieData}
                innerRadius={70}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip />
              <Legend iconType="circle" iconSize={8} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Dates */}
      {(data.started_at || data.completed_at) && (
        <div className="bg-card border rounded-xl p-5">
          <h2 className="font-semibold mb-3">Timeline</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {data.started_at && (
              <div>
                <p className="text-muted-foreground text-xs">Started</p>
                <p>{new Date(data.started_at).toLocaleDateString()}</p>
              </div>
            )}
            {data.completed_at && (
              <div>
                <p className="text-muted-foreground text-xs">Completed</p>
                <p>{new Date(data.completed_at).toLocaleDateString()}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
