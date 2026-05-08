import { Link } from "react-router-dom";
import { ShieldOff } from "lucide-react";

export function UnauthorizedPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8">
      <ShieldOff className="h-16 w-16 text-muted-foreground mb-4" />
      <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
      <p className="text-muted-foreground mb-6 max-w-sm">
        You don't have permission to view this page. Contact your administrator to request access.
      </p>
      <Link
        to="/dashboard"
        className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors text-sm font-medium"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
