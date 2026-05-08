import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/services/api";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuthStore } from "@/store/authStore";
import type { BusinessDomain } from "@/types";

const domainSchema = z.object({
  name: z.string().min(1, "Name required"),
  code: z.string().min(1, "Code required").toUpperCase(),
  description: z.string().optional(),
});

type DomainForm = z.infer<typeof domainSchema>;

function DomainRow({
  domain,
  onDelete,
}: {
  domain: BusinessDomain;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 p-3 border rounded-lg">
      <span className="font-mono text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
        {domain.code}
      </span>
      <div className="flex-1">
        <p className="text-sm font-medium">{domain.name}</p>
        {domain.description && (
          <p className="text-xs text-muted-foreground">{domain.description}</p>
        )}
      </div>
      <button
        onClick={() => onDelete(domain.id)}
        className="text-muted-foreground hover:text-red-600 transition-colors p-1"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

export function CompanySettingsPage() {
  const tenantId = useAuthStore((s) => s.tenantId);
  const qc = useQueryClient();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const { data: domains, isLoading } = useQuery({
    queryKey: ["business-domains", tenantId],
    queryFn: () => apiGet<BusinessDomain[]>("/api/v1/admin/domains"),
    enabled: !!tenantId,
  });

  const { register, handleSubmit, reset, formState: { errors } } = useForm<DomainForm>({
    resolver: zodResolver(domainSchema),
  });

  const create = useMutation({
    mutationFn: (data: DomainForm) =>
      apiPost<BusinessDomain>("/api/v1/admin/domains", {
        ...data,
        description: data.description || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["business-domains"] });
      reset();
      setShowForm(false);
    },
  });

  const del = useMutation({
    mutationFn: (id: string) => apiDelete(`/api/v1/admin/domains/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["business-domains"] });
      setDeleteId(null);
    },
  });

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Company Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Manage your company's configuration and business domains.
        </p>
      </div>

      {/* Business Domains */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Business Domains</h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            Add Domain
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleSubmit((d) => create.mutate(d))}
            className="bg-muted/50 border rounded-xl p-4 mb-4 space-y-3"
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1">Name *</label>
                <input {...register("name")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
                {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Code *</label>
                <input {...register("code")} className="w-full px-3 py-2 border rounded-lg text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary/30" placeholder="FIN" />
                {errors.code && <p className="text-xs text-red-600 mt-1">{errors.code.message}</p>}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Description</label>
              <input {...register("description")} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1.5 border rounded-lg text-xs hover:bg-accent">Cancel</button>
              <button type="submit" disabled={create.isPending} className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium disabled:opacity-50">
                {create.isPending ? "Adding…" : "Add"}
              </button>
            </div>
          </form>
        )}

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse bg-muted rounded-lg" />
            ))}
          </div>
        ) : !domains?.length ? (
          <p className="text-sm text-muted-foreground">No business domains configured.</p>
        ) : (
          <div className="space-y-2">
            {domains.map((d) => (
              <DomainRow key={d.id} domain={d} onDelete={setDeleteId} />
            ))}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
        title="Delete Business Domain"
        description="This domain will be removed. Any requirements assigned to it will lose their domain association."
        confirmLabel="Delete"
        destructive
        onConfirm={() => deleteId && del.mutate(deleteId)}
      />
    </div>
  );
}
