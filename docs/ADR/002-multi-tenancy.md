# ADR-002: Multi-Tenancy Approach

**Status:** Accepted  
**Date:** 2026-05-07  
**Deciders:** KIU AI Engineering Leadership

---

## Context

KAATS is a multi-tenant SaaS application serving enterprise customers across regulated industries. The multi-tenancy model must satisfy:
- **Data isolation:** A bug in the application layer must not expose one tenant's data to another.
- **Scalability:** The model must support hundreds of company tenants without per-tenant infrastructure provisioning.
- **Compliance:** Regulated customers (GxP, SOX) require demonstrable data segregation.
- **Operational simplicity:** A single database schema and single application codebase must serve all tenants.

---

## Options Considered

### Option A: Separate Database per Tenant
Each tenant gets a dedicated Azure SQL database.

**Pros:** Maximum isolation; database-level access controls; easy backup/restore per tenant.  
**Cons:** Hundreds of databases to manage, patch, and monitor; cross-tenant analytics requires federation; schema migrations across all databases are complex; cost scales linearly with tenant count.

### Option B: Separate Schema per Tenant (Schema-per-Tenant)
One Azure SQL server, but each tenant's tables live in a dedicated schema.

**Pros:** Better isolation than shared schema; database-level operations still manageable.  
**Cons:** Schema proliferation; SQLAlchemy/Alembic multi-schema management is non-trivial; still does not protect against application bugs that issue queries against the wrong schema.

### Option C: Shared Database + Shared Schema + Row-Level Security (RLS)
All tenants share one schema. Every table has a `tenant_id` column. Azure SQL row-level security enforces that a database session can only see rows matching its `SESSION_CONTEXT(N'tenant_id')`.

**Pros:** Single schema to migrate; operational simplicity; RLS provides a database-level safety net independent of application logic; cost-efficient.  
**Cons:** A misconfigured RLS policy or a session that forgets to set context could expose data — requires rigorous testing and code review.

---

## Decision

**Option C — Shared Database + Shared Schema + Row-Level Security** is selected.

---

## Detailed Design

### Three-Tier Tenant Hierarchy

```
GLOBAL (KIU AI platform)
  └── ENTERPRISE (contracted customer org, e.g., Pharma Corp)
        └── COMPANY (operational business unit, e.g., US R&D)
```

- The `tenant_id` used in RLS policies corresponds to the **Company** level.
- Enterprise-level operations (cross-company reporting, user management) are performed by queries that join via the `companies` table, not by bypassing RLS.
- Global Administrator sessions connect with a privileged database user (`kaats_admin`) that is exempt from RLS predicates. All Global Admin actions are doubly logged.

### Row-Level Security Implementation

Every tenant-scoped table has a `tenant_id UUID NOT NULL` column. Two predicate types are applied:

1. **FILTER predicate** — `SELECT`, `UPDATE`, `DELETE` statements silently filter to the current tenant's rows.
2. **BLOCK predicate** — `INSERT`, `UPDATE` statements that would create/move rows to a different tenant are blocked with an error.

```sql
-- Step 1: Predicate function (defined once in security schema)
CREATE FUNCTION security.fn_tenant_predicate(@tenant_id UUID)
RETURNS TABLE WITH SCHEMABINDING AS
RETURN
    SELECT 1 AS authorized
    WHERE @tenant_id = CAST(SESSION_CONTEXT(N'tenant_id') AS UNIQUEIDENTIFIER)
       OR IS_MEMBER('kaats_admin') = 1;  -- Global Admin bypass

-- Step 2: Applied to each table
CREATE SECURITY POLICY security.policy_projects
    ADD FILTER PREDICATE security.fn_tenant_predicate(tenant_id) ON dbo.projects,
    ADD BLOCK  PREDICATE security.fn_tenant_predicate(tenant_id) ON dbo.projects
    WITH (STATE = ON);
```

### SQLAlchemy Session Context Middleware

The FastAPI middleware sets `SESSION_CONTEXT` on every database connection checkout:

```python
# Executed before every request handler
async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("EXEC sp_set_session_context N'tenant_id', :tid"),
        {"tid": str(tenant_id)}
    )
```

This is wired into a SQLAlchemy event listener on the `connect` event so it applies to every connection from the pool, including connections reused across requests.

### Cosmos DB Tenant Isolation

- Container naming: `kaats-{tenant_id}` (one container per company tenant).
- Partition key within each container: `/project_id`.
- The Worker and API apps receive their tenant scope from the JWT and construct the container name dynamically — they never accept a container name from user input.

```python
def get_cosmos_container(tenant_id: UUID, cosmos_client: CosmosClient) -> ContainerProxy:
    db = cosmos_client.get_database_client("kaats")
    return db.get_container_client(f"kaats-{tenant_id}")
```

### Blob Storage Tenant Isolation

- Container naming: `tenant-{tenant_id}`.
- Azure RBAC: the API and Worker Managed Identities are granted `Storage Blob Data Contributor` on each tenant container at provisioning time (via Bicep).
- Files are addressed as: `tenant-{tenant_id}/{project_id}/{category}/{filename}`.

---

## Consequences

**Positive:**
- Single Alembic migration set applies to all tenants simultaneously.
- Cross-tenant queries (for Global Admin dashboards) are straightforward — connect as `kaats_admin`, query without RLS filter.
- Adding new tenants requires only: create DB record, provision Cosmos container, provision Blob container. No new database servers.

**Negative / Mitigations:**
- **RLS misconfiguration risk:** Mitigated by integration tests that verify cross-tenant queries return zero results. Every PR touching RLS policy or session context code requires two reviewers.
- **Session context not set:** Mitigated by a FastAPI startup health check that verifies RLS is active, and a middleware assertion that panics if `tenant_id` is missing from the JWT on a tenant-scoped endpoint.
- **Performance:** With large tenants, `tenant_id` is the leading column on all indexes so SQL can seek directly without scanning cross-tenant rows.

---

## Compliance Notes

For GxP/SOX regulated company environments, the KAATS platform offers:
- **Signed audit logs** — a HMAC signature appended to each `audit_logs` row prevents tampering (key stored in Key Vault).
- **Immutable execution records** — executions in a `LOCKED` cycle cannot be modified or deleted even by Global Admin via the application layer.
- **Data residency** — tenant data can be pinned to a specific Azure region by deploying a regional KAATS instance. The multi-tenant model supports this without architectural changes.
