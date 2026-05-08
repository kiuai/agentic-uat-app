import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthenticatedTemplate, UnauthenticatedTemplate } from "@azure/msal-react";
import { Layout } from "@/components/layout/Layout";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { RequirementsPage } from "@/pages/RequirementsPage";
import { TestScriptsPage } from "@/pages/TestScriptsPage";
import { TestCyclesPage } from "@/pages/TestCyclesPage";
import { CrawlerPage } from "@/pages/CrawlerPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { UsersPage } from "@/pages/UsersPage";

export default function App() {
  return (
    <BrowserRouter>
      <UnauthenticatedTemplate>
        <Routes>
          <Route path="*" element={<LoginPage />} />
        </Routes>
      </UnauthenticatedTemplate>

      <AuthenticatedTemplate>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="/projects/:projectId/requirements" element={<RequirementsPage />} />
            <Route path="/projects/:projectId/scripts" element={<TestScriptsPage />} />
            <Route path="/projects/:projectId/cycles" element={<TestCyclesPage />} />
            <Route path="/projects/:projectId/crawler" element={<CrawlerPage />} />
            <Route path="/projects/:projectId/reports" element={<ReportsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Layout>
      </AuthenticatedTemplate>
    </BrowserRouter>
  );
}
