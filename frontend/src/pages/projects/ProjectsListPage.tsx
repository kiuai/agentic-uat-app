import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, FolderKanban, Search } from "lucide-react";
import { useState } from "react";
import { apiGet } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import type { Project } from "@/types";

export function ProjectsListPage() {
  const [search, setSearch] = useState("");

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiGet<Project[]>("/api/v1/projects"),
    staleTime: 60_000,
  });

  const filtered = projects?.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projects</h1>
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

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search projects…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="border rounded-xl p-5 h-32 animate-pulse bg-muted" />
          ))}
        </div>
      ) : !filtered?.length ? (
        <div className="text-center py-16 border rounded-xl">
          <FolderKanban className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium">
            {search ? "No projects match your search" : "No projects yet"}
          </p>
          {!search && (
            <RoleGate permission="project:create">
              <Link
                to="/projects/new"
                className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Create first project
              </Link>
            </RoleGate>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((p) => (
            <Link
              key={p.id}
              to={`/projects/${p.id}`}
              className="bg-card border rounded-xl p-5 hover:border-primary transition-colors block group"
            >
              <div className="flex items-start justify-between mb-2">
                <p className="font-semibold group-hover:text-primary transition-colors truncate flex-1">
                  {p.name}
                </p>
                <StatusBadge status={p.status} className="ml-2 shrink-0" />
              </div>
              {p.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">{p.description}</p>
              )}
              <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
                <span className="bg-muted px-2 py-0.5 rounded">{p.system_type}</span>
                <span>{new Date(p.created_at).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
