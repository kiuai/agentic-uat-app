import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthenticatedTemplate, UnauthenticatedTemplate } from "@azure/msal-react";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/auth/ProtectedRoute";

// Auth pages
import { LoginPage } from "@/pages/auth/LoginPage";
import { UnauthorizedPage } from "@/pages/auth/UnauthorizedPage";

// Dashboard
import { DashboardPage } from "@/pages/dashboard/DashboardPage";

// Projects
import { ProjectsListPage } from "@/pages/projects/ProjectsListPage";
import { ProjectDetailPage } from "@/pages/projects/ProjectDetailPage";
import { NewProjectPage } from "@/pages/projects/NewProjectPage";
import { ProjectSettingsPage } from "@/pages/projects/ProjectSettingsPage";

// Requirements
import { RequirementsPage } from "@/pages/requirements/RequirementsPage";
import { RequirementDetailPage } from "@/pages/requirements/RequirementDetailPage";
import { ImportRequirementsPage } from "@/pages/requirements/ImportRequirementsPage";

// Test Scripts
import { TestScriptsPage } from "@/pages/scripts/TestScriptsPage";
import { TestScriptDetailPage } from "@/pages/scripts/TestScriptDetailPage";
import { NewTestScriptPage } from "@/pages/scripts/NewTestScriptPage";

// Test Cycles
import { TestCyclesPage } from "@/pages/cycles/TestCyclesPage";
import { TestCycleDetailPage } from "@/pages/cycles/TestCycleDetailPage";
import { ExecuteTestPage } from "@/pages/cycles/ExecuteTestPage";

// Crawler
import { CrawlerPage } from "@/pages/crawler/CrawlerPage";

// Reports
import { CoverageReportPage } from "@/pages/reports/CoverageReportPage";
import { CycleSummaryPage } from "@/pages/reports/CycleSummaryPage";
import { AIUsagePage } from "@/pages/reports/AIUsagePage";

// Admin
import { UsersPage } from "@/pages/admin/UsersPage";
import { CompanySettingsPage } from "@/pages/admin/CompanySettingsPage";
import { GlobalAdminPage } from "@/pages/admin/GlobalAdminPage";

export default function App() {
  return (
    <BrowserRouter>
      <UnauthenticatedTemplate>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<LoginPage />} />
        </Routes>
      </UnauthenticatedTemplate>

      <AuthenticatedTemplate>
        <AppShell>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/login" element={<Navigate to="/dashboard" replace />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />

            {/* Dashboard */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />

            {/* Projects */}
            <Route
              path="/projects"
              element={
                <ProtectedRoute permission="project:read">
                  <ProjectsListPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/new"
              element={
                <ProtectedRoute permission="project:create">
                  <NewProjectPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId"
              element={
                <ProtectedRoute permission="project:read">
                  <ProjectDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/settings"
              element={
                <ProtectedRoute permission="project:update">
                  <ProjectSettingsPage />
                </ProtectedRoute>
              }
            />

            {/* Requirements */}
            <Route
              path="/projects/:projectId/requirements"
              element={
                <ProtectedRoute permission="requirement:read">
                  <RequirementsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/requirements/import"
              element={
                <ProtectedRoute permission="requirement:create">
                  <ImportRequirementsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/requirements/:requirementId"
              element={
                <ProtectedRoute permission="requirement:read">
                  <RequirementDetailPage />
                </ProtectedRoute>
              }
            />

            {/* Test Scripts */}
            <Route
              path="/projects/:projectId/scripts"
              element={
                <ProtectedRoute permission="script:read">
                  <TestScriptsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/scripts/new"
              element={
                <ProtectedRoute permission="script:create">
                  <NewTestScriptPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/scripts/:scriptId"
              element={
                <ProtectedRoute permission="script:read">
                  <TestScriptDetailPage />
                </ProtectedRoute>
              }
            />

            {/* Test Cycles */}
            <Route
              path="/projects/:projectId/cycles"
              element={
                <ProtectedRoute permission="cycle:read">
                  <TestCyclesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/cycles/:cycleId"
              element={
                <ProtectedRoute permission="cycle:read">
                  <TestCycleDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/cycles/:cycleId/execute/:assignmentId"
              element={
                <ProtectedRoute permission="result:create">
                  <ExecuteTestPage />
                </ProtectedRoute>
              }
            />

            {/* Crawler */}
            <Route
              path="/projects/:projectId/crawler"
              element={
                <ProtectedRoute permission="crawler:read">
                  <CrawlerPage />
                </ProtectedRoute>
              }
            />

            {/* Reports */}
            <Route
              path="/projects/:projectId/reports"
              element={
                <ProtectedRoute permission="report:read">
                  <CoverageReportPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/reports/coverage"
              element={
                <ProtectedRoute permission="report:read">
                  <CoverageReportPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/reports/cycles/:cycleId"
              element={
                <ProtectedRoute permission="report:read">
                  <CycleSummaryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects/:projectId/reports/ai-usage"
              element={
                <ProtectedRoute permission="report:read">
                  <AIUsagePage />
                </ProtectedRoute>
              }
            />

            {/* Admin */}
            <Route
              path="/users"
              element={
                <ProtectedRoute permission="user:read">
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute permission="admin:company">
                  <CompanySettingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/global"
              element={
                <ProtectedRoute permission="admin:global">
                  <GlobalAdminPage />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AppShell>
      </AuthenticatedTemplate>
    </BrowserRouter>
  );
}
