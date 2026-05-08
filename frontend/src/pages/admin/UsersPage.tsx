import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Search, Users, UserX } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import type { User, UserRole } from "@/types";

const inviteSchema = z.object({
  email: z.string().email("Enter a valid email"),
  display_name: z.string().min(1, "Name is required"),
  role: z.enum(["GADM", "EADM", "CADM", "SM", "VL", "QA", "VT", "BPO"] as const),
});

type InviteForm = z.infer<typeof inviteSchema>;

const ROLE_LABELS: Record<UserRole, string> = {
  GADM: "Global Admin",
  EADM: "Enterprise Admin",
  CADM: "Company Admin",
  SM: "System Manager",
  VL: "Validation Lead",
  QA: "QA Engineer",
  VT: "Validation Tester",
  BPO: "Business Process Owner",
};

function InviteDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { register, handleSubmit, formState: { errors } } = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "VT" },
  });

  const invite = useMutation({
    mutationFn: (data: InviteForm) => apiPost("/api/v1/users/invite", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => invite.mutate(d))} className="space-y-4 mt-4">
      <div>
        <label className="block text-sm font-medium mb-1">Email *</label>
        <input {...register("email")} type="email" className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        {errors.email && <p className="text-xs text-red-600 mt-1">{errors.email.message}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Display Name *</label>
        <input {...register("display_name")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        {errors.display_name && <p className="text-xs text-red-600 mt-1">{errors.display_name.message}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Initial Role *</label>
        <select {...register("role")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
          {(Object.entries(ROLE_LABELS) as [UserRole, string][]).map(([code, label]) => (
            <option key={code} value={code}>{label} ({code})</option>
          ))}
        </select>
      </div>
      {invite.isError && <p className="text-xs text-red-600">Failed to invite user.</p>}
      {invite.isSuccess && <p className="text-xs text-green-600">Invitation sent!</p>}
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
        <button type="submit" disabled={invite.isPending} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
          {invite.isPending ? "Sending…" : "Send Invitation"}
        </button>
      </div>
    </form>
  );
}

export function UsersPage() {
  const [search, setSearch] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [deactivateId, setDeactivateId] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => apiGet<User[]>("/api/v1/users"),
    staleTime: 60_000,
  });

  const deactivate = useMutation({
    mutationFn: (id: string) => apiPost(`/api/v1/users/${id}/deactivate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setDeactivateId(null);
    },
  });

  const filtered = users?.filter(
    (u) =>
      u.display_name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Users</h1>
        <RoleGate permission="user:create">
          <button
            onClick={() => setInviteOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Invite User
          </button>
        </RoleGate>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search users…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-sm border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse bg-muted rounded-xl" />
          ))}
        </div>
      ) : !filtered?.length ? (
        <div className="text-center py-16 border rounded-xl">
          <Users className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium">
            {search ? "No users match your search" : "No users found"}
          </p>
        </div>
      ) : (
        <div className="border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">User</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Roles</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Last Login</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtered.map((user) => (
                <tr key={user.id} className="hover:bg-accent/30 transition-colors">
                  <td className="px-4 py-3">
                    <p className="font-medium">{user.display_name}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {user.roles.slice(0, 3).map((ra) => (
                        <span key={ra.id} className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {ROLE_LABELS[ra.role] ?? ra.role}
                        </span>
                      ))}
                      {user.roles.length > 3 && (
                        <span className="text-xs text-muted-foreground">+{user.roles.length - 3}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        user.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {user.last_login_at
                      ? new Date(user.last_login_at).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <RoleGate permission="user:update">
                      {user.is_active && (
                        <button
                          onClick={() => setDeactivateId(user.id)}
                          className="text-muted-foreground hover:text-red-600 transition-colors p-1"
                          title="Deactivate"
                        >
                          <UserX className="h-4 w-4" />
                        </button>
                      )}
                    </RoleGate>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite dialog */}
      <Dialog.Root open={inviteOpen} onOpenChange={setInviteOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-background border rounded-xl shadow-lg p-6">
            <Dialog.Title className="text-lg font-semibold">Invite User</Dialog.Title>
            <InviteDialog onClose={() => setInviteOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={!!deactivateId}
        onOpenChange={(open) => !open && setDeactivateId(null)}
        title="Deactivate User"
        description="This user will lose access to the platform. You can reactivate them later."
        confirmLabel="Deactivate"
        destructive
        onConfirm={() => deactivateId && deactivate.mutate(deactivateId)}
      />
    </div>
  );
}
