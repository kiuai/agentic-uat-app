# ADR-001: Technology Stack Selection

**Status:** Accepted  
**Date:** 2026-05-07  
**Deciders:** KIU AI Engineering Leadership

---

## Context

KAATS is a new greenfield SaaS application. We must select a technology stack that enables:
- Rapid development of AI-driven features.
- Multi-tenant isolation with regulatory-grade audit trails.
- Scalable async processing for AI and crawler workloads.
- A modern, maintainable codebase that the KIU AI team can own long-term.

---

## Decisions and Rationale

### Backend: Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic

**Decision:** Use Python 3.12 with FastAPI as the web framework, SQLAlchemy 2.x with `asyncio` support for ORM, and Alembic for database migrations.

**Rationale:**
- Python is the lingua franca for AI/ML tooling. LangChain, Azure OpenAI SDK, and Playwright's Python bindings are all first-class. Having the API and AI/crawler worker in the same language eliminates context switching and allows shared library code.
- FastAPI provides automatic OpenAPI doc generation, native `async/await` support (critical for high-concurrency AI calls), Pydantic v2 for request/response validation, and dependency injection for clean middleware composition (auth, tenant context, RBAC).
- SQLAlchemy 2.x async supports the `asyncpg`/`aioodbc` drivers needed for non-blocking DB access in an async FastAPI context.
- Alembic provides version-controlled, reproducible schema migrations — mandatory for a multi-tenant production system.

**Alternatives Considered:**
- **Node.js / NestJS:** Strong ecosystem but the AI tooling in Python is significantly ahead. We'd need to bridge to Python for AI features anyway.
- **Go:** Excellent performance, but the AI/ML library ecosystem (LangChain equivalent) is immature.
- **Django:** ORM is synchronous by default; Django's monolithic structure is less suited for a microservice split between API and worker.

---

### Frontend: React 18 + TypeScript + Vite + Shadcn/ui + TanStack Query

**Decision:** React 18 SPA with TypeScript, Vite for build tooling, Shadcn/ui for accessible component primitives, and TanStack Query for server state management.

**Rationale:**
- React 18 with concurrent features supports the complex, interactive dashboards and data tables required for test cycle management.
- TypeScript enforces correctness at scale; combined with the FastAPI-generated OpenAPI spec and tools like `openapi-typescript`, the frontend and backend type contract is maintained automatically.
- Vite offers dramatically faster HMR and build times than Create React App or Webpack, improving developer experience.
- Shadcn/ui provides unstyled, accessible components built on Radix UI primitives. Unlike UI libraries that bundle their own CSS, Shadcn copies component source into the project, allowing full customization without fighting a library's opinion.
- TanStack Query (React Query) manages server state, caching, background re-fetching, and the polling patterns needed for async job status — a core interaction in KAATS.

**Alternatives Considered:**
- **Next.js:** SSR benefits are minimal for a SaaS app behind authentication. The added build complexity is not justified.
- **Vue 3 / Nuxt:** Smaller talent pool within the KIU AI team; React expertise is stronger.
- **Angular:** Opinionated, heavier framework. Slower to prototype AI-driven UI features.

---

### AI Integration: Azure OpenAI (GPT-4o) + LangChain

**Decision:** Azure OpenAI service with a GPT-4o deployment as the AI backend. LangChain for prompt orchestration, chaining, and output parsing.

**Rationale:**
- Azure OpenAI provides the data privacy and compliance guarantees required by enterprise customers (no training on customer data, data residency in chosen Azure regions).
- GPT-4o has the code generation and reasoning capabilities needed to produce syntactically correct, runnable test scripts across multiple frameworks.
- LangChain's prompt templating, output parsers, and chain composition reduce boilerplate for multi-step AI workflows (e.g., decompose requirements → generate test cases → format into framework-specific syntax).

**Alternatives Considered:**
- **Direct OpenAI API (non-Azure):** Does not meet enterprise compliance requirements.
- **AWS Bedrock (Claude):** Not on Azure; would require a cross-cloud dependency and duplicate IAM management.
- **Custom fine-tuned model:** Significantly higher cost and maintenance burden. GPT-4o in-context learning with well-crafted prompts achieves the required quality.

