import { usePermission } from "@/hooks/usePermission";

interface RoleGateProps {
  permission: string;
  children: React.ReactNode;
  /** Rendered when permission is missing. Defaults to null. */
  fallback?: React.ReactNode;
}

/**
 * Renders `children` only if the current user has `permission`.
 * Use `fallback` to show something else (e.g. a disabled button).
 */
export function RoleGate({ permission, children, fallback = null }: RoleGateProps) {
  const allowed = usePermission(permission);
  return <>{allowed ? children : fallback}</>;
}
