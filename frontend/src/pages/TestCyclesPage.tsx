import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { TestCycle } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  ACTIVE: "bg-green-100 text-green-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  LOCKED: "bg-purple-100 text-purple-700",
};

export function TestCyclesPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: cycles, isLoading } = useQuery({
    queryKey: ["cycles", projectId],
    queryFn: () => apiGet<TestCycle[]>(`/api/v1/projects/${projectId}/cycles`),
  });

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Test Cycles</h2>
      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="space-y-2">
          {cycles?.map((cycle) => (
            <div key={cycle.id} className="bg-card border rounded-lg p-4 flex items-center justify-between">
              <div>
                <p className="font-medium">{cycle.name}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {cycle.start_date ?? "No start date"} — {cycle.end_date ?? "No end date"}
                </p>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[cycle.status]}`}>
                {cycle.status}
              </span>
            </div>
          ))}
          {cycles?.length === 0 && (
            <p className="text-muted-foreground text-sm">No test cycles yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
