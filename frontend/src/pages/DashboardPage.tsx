import { useProjects } from "@/hooks/useProjects";

export function DashboardPage() {
  const { data: projects, isLoading } = useProjects();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <p className="text-sm text-muted-foreground">Active Projects</p>
          <p className="text-3xl font-bold mt-1">
            {isLoading ? "—" : projects?.length ?? 0}
          </p>
        </div>
      </div>
    </div>
  );
}
