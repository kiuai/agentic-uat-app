import { Navigate, useLocation } from "react-router-dom";
import { useIsAuthenticated } from "@azure/msal-react";
import { useAuthStore } from "@/store/authStore";

interface ProtectedRouteProps {
  children: React.ReactNode;
  /** If provided, user must have this permission or be redirected to /unauthorized */
  permission?: string;
}

export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const isAuthenticated = useIsAuthenticated();
  const location = useLocation();
  const hasPermission = useAuthStore((s) => s.hasPermission);

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (permission && !hasPermission(permission)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
