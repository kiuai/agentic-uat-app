// ── Shared types mirroring backend Pydantic schemas ──────────────────────────

export type UserRole = "GADM" | "EADM" | "CADM" | "SM" | "VL" | "QA" | "VT" | "BPO";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  role: UserRole;
  domains: string[];
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export type ProjectStatus = "ACTIVE" | "ARCHIVED";

export interface Project {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export type RequirementStatus = "PENDING" | "PROCESSED" | "FAILED";
export type RequirementSourceType = "TEXT" | "DOCX" | "PDF" | "JIRA" | "ADO";

export interface Requirement {
  id: string;
  project_id: string;
  title: string;
  source_type: RequirementSourceType;
  source_ref: string | null;
  content_text: string | null;
  blob_uri: string | null;
  status: RequirementStatus;
  domain_code: string | null;
  uploaded_by: string;
  created_at: string;
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
  project_id: string;
  title: string;
  description: string | null;
  status: ScriptStatus;
  version: number;
  tags: string[];
  domain_code: string | null;
  scripts: Partial<Record<ScriptFormat, string>>;
  created_at: string;
  updated_at: string;
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
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
  project_id: string;
  environment_id: string;
  name: string;
  status: CycleStatus;
  created_by: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Execution {
  id: string;
  cycle_id: string;
  cosmos_script_id: string;
  script_version: number;
  assigned_to: string;
  executed_by: string | null;
  status: ExecutionStatus;
  notes: string | null;
  executed_at: string | null;
}

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
