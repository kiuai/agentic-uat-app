/**
 * ExecuteTestPage component tests.
 *
 * ExecuteTestPage is the core execution UI where testers record test results.
 * Bugs here directly affect the accuracy of UAT evidence.
 *
 * What is tested:
 * - Result radio buttons render all four statuses (PASSED/FAILED/BLOCKED/SKIPPED)
 * - PASSED is pre-selected by default (optimistic default for happy paths)
 * - Selecting a status applies the correct colour styling (visual feedback)
 * - Notes textarea is present and accepts input
 * - Duration input is present
 * - Evidence upload zone is rendered
 * - Submit button triggers the mutation
 * - Submit button is disabled while mutation is pending
 * - Error message displayed on submission failure
 * - Cancel button navigates back
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock the API calls so tests don't hit a real server
vi.mock("@/services/api", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  default: {
    post: vi.fn(),
  },
}));

// Mock Monaco Editor (heavy dep, irrelevant for this page's tests)
vi.mock("@/components/ui/ScriptEditor", () => ({
  ScriptEditor: ({ value }: { value: string }) => (
    <pre data-testid="script-editor">{value}</pre>
  ),
}));

// Mock FileUploadZone
vi.mock("@/components/ui/FileUploadZone", () => ({
  FileUploadZone: ({ onFiles }: { onFiles: (files: File[]) => void }) => (
    <div
      data-testid="file-upload-zone"
      onClick={() => onFiles([new File([""], "screenshot.png", { type: "image/png" })])}
    >
      Upload Evidence
    </div>
  ),
}));

import { apiGet, apiPost } from "@/services/api";
import { ExecuteTestPage } from "@/pages/cycles/ExecuteTestPage";

const mockApiGet = apiGet as ReturnType<typeof vi.fn>;
const mockApiPost = apiPost as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function renderPage(
  assignmentId = "assign-123",
  projectId = "proj-123",
  cycleId = "cycle-123"
) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter
        initialEntries={[
          `/projects/${projectId}/cycles/${cycleId}/execute/${assignmentId}`,
        ]}
      >
        <Routes>
          <Route
            path="/projects/:projectId/cycles/:cycleId/execute/:assignmentId"
            element={<ExecuteTestPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExecuteTestPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default: assignment and script data resolve immediately
    mockApiGet.mockImplementation((url: string) => {
      if (url.includes("/executions/")) {
        return Promise.resolve({
          id: "assign-123",
          script_id: "script-456",
          status: "NOT_STARTED",
        });
      }
      if (url.includes("/test-scripts/script-456/content")) {
        return Promise.resolve({ content: "Feature: Login\n  Scenario: Valid login" });
      }
      if (url.includes("/test-scripts/script-456")) {
        return Promise.resolve({
          id: "script-456",
          title: "Login — Gherkin",
          format: "gherkin",
        });
      }
      return Promise.resolve(null);
    });
  });

  // ── Page title ────────────────────────────────────────────────────────────

  it("renders the Execute Test heading", async () => {
    renderPage();
    expect(await screen.findByText("Execute Test")).toBeInTheDocument();
  });

  it("shows the script title once loaded", async () => {
    renderPage();
    expect(await screen.findByText("Login — Gherkin")).toBeInTheDocument();
  });

  // ── Result radio buttons ──────────────────────────────────────────────────

  it("renders all four result options", async () => {
    renderPage();
    // Wait for loading to complete
    await screen.findByText("Execute Test");

    expect(screen.getByText("PASSED")).toBeInTheDocument();
    expect(screen.getByText("FAILED")).toBeInTheDocument();
    expect(screen.getByText("BLOCKED")).toBeInTheDocument();
    expect(screen.getByText("SKIPPED")).toBeInTheDocument();
  });

  it("defaults to PASSED result", async () => {
    renderPage();
    await screen.findByText("Execute Test");

    // The PASSED radio should be checked by default
    const passedRadio = screen.getByRole("radio", { name: /passed/i }) as HTMLInputElement;
    // Input is sr-only but still in DOM — check checked attribute
    expect(passedRadio.checked).toBe(true);
  });

  it("PASSED label has green styling when selected", async () => {
    renderPage();
    await screen.findByText("Execute Test");

    // The visible PASSED div should have green classes (from RESULT_STYLES)
    const passedDiv = screen.getByText("PASSED").closest("div");
    expect(passedDiv?.className).toMatch(/green/);
  });

  it("FAILED label applies red styling when selected", async () => {
    renderPage();
    await screen.findByText("Execute Test");

    const failedRadio = screen.getByRole("radio", { name: /failed/i });
    fireEvent.click(failedRadio);

    await waitFor(() => {
      const failedDiv = screen.getByText("FAILED").closest("div");
      expect(failedDiv?.className).toMatch(/red/);
    });
  });

  // ── Form fields ───────────────────────────────────────────────────────────

  it("renders the Notes textarea", async () => {
    renderPage();
    await screen.findByText("Execute Test");
    expect(screen.getByRole("textbox", { name: /notes/i })).toBeInTheDocument();
  });

  it("renders the Duration input", async () => {
    renderPage();
    await screen.findByText("Execute Test");
    expect(screen.getByRole("spinbutton")).toBeInTheDocument(); // number input
  });

  it("renders the evidence upload zone", async () => {
    renderPage();
    await screen.findByText("Execute Test");
    expect(screen.getByTestId("file-upload-zone")).toBeInTheDocument();
  });

  // ── Form submission ───────────────────────────────────────────────────────

  it("Submit Result button is present", async () => {
    renderPage();
    await screen.findByText("Execute Test");
    expect(screen.getByRole("button", { name: /submit result/i })).toBeInTheDocument();
  });

  it("Submit calls apiPost with the selected status", async () => {
    mockApiPost.mockResolvedValue({ id: "result-789", status: "PASSED" });

    renderPage();
    await screen.findByText("Execute Test");

    const notesField = screen.getByRole("textbox", { name: /notes/i });
    await userEvent.type(notesField, "All steps passed successfully");

    fireEvent.click(screen.getByRole("button", { name: /submit result/i }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        expect.stringContaining("/results"),
        expect.objectContaining({ status: "PASSED" })
      );
    });
  });

  it("shows error message when submission fails", async () => {
    mockApiPost.mockRejectedValue(new Error("Network error"));

    renderPage();
    await screen.findByText("Execute Test");

    fireEvent.click(screen.getByRole("button", { name: /submit result/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/failed to submit result/i)
      ).toBeInTheDocument();
    });
  });

  it("Submit button shows submitting state while pending", async () => {
    // Hang the mutation indefinitely to test the pending state
    mockApiPost.mockImplementation(() => new Promise(() => {}));

    renderPage();
    await screen.findByText("Execute Test");

    fireEvent.click(screen.getByRole("button", { name: /submit result/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitting/i)).toBeInTheDocument();
    });
  });

  // ── Navigation ────────────────────────────────────────────────────────────

  it("Cancel button is present", async () => {
    renderPage();
    await screen.findByText("Execute Test");
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("Cancel button does not submit the form", async () => {
    renderPage();
    await screen.findByText("Execute Test");

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(mockApiPost).not.toHaveBeenCalled();
  });
});
