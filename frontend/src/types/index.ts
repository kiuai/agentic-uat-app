// ── Shared types mirroring backend Pydantic schemas ──────────────────────────

export type UserRole = "GADM" | "EADM" | "CADM" | "SM" | "VL" | "QA" | "VT" | "BPO";

// RoleAssignmentOut shape returned by /auth/me
export interface RoleAssignment {
  role: UserRole;
  tenant_id: string;
  domain_code: string | null;
  // Present in full DB responses but absent from /auth/me
  id?: string;
  user_id?: string;
  assigned_by?: string | null;
  created_at?: string;
}

// UserProfileOut returned by GET /api/v1/auth/me
export interface User {
  id: string;
  azure_oid: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_global_admin: boolean;
  last_login_at: string | null;
  roles: RoleAssignment[];
  /** Permission strings already resolved by the backend */
  permissions: string[];
  // Optional — present in full DB read but not in /auth/me
  created_at?: string;
  updated_at?: string;
}

// TenantOut returned by GET /api/v1/auth/tenants
export interface TenantOut {
  company_id: string;
  tenant_id: string;
  company_name: string;
  company_slug: string;
  enterprise_id: string;
  enterprise_name: string;
  roles: string[];
}

// Tenant structures
export interface Enterprise {
  id: string;
  name: string;
  slug: string;
  azure_ad_tenant_id: string | null;
  settings: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  enterprise_id: string;
  tenant_id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BusinessDomain {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Current user / tenant context
export interface CurrentUserContext {
  user: User;
  tenantId: string | null;
  companySlug: string | null;
  roles: UserRole[];
  permissions: string[];
}

export type ProjectStatus = "ACTIVE" | "ARCHIVED";
export type SystemType = "WEB" | "SAP_FIORI" | "API" | "MOBILE" | "DESKTOP";

export interface Project {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  system_type: SystemType;
  base_url: string | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Environment {
  id: string;
  tenant_id: string;
  project_id: string;
  name: string;
  type: "DEV" | "QA" | "UAT" | "PROD";
  base_url: string | null;
  requires_bpo_approval: boolean;
  gxp_mode: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectDashboard {
  project_id: string;
  name: string;
  total_requirements: number;
  pending_requirements: number;
  total_scripts: number;
  draft_scripts: number;
  approved_scripts: number;
  total_cycles: number;
  active_cycles: number;
  total_assignments: number;
  pass_rate: number;
}

export type RequirementStatus = "PENDING" | "PROCESSED" | "FAILED";
export type RequirementSourceType = "TEXT" | "DOCX" | "PDF" | "JIRA" | "ADO";
export type RequirementPriority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Requirement {
  id: string;
  tenant_id: string;
  project_id: string;
  title: string;
  description: string | null;
  source_type: RequirementSourceType;
  source_ref: string | null;
  content_text: string | null;
  blob_uri: string | null;
  business_domain: string | null;
  priority: RequirementPriority;
  tags: string[];
  status: RequirementStatus;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface QualityCheckResult {
  requirement_id: string;
  score: number;
  verdict: "TESTABLE" | "NEEDS_IMPROVEMENT" | "UNTESTABLE";
  issues: string[];
}

export type JobStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type JobType = "AI_GENERATION" | "WEB_CRAWL" | "SAP_CRAWL" | "EXPORT" | "REPORT";

export interface Job {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  created_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  cosmos_result_id: string | null;
}

export type ScriptStatus = "DRAFT" | "IN_REVIEW" | "APPROVED" | "REJECTED" | "LOCKED";
export type ScriptFormat =
  | "playwright_ts"
  | "playwright_js"
  | "selenium_python"
  | "pytest"
  | "robot_framework"
  | "gherkin";

export interface TestScript {
  id: string;
  tenant_id: string;
  project_id: string;
  requirement_id: string;
  title: string;
  description: string | null;
  format: ScriptFormat;
  status: ScriptStatus;
  cosmos_doc_id: string | null;
  current_version: number;
  is_ai_generated: boolean;
  approved_by: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TestScriptVersion {
  version_number: number;
  change_summary: string | null;
  is_ai_generated: boolean;
  created_by: string | null;
  created_at: string;
  // Present in DB-backed responses only
  id?: string;
  script_id?: string;
  cosmos_doc_id?: string;
}

export interface ScriptExport {
  format: ScriptFormat;
  content: string;
  blob_uri: string | null;
  download_url: string | null;
  expires_at: string | null;
  validation_errors: string[];
}

export type CycleStatus = "DRAFT" | "ACTIVE" | "COMPLETED" | "LOCKED";
export type ExecutionStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "PASSED"
  | "FAILED"
  | "BLOCKED"
  | "SKIPPED";

export interface TestCycle {
  id: string;
  tenant_id: string;
  project_id: string;
  environment_id: string;
  name: string;
  description: string | null;
  status: CycleStatus;
  created_by: string;
  lead_user_id: string | null;
  planned_start_date: string | null;
  planned_end_date: string | null;
  actual_start_date: string | null;
  actual_end_date: string | null;
  bpo_approved_by: string | null;
  bpo_approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestAssignment {
  id: string;
  tenant_id: string;
  cycle_id: string;
  script_id: string;
  script_version: number;
  assigned_to: string;
  assigned_by: string;
  status: ExecutionStatus;
  due_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestResult {
  id: string;
  tenant_id: string;
  assignment_id: string;
  status: ExecutionStatus;
  executed_by: string;
  executed_at: string;
  duration_seconds: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceItem {
  id: string;
  result_id: string;
  blob_uri: string;
  file_name: string;
  content_type: string | null;
  uploaded_by: string;
  uploaded_at: string;
}

// Reports
export interface ProjectSummaryReport {
  project_id: string;
  total_scripts: number;
  approved_scripts: number;
  total_requirements: number;
  total_cycles: number;
  active_cycles: number;
  total_assignments: number;
  passed: number;
  failed: number;
  blocked: number;
  not_started: number;
  pass_rate: number;
}

export interface ScriptCoverageReport {
  project_id: string;
  total_requirements: number;
  requirements_with_scripts: number;
  coverage_percent: number;
  requirements_without_scripts: string[];
}

export interface CycleSummaryReport {
  cycle_id: string;
  cycle_name: string;
  status: string;
  total_assignments: number;
  passed: number;
  failed: number;
  blocked: number;
  not_started: number;
  in_progress: number;
  pass_rate: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface AIUsageReport {
  project_id: string;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_scripts_generated: number;
  generated_at: string;
}

// Crawler
export interface CrawlJob {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  created_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  cosmos_result_id: string | null;
}

// Pagination
export interface PaginationMeta {
  total: number;
  limit: number;
  has_more: boolean;
  next_cursor: string | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  _pagination: PaginationMeta;
}

// API error
export interface ApiError {
  status: number;
  title: string;
  detail: string;
  type: string;
}

// Execution (legacy alias for TestAssignment)
export type Execution = TestAssignment;
