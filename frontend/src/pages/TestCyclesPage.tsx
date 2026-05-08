import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  useTestCycles,
  useCreateTestCycle,
  useActivateCycle,
  useCloseCycle,
  useExecutions,
  useUpdateExecution,
} from "@/hooks/useTestCycles";
import type { Execution, TestCycle } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-600",
  ACTIVE: "bg-green-100 text-green-700",
  COMPLETED: "bg-blue-100 text-blue-700",
  LOCKED: "bg-purple-100 text-purple-700",
};

const EXEC_STATUS_COLORS: Record<string, string> = {
  NOT_STARTED: "bg-gray-100 text-gray-600",
  IN_PROGRESS: "bg-blue-100 text-blue-700",
  PASSED: "bg-green-100 text-green-700",
  FAILED: "bg-red-100 text-red-700",
  BLOCKED: "bg-orange-100 text-orange-700",
  SKIPPED: "bg-gray-100 text-gray-500",
};

function ExecutionRow({
  projectId,
  cycleId,
  exec,
}: {
  projectId: string;
  cycleId: string;
  exec: Execution;
}) {
  const update = useUpdateExecution(projectId, cycleId, exec.id);

  return (
    <div className="flex items-center gap-3 py-2 border-b last:border-b-0">
      <span className="text-xs text-muted-foreground font-mono flex-shrink-0 w-28 truncate">
        {exec.cosmos_script_id.slice(0, 14)}…
      </span>
      <select
        value={exec.status}
        onChange={(e) => update.mutate({ status: e.target.value })}
        disabled={update.isPending}
        className={`text-xs px-2 py-1 rounded border cursor-pointer ${EXEC_STATUS_COLORS[exec.status]}`}
      >
        {["NOT_STARTED", "IN_PROGRESS", "PASSED", "FAILED", "BLOCKED", "SKIPPED"].map((s) => (
          <option key={s} value={s}>
            {s.replace(/_/g, " ")}
          </option>
        ))}
      </select>
      {exec.notes && (
        <span className="text-xs text-muted-foreground truncate flex-1">{exec.notes}</span>
      )}
    </div>
  );
}

function CycleCard({
  cycle,
  projectId,
  isSelected,
  onSelect,
}: {
  cycle: TestCycle;
  projectId: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const activate = useActivateCycle(projectId, cycle.id);
  const close = useCloseCycle(projectId, cycle.id);
  const { data: executions } = useExecutions(projectId, cycle.id);

  const passedCount = executions?.filter((e) => e.status === "PASSED").length ?? 0;
  const totalCount = executions?.length ?? 0;

  return (
    <div
      className={`bg-card border rounded-lg p-4 cursor-pointer transition-colors ${
        isSelected ? "border-primary" : "hover:border-muted-foreground/40"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-sm">{cycle.name}</p>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[cycle.status]}`}
            >
              {cycle.status}
            </span>
            {totalCount > 0 && (
              <span className="text-xs text-muted-foreground">
                {passedCount}/{totalCount} passed
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-1" onClick={(e) => e.stopPropagation()}>
          {cycle.status === "DRAFT" && (
            <button
              onClick={() => activate.mutate()}
              disabled={activate.isPending}
              className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded hover:bg-green-200 disabled:opacity-50"
            >
              Activate
            </button>
          )}
          {cycle.status === "ACTIVE" && (
            <button
              onClick={() => close.mutate()}
              disabled={close.isPending}
              className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded hover:bg-blue-200 disabled:opacity-50"
            >
              Close
            </button>
          )}
        </div>
      </div>
      {(cycle.start_date || cycle.end_date) && (
        <p className="text-xs text-muted-foreground mt-2">
          {cycle.start_date ?? "—"} → {cycle.end_date ?? "—"}
        </p>
      )}
    </div>
  );
}

function CreateCycleForm({
  projectId,
  onClose,
}: {
  projectId: string;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [envId, setEnvId] = useState("");
  const create = useCreateTestCycle(projectId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await create.mutateAsync({ name, environment_id: envId });
    onClose();
  };

  return (
    <form onSubmit={handleSubmit} className="bg-card border rounded-lg p-4 mb-4 space-y-3">
      <h3 className="font-medium text-sm">New Test Cycle</h3>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Cycle name (e.g. Sprint 12 Regression)"
        required
        className="w-full border rounded px-3 py-2 text-sm"
      />
      <input
        value={envId}
        onChange={(e) => setEnvId(e.target.value)}
        placeholder="Environment ID"
        required
        className="w-full border rounded px-3 py-2 text-sm font-mono"
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={create.isPending}
          className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Create"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm text-muted-foreground"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export function TestCyclesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: cycles, isLoading } = useTestCycles(projectId!);
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const selectedCycle = cycles?.find((c) => c.id === selectedCycleId) ?? null;
  const { data: executions } = useExecutions(projectId!, selectedCycleId ?? "");

  return (
    <div className="flex gap-4 h-full">
      {/* Cycle list */}
      <div className="w-72 shrink-0 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Test Cycles</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="text-xs bg-primary text-primary-foreground px-3 py-1.5 rounded hover:bg-primary/90"
          >
            + New
          </button>
        </div>

        {showCreate && (
          <CreateCycleForm projectId={projectId!} onClose={() => setShowCreate(false)} />
        )}

        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : (
          <div className="space-y-2 overflow-y-auto flex-1">
            {cycles?.map((cycle) => (
              <CycleCard
                key={cycle.id}
                cycle={cycle}
                projectId={projectId!}
                isSelected={cycle.id === selectedCycleId}
                onSelect={() => setSelectedCycleId(cycle.id)}
              />
            ))}
            {cycles?.length === 0 && (
              <p className="text-muted-foreground text-sm">No test cycles yet.</p>
            )}
          </div>
        )}
      </div>

      {/* Execution list */}
      {selectedCycle && (
        <div className="flex-1 bg-card border rounded-lg p-4 flex flex-col min-w-0">
          <h3 className="font-medium mb-4">{selectedCycle.name} — Executions</h3>
          {executions && executions.length > 0 ? (
            <div className="flex-1 overflow-y-auto">
              {executions.map((exec) => (
                <ExecutionRow
                  key={exec.id}
                  projectId={projectId!}
                  cycleId={selectedCycle.id}
                  exec={exec}
                />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">
              No executions in this cycle yet.
            </p>
          )}
        </div>
      )}

      {!selectedCycle && !isLoading && (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm">Select a cycle to view executions</p>
        </div>
      )}
    </div>
  );
}
