import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface SummaryReport {
  project_id: string;
  total_cycles: number;
  active_cycles: number;
  total_executions: number;
  passed: number;
  failed: number;
  blocked: number;
  not_started: number;
  pass_rate: number;
}

const COLORS: Record<string, string> = {
  passed: "#22c55e",
  failed: "#ef4444",
  blocked: "#f59e0b",
  not_started: "#94a3b8",
};

export function ReportsPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: summary, isLoading } = useQuery({
    queryKey: ["report-summary", projectId],
    queryFn: () => apiGet<SummaryReport>(`/api/v1/projects/${projectId}/reports/summary`),
  });

  if (isLoading) return <p className="text-muted-foreground">Loading report...</p>;

  const chartData = summary
    ? [
        { name: "Passed", value: summary.passed, key: "passed" },
        { name: "Failed", value: summary.failed, key: "failed" },
        { name: "Blocked", value: summary.blocked, key: "blocked" },
        { name: "Not Started", value: summary.not_started, key: "not_started" },
      ]
    : [];

  return (
    <div>
      <h2 className="text-xl font-bold mb-6">Reports</h2>
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-card border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Total Executions</p>
            <p className="text-3xl font-bold">{summary.total_executions}</p>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Pass Rate</p>
            <p className="text-3xl font-bold text-green-600">{summary.pass_rate}%</p>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Active Cycles</p>
            <p className="text-3xl font-bold">{summary.active_cycles}</p>
          </div>
          <div className="bg-card border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Total Cycles</p>
            <p className="text-3xl font-bold">{summary.total_cycles}</p>
          </div>
        </div>
      )}
      {chartData.length > 0 && (
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-medium mb-4">Execution Results</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value">
                {chartData.map((entry) => (
                  <Cell key={entry.key} fill={COLORS[entry.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
