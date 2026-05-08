import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Building2 } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { apiGet, apiPost } from "@/services/api";
import type { Enterprise } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name required"),
  slug: z.string().min(1, "Slug required").regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers, hyphens only"),
  azure_ad_tenant_id: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

function NewEnterpriseDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const create = useMutation({
    mutationFn: (data: FormData) =>
      apiPost<Enterprise>("/api/v1/enterprises", {
        ...data,
        azure_ad_tenant_id: data.azure_ad_tenant_id || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["enterprises"] });
      onClose();
    },
  });

  return (
    <form onSubmit={handleSubmit((d) => create.mutate(d))} className="space-y-4 mt-4">
      <div>
        <label className="block text-sm font-medium mb-1">Name *</label>
        <input {...register("name")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Slug *</label>
        <input {...register("slug")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" placeholder="my-enterprise" />
        {errors.slug && <p className="text-xs text-red-600 mt-1">{errors.slug.message}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Azure AD Tenant ID</label>
        <input {...register("azure_ad_tenant_id")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" placeholder="00000000-0000-0000-0000-000000000000" />
      </div>
      {create.isError && <p className="text-xs text-red-600">Failed to create enterprise.</p>}
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
        <button type="submit" disabled={create.isPending} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
          {create.isPending ? "Creating…" : "Create Enterprise"}
        </button>
      </div>
    </form>
  );
}

export function GlobalAdminPage() {
  const [newOpen, setNewOpen] = useState(false);

  const { data: enterprises, isLoading } = useQuery({
    queryKey: ["enterprises"],
    queryFn: () => apiGet<Enterprise[]>("/api/v1/enterprises"),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Global Administration</h1>
          <p className="text-muted-foreground text-sm mt-1">Manage enterprises across the platform.</p>
        </div>
        <button
          onClick={() => setNewOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Enterprise
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse bg-muted rounded-xl" />
          ))}
        </div>
      ) : !enterprises?.length ? (
        <div className="text-center py-16 border rounded-xl">
          <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium">No enterprises yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {enterprises.map((e) => (
            <div key={e.id} className="bg-card border rounded-xl p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold">{e.name}</p>
                  <p className="text-xs text-muted-foreground font-mono mt-0.5">{e.slug}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${e.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {e.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              {e.azure_ad_tenant_id && (
                <p className="text-xs text-muted-foreground mt-2">
                  Azure: <span className="font-mono">{e.azure_ad_tenant_id.slice(0, 8)}…</span>
                </p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Created {new Date(e.created_at).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}

      <Dialog.Root open={newOpen} onOpenChange={setNewOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-background border rounded-xl shadow-lg p-6">
            <Dialog.Title className="text-lg font-semibold">New Enterprise</Dialog.Title>
            <NewEnterpriseDialog onClose={() => setNewOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
