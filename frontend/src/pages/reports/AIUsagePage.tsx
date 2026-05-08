import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { apiGet } from "@/services/api";
import type { AIUsageReport } from "@/types";
import { Cpu } from "lucide-react";

export function AIUsagePage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data, isLoading } = useQuery({
    queryKey: ["report-ai-usage", projectId],
    queryFn: () =>
      apiGet<AIUsageReport>(`/api/v1/projects/${projectId}/reports/ai-usage`),
    enabled: !!projectId,
  });

  const chartData = data
    ? [
        { name: "Total Jobs", value: data.total_jobs, fill: "#6366f1" },
        { name: "Completed", value: data.completed_jobs, fill: "#22c55e" },
        { name: "Failed", value: data.failed_jobs, fill: "#ef4444" },
        { name: "Scripts Generated", value: data.total_scripts_generated, fill: "#3b82f6" },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Cpu className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">AI Usage Report</h1>
      </div>

      <div className="flex gap-2 text-sm text-muted-foreground">
        <Link to={`/projects/${projectId}/reports`} className="hover:text-foreground underline-offset-2 hover:underline">
          Coverage
        </Link>
        <span>·</span>
        <span className="text-foreground">AI Usage</span>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="h-32 animate-pulse bg-muted rounded-xl" />
          <div className="h-64 animate-pulse bg-muted rounded-xl" />
        </div>
      ) : !data ? (
        <p className="text-muted-foreground">No data available.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {chartData.map(({ name, value, fill }) => (
              <div key={name} className="bg-card border rounded-xl p-5 text-center">
                <p className="text-3xl font-bold" style={{ color: fill }}>{value}</p>
                <p className="text-sm text-muted-foreground mt-1">{name}</p>
              </div>
            ))}
          </div>

          <div className="bg-card border rounded-xl p-5">
            <h2 className="font-semibold mb-4">Job Statistics</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} barSize={40}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="text-xs text-muted-foreground">
            Generated at {new Date(data.generated_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}
