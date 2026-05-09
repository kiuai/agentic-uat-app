/**
 * PaginatedTable component tests.
 *
 * PaginatedTable is used throughout KAATS to display scripts, requirements,
 * cycles, and assignments.  Pagination bugs can silently hide records from
 * users (missed test scripts, incomplete audit views).
 *
 * Tests verify:
 * - Correct row count rendered for given data
 * - Column headers rendered
 * - Empty state message displayed
 * - Loading skeleton displayed during isLoading
 * - Pagination: previous/next buttons disabled/enabled correctly
 * - onPageChange fires with correct page number
 * - onRowClick fires with the correct row object
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PaginatedTable, type Column } from "../PaginatedTable";

// ---------------------------------------------------------------------------
// Test data and column config
// ---------------------------------------------------------------------------

interface Script {
  id: string;
  title: string;
  status: string;
}

const SCRIPTS: Script[] = [
  { id: "s1", title: "Login Test", status: "APPROVED" },
  { id: "s2", title: "Logout Test", status: "DRAFT" },
  { id: "s3", title: "Search Test", status: "IN_REVIEW" },
];

const COLUMNS: Column<Script>[] = [
  { key: "title", header: "Title", cell: (row) => row.title },
  { key: "status", header: "Status", cell: (row) => row.status },
];

// ---------------------------------------------------------------------------
// Rendering tests
// ---------------------------------------------------------------------------

describe("PaginatedTable — rendering", () => {
  it("renders all rows for the given data array", () => {
    /**
     * All data items must appear as rows.  Missing rows mean scripts would
     * disappear from the test library list — a critical usability bug.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
      />
    );

    expect(screen.getByText("Login Test")).toBeInTheDocument();
    expect(screen.getByText("Logout Test")).toBeInTheDocument();
    expect(screen.getByText("Search Test")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    /**
     * Column headers must be rendered so users can identify what each
     * column contains.  Missing headers make the table unusable.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
      />
    );

    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders empty message when data is empty", () => {
    /**
     * Empty data must show a user-friendly message, not a blank table.
     * This helps users understand there are no results vs. a loading error.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={[]}
        rowKey={(r) => r.id}
        emptyMessage="No test scripts found."
      />
    );

    expect(screen.getByText("No test scripts found.")).toBeInTheDocument();
  });

  it("uses default empty message when none is provided", () => {
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={[]}
        rowKey={(r) => r.id}
      />
    );

    // Default message from the component
    expect(screen.getByText(/no data found/i)).toBeInTheDocument();
  });

  it("renders skeleton rows while loading", () => {
    /**
     * During data fetch, a loading skeleton prevents layout shift and
     * communicates progress.  If skeletons are missing, the table looks
     * broken while loading.
     */
    const { container } = render(
      <PaginatedTable
        columns={COLUMNS}
        data={[]}
        isLoading
        rowKey={(r) => r.id}
      />
    );

    // Skeleton rows contain animate-pulse divs
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("does not render data rows while loading", () => {
    /**
     * While loading, the previous data (if any) should be replaced by
     * skeletons, not shown stale.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        isLoading
        rowKey={(r) => r.id}
      />
    );

    // Data rows should not be visible during loading
    expect(screen.queryByText("Login Test")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Pagination controls
// ---------------------------------------------------------------------------

describe("PaginatedTable — pagination", () => {
  it("disables Previous button on first page", () => {
    /**
     * On page 1 there is no previous page; the button must be disabled to
     * prevent nonsensical navigation.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={1}
        pageSize={5}
        total={15}
        onPageChange={vi.fn()}
      />
    );

    const prevButton = screen.getByRole("button", { name: /previous/i });
    expect(prevButton).toBeDisabled();
  });

  it("disables Next button on last page", () => {
    /**
     * On the last page, Next must be disabled.  Without this, users could
     * navigate to a page with no data.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={3}
        pageSize={5}
        total={15}
        onPageChange={vi.fn()}
      />
    );

    const nextButton = screen.getByRole("button", { name: /next/i });
    expect(nextButton).toBeDisabled();
  });

  it("enables Previous button on page > 1", () => {
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={2}
        pageSize={5}
        total={15}
        onPageChange={vi.fn()}
      />
    );

    const prevButton = screen.getByRole("button", { name: /previous/i });
    expect(prevButton).not.toBeDisabled();
  });

  it("enables Next button when not on last page", () => {
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={1}
        pageSize={5}
        total={15}
        onPageChange={vi.fn()}
      />
    );

    const nextButton = screen.getByRole("button", { name: /next/i });
    expect(nextButton).not.toBeDisabled();
  });

  it("calls onPageChange with page + 1 when Next is clicked", () => {
    /**
     * Clicking Next must advance to the next page.  An off-by-one error here
     * would skip pages and make scripts invisible.
     */
    const onPageChange = vi.fn();
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={2}
        pageSize={5}
        total={15}
        onPageChange={onPageChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it("calls onPageChange with page - 1 when Previous is clicked", () => {
    const onPageChange = vi.fn();
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        page={3}
        pageSize={5}
        total={20}
        onPageChange={onPageChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /previous/i }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});

// ---------------------------------------------------------------------------
// Row interaction
// ---------------------------------------------------------------------------

describe("PaginatedTable — row interaction", () => {
  it("calls onRowClick with the row data when a row is clicked", () => {
    /**
     * Row click navigation takes users to the script/requirement detail page.
     * If the wrong row data is passed, users end up on the wrong detail page.
     */
    const onRowClick = vi.fn();
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        onRowClick={onRowClick}
      />
    );

    fireEvent.click(screen.getByText("Login Test").closest("tr")!);
    expect(onRowClick).toHaveBeenCalledWith(SCRIPTS[0]);
  });

  it("does not crash when onRowClick is not provided", () => {
    /**
     * onRowClick is optional; clicking a row without a handler must not
     * throw an error.
     */
    render(
      <PaginatedTable
        columns={COLUMNS}
        data={SCRIPTS}
        rowKey={(r) => r.id}
        // no onRowClick
      />
    );

    expect(() => {
      fireEvent.click(screen.getByText("Logout Test").closest("tr")!);
    }).not.toThrow();
  });
});
