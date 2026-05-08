import { cn } from "@/utils/cn";
import type {
  JobStatus,
  ScriptStatus,
  CycleStatus,
  ExecutionStatus,
  RequirementStatus,
} from "@/types";

type BadgeStatus =
  | JobStatus
  | ScriptStatus
  | CycleStatus
  | ExecutionStatus
  | RequirementStatus
  | string;

const STATUS_STYLES: Record<string, string> = {
  // Jobs
  PENDING: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  PROCESSING: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  COMPLETED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  FAILED: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  CANCELLED: "bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500",

  // Scripts
  DRAFT: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  IN_REVIEW: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  APPROVED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  REJECTED: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  LOCKED: "bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300",

  // Cycles
  ACTIVE: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",

  // Executions
  NOT_STARTED: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  IN_PROGRESS: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  PASSED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  BLOCKED: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  SKIPPED: "bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500",

  // Requirements
  PROCESSED: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",

  // Project status
  ARCHIVED: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

const STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: "Not Started",
  IN_PROGRESS: "In Progress",
  IN_REVIEW: "In Review",
};

interface StatusBadgeProps {
  status: BadgeStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const styles = STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600";
  const label = STATUS_LABELS[status] ?? status.replace(/_/g, " ");

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap",
        styles,
        className
      )}
    >
      {label}
    </span>
  );
}
