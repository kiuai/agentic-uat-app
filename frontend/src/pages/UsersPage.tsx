import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/services/api";
import type { User } from "@/types";

const ROLE_LABELS: Record<string, string> = {
  GADM: "Global Admin",
  EADM: "Enterprise Admin",
  CADM: "Company Admin",
  SM: "System Manager",
  VL: "Validation Lead",
  QA: "Quality Assurance",
  VT: "Validation Tester",
  BPO: "Business Process Owner",
};

export function UsersPage() {
  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<User[]>("/api/v1/users"),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Users</h1>
      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="bg-card border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Name</th>
                <th className="text-left px-4 py-3 font-medium">Email</th>
                <th className="text-left px-4 py-3 font-medium">Role</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users?.map((user) => (
                <tr key={user.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3">{user.display_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                  <td className="px-4 py-3">{ROLE_LABELS[user.role] ?? user.role}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      user.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                    }`}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
