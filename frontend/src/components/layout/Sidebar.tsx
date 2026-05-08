import { Link, useLocation, useParams } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  Code2,
  PlayCircle,
  Globe,
  BarChart3,
  Users,
  Settings,
  ChevronRight,
  Shield,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { usePermission } from "@/hooks/usePermission";

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  permission?: string;
  exact?: boolean;
}

const topNav: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/projects", label: "Projects", icon: FolderKanban, permission: "project:read" },
  { to: "/users", label: "Users", icon: Users, permission: "user:read" },
  { to: "/admin", label: "Admin", icon: Shield, permission: "admin:company" },
];

function projectNav(projectId: string): NavItem[] {
  return [
    { to: `/projects/${projectId}`, label: "Overview", icon: LayoutDashboard, exact: true },
    { to: `/projects/${projectId}/requirements`, label: "Requirements", icon: FileText, permission: "requirement:read" },
    { to: `/projects/${projectId}/scripts`, label: "Test Scripts", icon: Code2, permission: "script:read" },
    { to: `/projects/${projectId}/cycles`, label: "Test Cycles", icon: PlayCircle, permission: "cycle:read" },
    { to: `/projects/${projectId}/crawler`, label: "Crawler", icon: Globe, permission: "crawler:read" },
    { to: `/projects/${projectId}/reports`, label: "Reports", icon: BarChart3, permission: "report:read" },
    { to: `/projects/${projectId}/settings`, label: "Settings", icon: Settings, permission: "project:update" },
  ];
}

function NavLink({ item }: { item: NavItem }) {
  const location = useLocation();
  const allowed = usePermission(item.permission ?? "project:read");

  // Always show items without permission (like Dashboard)
  if (item.permission && !allowed) return null;

  const active = item.exact
    ? location.pathname === item.to
    : location.pathname.startsWith(item.to);

  return (
    <Link
      to={item.to}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      <span className="flex-1">{item.label}</span>
      {active && <ChevronRight className="h-3 w-3" />}
    </Link>
  );
}

export function Sidebar() {
  const { projectId } = useParams<{ projectId?: string }>();

  return (
    <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
      {topNav.map((item) => (
        <NavLink key={item.to} item={item} />
      ))}

      {projectId && (
        <>
          <div className="pt-4 pb-1">
            <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Project
            </p>
          </div>
          {projectNav(projectId).map((item) => (
            <NavLink key={item.to} item={item} />
          ))}
        </>
      )}
    </nav>
  );
}
