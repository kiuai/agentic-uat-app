# KAATS — REST API Design

**Version:** 1.0  
**Date:** 2026-05-07

---

## 1. Design Principles

| Principle | Details |
|---|---|
| **REST** | Resources are nouns; HTTP verbs express intent. No RPC-style verb endpoints. |
| **Versioned** | All endpoints are prefixed `/api/v1/`. Breaking changes increment the version. Non-breaking additions (new fields, new endpoints) do not require a version bump. |
| **Tenant-scoped** | The authenticated user's `tenant_id` is extracted from the JWT. The URL never contains a tenant prefix — tenancy is implicit. Global Admin endpoints use a separate `/api/v1/admin/` prefix. |
| **Consistent errors** | All errors follow the RFC 9457 Problem Details format. |
| **Pagination** | All list endpoints support cursor-based pagination via `?after=<cursor>&limit=<n>` (default limit 50, max 200). |
| **Async jobs** | Long-running operations (AI generation, crawling, export) return `202 Accepted` with a job resource URL. Clients poll or subscribe via SSE. |
| **HATEOAS (light)** | Responses include `_links` objects for common next-actions, without full HATEOAS complexity. |
| **OpenAPI** | FastAPI generates an OpenAPI 3.1 spec automatically. The spec is served at `/api/v1/openapi.json`. |

---

## 2. Base URL and Versioning

```
https://api.kaats.example.com/api/v1/
```

**Versioning strategy:**
- URI path versioning (`/api/v1/`, `/api/v2/`) is used because it is explicit, cacheable, and straightforward for clients.
- A deprecated version is supported for a minimum of 12 months after the successor version is GA.
- Deprecated endpoints return `Deprecation: true` and `Sunset: <date>` HTTP headers.

---

## 3. Authentication

All requests must carry a valid JWT in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

The token is obtained from Azure Entra ID via MSAL (PKCE for browser clients, client credentials for service-to-service). The FastAPI middleware validates:
1. JWT signature against Entra ID JWKS endpoint.
2. `aud` claim matches the KAATS API application registration.
3. `exp` claim — token not expired.
4. Custom `kaats_tenant_id` and `kaats_roles` claims present.

---

## 4. Error Format (RFC 9457)

```json
{
  "type": "https://kaats.example.com/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Project with id '550e8400-...' does not exist or is not accessible.",
  "instance": "/api/v1/projects/550e8400-...",
  "request_id": "req-abc123"
}
```

**Standard error types:**

| HTTP Status | `type` slug | When |
|---|---|---|
| 400 | `validation-error` | Request body fails schema validation |
| 401 | `unauthorized` | Missing or invalid JWT |
| 403 | `forbidden` | Valid JWT but insufficient role/permissions |
| 404 | `not-found` | Resource does not exist in this tenant |
| 409 | `conflict` | Duplicate unique constraint violation |
| 422 | `unprocessable` | Business rule violation (e.g., closing a locked cycle) |
| 429 | `rate-limited` | Tenant rate limit exceeded |
| 500 | `internal-error` | Unexpected server error |
| 503 | `service-unavailable` | Dependency (AOAI, SQL) temporarily down |

---

## 5. Pagination

All list endpoints accept:

