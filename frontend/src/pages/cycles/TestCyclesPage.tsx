import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useState } from "react";
import { Plus, PlayCircle } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { apiGet, apiPost } from "@/services/api";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { RoleGate } from "@/components/ui/RoleGate";
import * as Dialog from "@radix-ui/react-dialog";
import type { TestCycle, Environment } from "@/types";

const schema = z.object({
  name: z.string().min(1, "Name required"),
  description: z.string().optional(),
  environment_id: z.string().uuid("Select an environment"),
  planned_start_date: z.string().optional(),
  planned_end_date: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

const PIE_COLORS = {
  PASSED: "#22c55e",
  FAILED: "#ef4444",
  BLOCKED: "#f97316",
  IN_PROGRESS: "#3b82f6",
  NOT_STARTED: "#d1d5db",
  SKIPPED: "#9ca3af",
};

function CycleCard({ cycle, projectId }: { cycle: TestCycle; projectId: string }) {
  return (
    <Link
      to={`/projects/${projectId}/cycles/${cycle.id}`}
      className="bg-card border rounded-xl p-5 hover:border-primary transition-colors block"
    >
      <div className="flex items-start justify-between mb-2">
        <p className="font-semibold">{cycle.name}</p>
        <StatusBadge status={cycle.status} />
      </div>
      {cycle.description && (
        <p className="text-sm text-muted-foreground line-clamp-2">{cycle.description}</p>
      )}
      <div className="flex gap-3 mt-3 text-xs text-muted-foreground">
        {cycle.planned_start_date && (
          <span>Start: {new Date(cycle.planned_start_date).toLocaleDateString()}</span>
        )}
        {cycle.planned_end_date && (
          <span>End: {new Date(cycle.planned_end_date).toLocaleDateString()}</span>
        )}
      </div>
    </Link>
  );
}

function NewCycleDialog({
  projectId,
  onClose,
}: {
  projectId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const { data: environments } = useQuery({
    queryKey: ["environments", projectId],
    queryFn: () => apiGet<Environment[]>(`/api/v1/projects/${projectId}/environments`),
    enabled: !!projectId,
  });

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const create = useMutation({
    mutationFn: (data: FormData) =>
      apiPost<TestCycle>(`/api/v1/projects/${projectId}/cycles`, {
        ...data,
        description: data.description || null,
        planned_start_date: data.planned_start_date || null,
        planned_end_date: data.planned_end_date || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cycles", projectId] });
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
        <label className="block text-sm font-medium mb-1">Description</label>
        <textarea {...register("description")} rows={2} className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none" />
      </div>
      <div>
        <label className="block text-sm font-medium mb-1">Environment *</label>
        <select {...register("environment_id")} className="w-full px-3 py-2 border rounded-lg text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30">
          <option value="">Select environment</option>
          {environments?.map((e) => (
            <option key={e.id} value={e.id}>{e.name} ({e.type})</option>
          ))}
        </select>
        {errors.environment_id && <p className="text-xs text-red-600 mt-1">{errors.environment_id.message}</p>}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Planned Start</label>
          <input {...register("planned_start_date")} type="date" className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Planned End</label>
          <input {...register("planned_end_date")} type="date" className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
      </div>
      {create.isError && <p className="text-xs text-red-600">Failed to create cycle.</p>}
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-sm hover:bg-accent">Cancel</button>
        <button type="submit" disabled={create.isPending} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
          {create.isPending ? "Creating…" : "Create Cycle"}
        </button>
      </div>
    </form>
  );
}

export function TestCyclesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [newOpen, setNewOpen] = useState(false);

  const { data: cycles, isLoading } = useQuery({
    queryKey: ["cycles", projectId],
    queryFn: () => apiGet<TestCycle[]>(`/api/v1/projects/${projectId}/cycles`),
    enabled: !!projectId,
    staleTime: 30_000,
  });

  const active = cycles?.filter((c) => c.status === "ACTIVE") ?? [];
  const others = cycles?.filter((c) => c.status !== "ACTIVE") ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Test Cycles</h1>
        <RoleGate permission="cycle:create">
          <button
            onClick={() => setNewOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Cycle
          </button>
        </RoleGate>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse bg-muted rounded-xl" />
          ))}
        </div>
      ) : !cycles?.length ? (
        <div className="text-center py-16 border rounded-xl">
          <PlayCircle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium">No test cycles yet</p>
          <RoleGate permission="cycle:create">
            <button
              onClick={() => setNewOpen(true)}
              className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90"
            >
              Create first cycle
            </button>
          </RoleGate>
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Active</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {active.map((c) => <CycleCard key={c.id} cycle={c} projectId={projectId!} />)}
              </div>
            </section>
          )}
          {others.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                {active.length > 0 ? "Others" : "All Cycles"}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {others.map((c) => <CycleCard key={c.id} cycle={c} projectId={projectId!} />)}
              </div>
            </section>
          )}
        </>
      )}

      <Dialog.Root open={newOpen} onOpenChange={setNewOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-background border rounded-xl shadow-lg p-6">
            <Dialog.Title className="text-lg font-semibold">New Test Cycle</Dialog.Title>
            <NewCycleDialog projectId={projectId!} onClose={() => setNewOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
