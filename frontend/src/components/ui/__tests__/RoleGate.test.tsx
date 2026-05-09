/**
 * RoleGate component tests.
 *
 * RoleGate is the frontend analogue of the backend assert_permission() guard.
 * It controls whether UI elements are rendered based on the current user's
 * permissions.  A bug here could show admin controls to unprivileged users
 * (UI security) or hide features from users who should have them (UX bug).
 *
 * All tests mock the Zustand authStore directly to avoid needing MSAL or
 * a real authentication flow.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { RoleGate } from "../RoleGate";

// ---------------------------------------------------------------------------
// Mock usePermission hook — avoids full store setup
// ---------------------------------------------------------------------------

const mockUsePermission = vi.fn<[string], boolean>();

vi.mock("@/hooks/usePermission", () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RoleGate", () => {
  beforeEach(() => {
    mockUsePermission.mockReset();
  });

  it("renders children when user has the required permission", () => {
    /**
     * The primary success path: a user with script:approve sees the Approve
     * button.  If this fails, admin UI is always hidden.
     */
    mockUsePermission.mockReturnValue(true);

    render(
      <RoleGate permission="script:approve">
        <button>Approve Script</button>
      </RoleGate>
    );

    expect(screen.getByRole("button", { name: "Approve Script" })).toBeInTheDocument();
  });

  it("does not render children when user lacks the permission", () => {
    /**
     * The primary security path: a user without script:approve must NOT see
     * the Approve button.  If this fails, unprivileged users see admin controls.
     */
    mockUsePermission.mockReturnValue(false);

    render(
      <RoleGate permission="script:approve">
        <button>Approve Script</button>
      </RoleGate>
    );

    expect(screen.queryByRole("button", { name: "Approve Script" })).not.toBeInTheDocument();
  });

  it("renders null (not fallback) by default when permission is missing", () => {
    /**
     * Without an explicit fallback, RoleGate renders nothing — not an error
     * state, not empty space.  This matches the most common usage where the
     * element simply shouldn't exist in the DOM.
     */
    mockUsePermission.mockReturnValue(false);
    const { container } = render(
      <RoleGate permission="admin:company">
        <div data-testid="secret-panel">Admin Panel</div>
      </RoleGate>
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("secret-panel")).not.toBeInTheDocument();
  });

  it("renders fallback when provided and user lacks permission", () => {
    /**
     * When a fallback is provided (e.g. a disabled button), it should be
     * shown instead of children when permission is denied.
     */
    mockUsePermission.mockReturnValue(false);

    render(
      <RoleGate
        permission="script:delete"
        fallback={<span data-testid="disabled-notice">Not authorised</span>}
      >
        <button>Delete</button>
      </RoleGate>
    );

    expect(screen.getByTestId("disabled-notice")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("does not render fallback when user has permission", () => {
    /**
     * Fallback must not appear when the user IS authorised — it should only
     * show as an alternative to the protected content, not alongside it.
     */
    mockUsePermission.mockReturnValue(true);

    render(
      <RoleGate
        permission="script:approve"
        fallback={<span data-testid="disabled-notice">Not authorised</span>}
      >
        <button>Approve</button>
      </RoleGate>
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.queryByTestId("disabled-notice")).not.toBeInTheDocument();
  });

  it("passes the exact permission string to usePermission", () => {
    /**
     * RoleGate must forward the permission prop verbatim to usePermission.
     * Any transformation (toLowerCase, mapping) would cause mismatches with
     * the backend permission enum values.
     */
    mockUsePermission.mockReturnValue(false);
    const permission = "crawler:cancel";

    render(
      <RoleGate permission={permission}>
        <span>Cancel</span>
      </RoleGate>
    );

    expect(mockUsePermission).toHaveBeenCalledWith(permission);
  });

  it("renders multiple children when permission is granted", () => {
    /**
     * RoleGate must handle React fragments / multiple child elements,
     * not just single children.
     */
    mockUsePermission.mockReturnValue(true);

    render(
      <RoleGate permission="cycle:create">
        <button>Create Cycle</button>
        <button>Assign Testers</button>
      </RoleGate>
    );

    expect(screen.getByRole("button", { name: "Create Cycle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Testers" })).toBeInTheDocument();
  });

  it("re-renders correctly when permission changes from false to true", () => {
    /**
     * When the auth store updates (e.g. user switches tenant and gains a new
     * role), RoleGate must re-render to reflect the new permission state.
     */
    mockUsePermission.mockReturnValue(false);

    const { rerender } = render(
      <RoleGate permission="report:export">
        <button>Export Report</button>
      </RoleGate>
    );

    expect(screen.queryByRole("button", { name: "Export Report" })).not.toBeInTheDocument();

    // Simulate gaining the permission (e.g. tenant switch)
    mockUsePermission.mockReturnValue(true);
    rerender(
      <RoleGate permission="report:export">
        <button>Export Report</button>
      </RoleGate>
    );

    expect(screen.getByRole("button", { name: "Export Report" })).toBeInTheDocument();
  });
});