See ADR-003 for detailed AI integration architecture.

---

### Primary Database: Azure SQL (Azure SQL Database, General Purpose)

**Decision:** Azure SQL Database (PaaS, General Purpose tier) as the primary relational store.

**Rationale:**
- Azure SQL is fully managed (backups, patching, HA replica), reducing operational burden.
- Row-level security is a first-class, well-documented feature — essential for multi-tenant data isolation.
- T-SQL stored procedures and row-level security policies give us defense-in-depth at the database layer, not just the application layer.
- The General Purpose tier provides predictable performance with separate compute and storage scaling.
- The KIU AI team has existing SQL Server expertise.

**Alternatives Considered:**
- **PostgreSQL (Azure Database for PostgreSQL):** Excellent row-level security support; similar capability. Azure SQL was chosen for team familiarity and the strong managed PaaS offering.
- **Azure Cosmos DB (NoSQL only):** Not suitable as a primary relational store for complex joins (user → project → requirement → execution chains).

---

### Artifact Store: Azure Cosmos DB

**Decision:** Azure Cosmos DB (NoSQL API) for test script artifacts, crawl maps, and AI logs.

**Rationale:**
- Test script documents are variable-schema (different AI output formats, different number of script variants per document). A document model is a natural fit.
- Per-tenant containers provide physical data isolation without schema-level tricks.
- Cosmos DB's global distribution and autoscale throughput (RU/s) handle bursty AI generation workloads efficiently.
- TTL on AI log documents automates retention management.

---

### Message Queue: Azure Service Bus

**Decision:** Azure Service Bus for decoupling API from worker processes.

**Rationale:**
- Service Bus provides durable, ordered, at-least-once message delivery with dead-letter queues — critical for ensuring no AI generation or crawl job is silently dropped.
- KEDA's Service Bus scaler allows the Worker Container App to scale to zero, minimizing cost when idle.
- Sessions in Service Bus allow per-tenant message ordering if needed.
- The competing consumer pattern means multiple worker replicas can process jobs in parallel without coordination overhead.

**Alternatives Considered:**
- **Azure Storage Queues:** Simpler but lacks dead-letter support, message locking, and sessions.
- **RabbitMQ:** Would require self-managed infrastructure; Service Bus is fully managed.
- **Azure Event Hubs:** Optimized for high-throughput streaming/analytics, not job dispatch.

---

### Infrastructure: Azure Container Apps + Azure Bicep

**Decision:** Azure Container Apps for hosting, Azure Bicep for IaC.

**Rationale:**
- Container Apps is a managed Kubernetes-based platform. We get autoscaling (including KEDA), managed ingress, and container orchestration without managing the Kubernetes control plane.
- Three separate Container Apps (api, worker, frontend) gives us independent scaling, deployment, and secret management per component.
- Azure Bicep is the Azure-native IaC language, with first-class support for all Azure resource types and strong VS Code tooling. It compiles to ARM templates, so it integrates natively with Azure deployment pipelines.

**Alternatives Considered:**
- **Azure Kubernetes Service (AKS):** More control but significantly higher operational complexity. Container Apps provides 90% of the capability at 10% of the ops burden for our scale.
- **Azure App Service:** Lacks the KEDA-based scaling needed for the worker.
- **Terraform:** Cross-cloud but requires a separate state backend and has a lag in supporting new Azure resource types. Bicep's Azure-native support outweighs Terraform's multi-cloud portability for an Azure-only deployment.

---

## Consequences

**Positive:**
- A Python monorepo (API + worker) simplifies shared code for AI utilities, tenant middleware, and data models.
- FastAPI + Pydantic + OpenAPI enables automatic client SDK generation for future external integrations.
- Azure-native stack minimizes integration complexity and vendor support surface.

**Negative / Risks:**
- LangChain is a fast-moving library; API breaking changes are common. We mitigate by pinning versions and using a thin abstraction layer over LangChain in the worker.
- Azure SQL row-level security requires discipline — any raw SQL query that bypasses SQLAlchemy must manually enforce tenant context.
- Azure Container Apps is newer than AKS; some advanced networking scenarios may require workarounds.
