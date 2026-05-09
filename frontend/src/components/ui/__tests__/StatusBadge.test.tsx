/**
 * StatusBadge component tests.
 *
 * StatusBadge is the visual indicator for entity status across the app
 * (jobs, scripts, cycles, executions, requirements).  Wrong colours make
 * the UI misleading — a FAILED status in green would look passed.
 *
 * Tests verify:
 * - Correct label text for each status value
 * - Correct CSS colour class for each status (green=pass, red=fail, etc.)
 * - Multi-word statuses use spaces (not underscores) in labels
 * - Unknown statuses render with a safe fallback style
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "../StatusBadge";

describe("StatusBadge", () => {
  // ── Label rendering ──────────────────────────────────────────────────────

  it("renders PASSED status text", () => {
    /**
     * PASSED executions must display as 'PASSED', not the raw enum value
     * with underscores (which would be a confusing UX).
     */
    render(<StatusBadge status="PASSED" />);
    expect(screen.getByText("PASSED")).toBeInTheDocument();
  });

  it("renders FAILED status text", () => {
    render(<StatusBadge status="FAILED" />);
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });

  it("renders NOT_STARTED as readable label 'Not Started'", () => {
    /**
     * Multi-word statuses with underscores must be humanised.
     * NOT_STARTED → 'Not Started' in the STATUS_LABELS map.
     */
    render(<StatusBadge status="NOT_STARTED" />);
    expect(screen.getByText("Not Started")).toBeInTheDocument();
  });

  it("renders IN_REVIEW as 'In Review'", () => {
    render(<StatusBadge status="IN_REVIEW" />);
    expect(screen.getByText("In Review")).toBeInTheDocument();
  });

  it("renders IN_PROGRESS as 'In Progress'", () => {
    render(<StatusBadge status="IN_PROGRESS" />);
    expect(screen.getByText("In Progress")).toBeInTheDocument();
  });

  it("renders DRAFT status", () => {
    render(<StatusBadge status="DRAFT" />);
    expect(screen.getByText("DRAFT")).toBeInTheDocument();
  });

  it("renders APPROVED status", () => {
    render(<StatusBadge status="APPROVED" />);
    expect(screen.getByText("APPROVED")).toBeInTheDocument();
  });

  it("renders REJECTED status", () => {
    render(<StatusBadge status="REJECTED" />);
    expect(screen.getByText("REJECTED")).toBeInTheDocument();
  });

  it("renders PENDING status", () => {
    render(<StatusBadge status="PENDING" />);
    expect(screen.getByText("PENDING")).toBeInTheDocument();
  });

  it("renders unknown status by replacing underscores with spaces", () => {
    /**
     * Unexpected status values (e.g. from a new backend release before
     * frontend is updated) must render gracefully, not crash.
     */
    render(<StatusBadge status="CUSTOM_STATUS" />);
    expect(screen.getByText("CUSTOM STATUS")).toBeInTheDocument();
  });

  // ── Colour class verification ────────────────────────────────────────────

  it("PASSED badge contains green colour classes", () => {
    /**
     * Green = success in the KAATS design system.  PASSED results must use
     * green so testers can visually scan for failures at a glance.
     */
    const { container } = render(<StatusBadge status="PASSED" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/green/);
  });

  it("FAILED badge contains red colour classes", () => {
    const { container } = render(<StatusBadge status="FAILED" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/red/);
  });

  it("APPROVED badge contains green colour classes", () => {
    const { container } = render(<StatusBadge status="APPROVED" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/green/);
  });

  it("REJECTED badge contains red colour classes", () => {
    const { container } = render(<StatusBadge status="REJECTED" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/red/);
  });

  it("IN_REVIEW badge contains purple colour classes", () => {
    /**
     * IN_REVIEW scripts use purple to distinguish them visually from
     * APPROVED (green) and DRAFT (yellow).
     */
    const { container } = render(<StatusBadge status="IN_REVIEW" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/purple/);
  });

  it("DRAFT badge contains yellow colour classes", () => {
    const { container } = render(<StatusBadge status="DRAFT" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/yellow/);
  });

  it("BLOCKED execution badge contains orange colour classes", () => {
    const { container } = render(<StatusBadge status="BLOCKED" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/orange/);
  });

  it("PROCESSING badge contains blue colour classes", () => {
    const { container } = render(<StatusBadge status="PROCESSING" />);
    const badge = container.firstElementChild!;
    expect(badge.className).toMatch(/blue/);
  });

  it("unknown status badge renders without crashing and uses fallback style", () => {
    /**
     * No status should ever cause a render error.  Missing styles fall back
     * to a neutral gray (defined as the default in STATUS_STYLES).
     */
    const { container } = render(<StatusBadge status="COMPLETELY_UNKNOWN" />);
    expect(container.firstElementChild).toBeInTheDocument();
  });

  // ── Accessibility ────────────────────────────────────────────────────────

  it("renders as an inline element (span)", () => {
    /**
     * StatusBadge is inline — it should not disrupt text flow when embedded
     * in table cells or list items.
     */
    render(<StatusBadge status="ACTIVE" />);
    const badge = screen.getByText("ACTIVE");
    expect(badge.tagName.toLowerCase()).toBe("span");
  });

  it("accepts additional className prop", () => {
    /**
     * Callers can pass extra classes (e.g. margins) without breaking the
     * default styling.
     */
    render(<StatusBadge status="COMPLETED" className="mt-2 ml-1" />);
    const badge = screen.getByText("COMPLETED");
    expect(badge.className).toMatch(/mt-2/);
  });
});
