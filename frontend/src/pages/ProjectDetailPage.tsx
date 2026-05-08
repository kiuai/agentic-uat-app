import { useParams, Link } from "react-router-dom";
import { useProject } from "@/hooks/useProjects";

const sections = [
  { to: "requirements", label: "Requirements" },
  { to: "scripts", label: "Test Scripts" },
  { to: "cycles", label: "Test Cycles" },
  { to: "crawler", label: "Crawler" },
  { to: "reports", label: "Reports" },
];

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading } = useProject(projectId!);

  if (isLoading) return <p className="text-muted-foreground">Loading...</p>;
  if (!project) return <p className="text-destructive">Project not found.</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">{project.name}</h1>
      {project.description && (
        <p className="text-muted-foreground mb-6">{project.description}</p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {sections.map(({ to, label }) => (
          <Link
            key={to}
            to={`/projects/${projectId}/${to}`}
            className="bg-card border rounded-lg p-4 text-center hover:border-primary transition-colors"
          >
            <p className="font-medium text-sm">{label}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
