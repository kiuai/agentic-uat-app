import { Link } from "react-router-dom";
import { useProjects, useCreateProject } from "@/hooks/useProjects";
import { useState } from "react";

export function ProjectsPage() {
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createProject.mutateAsync({ name });
    setName("");
    setShowCreate(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90"
        >
          New Project
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="bg-card border rounded-lg p-4 mb-4 flex gap-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            required
            className="flex-1 border rounded px-3 py-2 text-sm"
          />
          <button type="submit" className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm">
            Create
          </button>
          <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm">
            Cancel
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-muted-foreground">Loading projects...</p>
      ) : (
        <div className="grid gap-3">
          {projects?.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="bg-card border rounded-lg p-4 hover:border-primary transition-colors flex items-center justify-between"
            >
              <div>
                <p className="font-medium">{project.name}</p>
                {project.description && (
                  <p className="text-sm text-muted-foreground">{project.description}</p>
                )}
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${
                project.status === "ACTIVE" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
              }`}>
                {project.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