| Query Parameter | Default | Description |
|---|---|---|
| `after` | `null` | Cursor (opaque string from previous response's `_pagination.next_cursor`) |
| `limit` | `50` | Number of items to return (max 200) |

Response envelope:

```json
{
  "data": [...],
  "_pagination": {
    "total": 342,
    "limit": 50,
    "has_more": true,
    "next_cursor": "eyJpZCI6IjU1MGU4..."
  }
}
```

---

## 6. Endpoint Reference

### 6.1 Projects

```
GET    /api/v1/projects                        List projects for the authenticated tenant
POST   /api/v1/projects                        Create a new project
GET    /api/v1/projects/{project_id}           Get project details
PATCH  /api/v1/projects/{project_id}           Update project (name, description, status)
DELETE /api/v1/projects/{project_id}           Archive project (soft delete)

GET    /api/v1/projects/{project_id}/environments          List environments
POST   /api/v1/projects/{project_id}/environments          Create environment
GET    /api/v1/projects/{project_id}/environments/{env_id} Get environment
PATCH  /api/v1/projects/{project_id}/environments/{env_id} Update environment
DELETE /api/v1/projects/{project_id}/environments/{env_id} Delete environment
```

### 6.2 Requirements

```
GET    /api/v1/projects/{project_id}/requirements              List requirements
POST   /api/v1/projects/{project_id}/requirements              Upload requirement (multipart/form-data or JSON)
GET    /api/v1/projects/{project_id}/requirements/{req_id}     Get requirement
PATCH  /api/v1/projects/{project_id}/requirements/{req_id}     Update tags/metadata
DELETE /api/v1/projects/{project_id}/requirements/{req_id}     Delete requirement

POST   /api/v1/projects/{project_id}/requirements/import-jira  Import from Jira (body: {project_key, filter})
POST   /api/v1/projects/{project_id}/requirements/import-ado   Import from Azure DevOps
```

**Requirement upload request (multipart):**

```
POST /api/v1/projects/{project_id}/requirements
Content-Type: multipart/form-data

file: <binary>
title: "Login Feature Requirements"
source_type: "PDF"
domain_code: "USER_MANAGEMENT"
tags: ["auth", "v2.1"]
```

### 6.3 AI Test Generation

```
POST   /api/v1/projects/{project_id}/generation-jobs          Trigger AI generation
GET    /api/v1/projects/{project_id}/generation-jobs          List generation jobs
GET    /api/v1/projects/{project_id}/generation-jobs/{job_id} Get job status
DELETE /api/v1/projects/{project_id}/generation-jobs/{job_id} Cancel job (if PENDING or PROCESSING)
```

**Trigger request:**

```json
POST /api/v1/projects/{project_id}/generation-jobs
{
  "requirement_ids": ["<uuid1>", "<uuid2>"],
  "output_formats": ["playwright_ts", "gherkin"],
  "generation_config": {
    "include_assertions": true,
    "include_negative_cases": false,
    "max_steps_per_script": 20
  }
}
```

**Response (202):**

```json
{
  "job_id": "<uuid>",
  "status": "PENDING",
  "created_at": "2026-05-07T10:00:00Z",
  "_links": {
    "self": "/api/v1/projects/{project_id}/generation-jobs/{job_id}",
    "result": "/api/v1/projects/{project_id}/test-scripts?source_job_id={job_id}"
  }
}
```

### 6.4 Crawler Jobs

```
POST   /api/v1/projects/{project_id}/crawl-jobs                Trigger crawl (Web or SAP Fiori)
GET    /api/v1/projects/{project_id}/crawl-jobs                List crawl jobs
GET    /api/v1/projects/{project_id}/crawl-jobs/{job_id}       Get job status + map
DELETE /api/v1/projects/{project_id}/crawl-jobs/{job_id}       Cancel crawl
```

**Web crawl request:**

```json
POST /api/v1/projects/{project_id}/crawl-jobs
{
  "crawler_type": "WEB",
  "target_url": "https://app.example.com",
  "auth_config": {
    "type": "form",
    "credentials_key_vault_ref": "kaats-crawl-creds-projectX"
  },
  "max_pages": 100,
  "exclude_patterns": ["/admin/*", "/logout"],
  "generate_scripts": true
}
```

**SAP Fiori crawl request:**

```json
POST /api/v1/projects/{project_id}/crawl-jobs
{
  "crawler_type": "SAP_FIORI",
  "launchpad_url": "https://fiori.example.com/sap/bc/ui5_ui5/ui2/ushell/shells/abap/FioriLaunchpad.html",
  "auth_config": {
    "type": "basic",
    "credentials_key_vault_ref": "kaats-sap-creds-projectX"
  },
  "tile_groups": ["Purchasing", "Finance"],
  "generate_scripts": true
}
```

### 6.5 Test Scripts

```
GET    /api/v1/projects/{project_id}/test-scripts                List test scripts
POST   /api/v1/projects/{project_id}/test-scripts                Create script manually
GET    /api/v1/projects/{project_id}/test-scripts/{script_id}    Get script (all formats)
PATCH  /api/v1/projects/{project_id}/test-scripts/{script_id}    Update script content/metadata
DELETE /api/v1/projects/{project_id}/test-scripts/{script_id}    Delete script

POST   /api/v1/projects/{project_id}/test-scripts/{script_id}/submit-review     Submit for approval
POST   /api/v1/projects/{project_id}/test-scripts/{script_id}/approve           Approve (VL / BPO)
POST   /api/v1/projects/{project_id}/test-scripts/{script_id}/reject            Reject with comments
POST   /api/v1/projects/{project_id}/test-scripts/{script_id}/reset             Reset to DRAFT

GET    /api/v1/projects/{project_id}/test-scripts/{script_id}/versions          Version history
GET    /api/v1/projects/{project_id}/test-scripts/{script_id}/versions/{ver}    Get specific version

POST   /api/v1/projects/{project_id}/test-scripts/{script_id}/export            Export in specific format
```

**Export request:**

```json
POST /api/v1/projects/{project_id}/test-scripts/{script_id}/export
{
  "format": "robot_framework",
  "include_data_table": true
}
```

**Export response:**

```json
{
  "format": "robot_framework",
  "content": "*** Settings ***\n...",
  "blob_uri": "https://blob.../exports/script-uuid-robot.robot",
  "expires_at": "2026-05-08T10:00:00Z"
}
```

### 6.6 Test Cycles

```
GET    /api/v1/projects/{project_id}/cycles                    List test cycles
POST   /api/v1/projects/{project_id}/cycles                    Create cycle
GET    /api/v1/projects/{project_id}/cycles/{cycle_id}         Get cycle + summary
PATCH  /api/v1/projects/{project_id}/cycles/{cycle_id}         Update cycle
DELETE /api/v1/projects/{project_id}/cycles/{cycle_id}         Delete cycle (DRAFT only)

POST   /api/v1/projects/{project_id}/cycles/{cycle_id}/activate  Activate cycle
POST   /api/v1/projects/{project_id}/cycles/{cycle_id}/close     Close and lock cycle
```

### 6.7 Executions

```
GET    /api/v1/projects/{project_id}/cycles/{cycle_id}/executions              List executions
POST   /api/v1/projects/{project_id}/cycles/{cycle_id}/executions              Add scripts to cycle (assign)
GET    /api/v1/projects/{project_id}/cycles/{cycle_id}/executions/{exec_id}    Get execution
PATCH  /api/v1/projects/{project_id}/cycles/{cycle_id}/executions/{exec_id}    Log result (status, notes)

POST   /api/v1/projects/{project_id}/cycles/{cycle_id}/executions/{exec_id}/evidence   Upload evidence
GET    /api/v1/projects/{project_id}/cycles/{cycle_id}/executions/{exec_id}/evidence   List evidence
```

**Log result request:**

```json
PATCH /api/v1/projects/{project_id}/cycles/{cycle_id}/executions/{exec_id}
{
  "status": "FAILED",
  "notes": "Assertion failed on step 3: expected 'Welcome' but got 'Error'",
  "executed_at": "2026-05-07T14:30:00Z"
}
```

### 6.8 Defects

```
GET    /api/v1/projects/{project_id}/defects          List defects
POST   /api/v1/projects/{project_id}/defects          Create defect
GET    /api/v1/projects/{project_id}/defects/{id}     Get defect
PATCH  /api/v1/projects/{project_id}/defects/{id}     Update defect
DELETE /api/v1/projects/{project_id}/defects/{id}     Delete defect

POST   /api/v1/projects/{project_id}/defects/{id}/export-jira   Push to Jira
POST   /api/v1/projects/{project_id}/defects/{id}/export-ado    Push to Azure DevOps
```

### 6.9 Reporting

```
GET    /api/v1/projects/{project_id}/reports/summary         Project-level pass/fail summary
GET    /api/v1/projects/{project_id}/reports/coverage        Requirement coverage report
GET    /api/v1/projects/{project_id}/reports/cycle/{id}      Cycle execution report

POST   /api/v1/projects/{project_id}/reports/export          Generate PDF/HTML report (async)
GET    /api/v1/projects/{project_id}/reports/schedule        List scheduled report deliveries
POST   /api/v1/projects/{project_id}/reports/schedule        Create scheduled delivery
DELETE /api/v1/projects/{project_id}/reports/schedule/{id}   Delete schedule
```

### 6.10 Jobs (Generic Status Endpoint)

```
GET    /api/v1/jobs/{job_id}     Get any job status (generation, crawl, export, report)
```

This single endpoint simplifies client polling for any async operation.

### 6.11 SSE (Server-Sent Events) for Real-Time Job Status

```
GET    /api/v1/jobs/{job_id}/events    SSE stream of job state transitions
```

Event format:

```
event: job_status
data: {"job_id": "<uuid>", "status": "PROCESSING", "progress": 40, "message": "Generating Playwright script..."}

event: job_status
data: {"job_id": "<uuid>", "status": "COMPLETED", "result_url": "/api/v1/projects/..."}
```

### 6.12 Admin Endpoints (Global / Enterprise Admin)

```
GET    /api/v1/admin/enterprises              List all enterprises
POST   /api/v1/admin/enterprises              Create enterprise
GET    /api/v1/admin/enterprises/{id}         Get enterprise
PATCH  /api/v1/admin/enterprises/{id}         Update enterprise
DELETE /api/v1/admin/enterprises/{id}         Deactivate enterprise

GET    /api/v1/admin/enterprises/{id}/companies    List companies
POST   /api/v1/admin/enterprises/{id}/companies    Create company

GET    /api/v1/admin/platform/stats           Platform-wide usage statistics
GET    /api/v1/admin/platform/jobs            All jobs across tenants (global admin only)
```

---

## 7. Common Query Parameters

All list endpoints support:

| Parameter | Type | Description |
|---|---|---|
| `after` | string | Pagination cursor |
| `limit` | integer | Page size (default 50, max 200) |
| `q` | string | Full-text search (where supported) |
| `status` | string | Filter by status |
| `created_after` | ISO 8601 | Filter by creation date |
| `created_before` | ISO 8601 | Filter by creation date |
| `sort` | string | Field to sort by (prefix `-` for descending, e.g. `-created_at`) |

---

## 8. Content Types

| Use Case | Content-Type |
|---|---|
| Standard JSON request/response | `application/json` |
| File uploads (requirements, evidence) | `multipart/form-data` |
| Exported script download | `text/plain` or `application/octet-stream` |
| SSE streams | `text/event-stream` |
| PDF report download | `application/pdf` |

---

## 9. Rate Limiting

Rate limits are enforced per tenant, not per user:

| Limit | Value |
|---|---|
| Standard API requests | 1000 req/min per tenant |
| AI generation jobs | 20 concurrent jobs per tenant |
| Crawler jobs | 5 concurrent crawl jobs per tenant |
| File uploads | 50 MB max per file |

Rate limit headers are included on every response:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1715080800
```

When exceeded, returns `429 Too Many Requests` with a `Retry-After` header.
