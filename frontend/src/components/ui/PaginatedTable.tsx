import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/utils/cn";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
}

interface PaginatedTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  className?: string;
}

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-muted animate-pulse rounded" />
        </td>
      ))}
    </tr>
  );
}

export function PaginatedTable<T>({
  columns,
  data,
  isLoading,
  total,
  page = 1,
  pageSize = 20,
  onPageChange,
  emptyMessage = "No data found.",
  rowKey,
  onRowClick,
  className,
}: PaginatedTableProps<T>) {
  const totalPages = total !== undefined ? Math.ceil(total / pageSize) : undefined;
  const hasPrev = page > 1;
  const hasNext = totalPages !== undefined ? page < totalPages : data.length === pageSize;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left font-medium text-muted-foreground",
                    col.className
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <SkeletonRow key={i} cols={columns.length} />
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-10 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={() => onRowClick?.(row)}
                  className={cn(
                    "transition-colors",
                    onRowClick && "cursor-pointer hover:bg-accent/40"
                  )}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={cn("px-4 py-3", col.className)}>
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      {onPageChange && (hasPrev || hasNext) && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {total !== undefined
              ? `${Math.min((page - 1) * pageSize + 1, total)}–${Math.min(page * pageSize, total)} of ${total}`
              : `Page ${page}`}
          </span>
          <div className="flex gap-1">
            <button
              disabled={!hasPrev}
              onClick={() => onPageChange(page - 1)}
              className="p-1 rounded hover:bg-accent disabled:opacity-30"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              disabled={!hasNext}
              onClick={() => onPageChange(page + 1)}
              className="p-1 rounded hover:bg-accent disabled:opacity-30"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
