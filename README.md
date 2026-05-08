# KIU AI Automated Test System (KAATS)

KAATS is a production-grade, multi-tenant SaaS platform that uses Azure OpenAI (GPT-4o) to generate executable test scripts from software requirements. It also crawls live web applications and SAP Fiori launchpads to produce test automation artifacts in Playwright, Selenium, Pytest, Robot Framework, and Gherkin formats.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design.

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| Worker | Python 3.12, Azure Service Bus consumer, Playwright |
| Frontend | React 18, TypeScript, Vite, Shadcn/ui, TanStack Query |
| AI | Azure OpenAI GPT-4o, LangChain |
| Auth | Azure Entra ID (MSAL), JWT, custom RBAC |
| Primary DB | Azure SQL Database (row-level security, multi-tenant) |
| Artifact DB | Azure Cosmos DB (per-tenant containers) |
| File Storage | Azure Blob Storage (per-tenant containers) |
| Queue | Azure Service Bus |
| Infra | Azure Container Apps, Azure Bicep |

## Repository Layout

```
kaats/
├── backend/          Python API + Worker (FastAPI, SQLAlchemy, Playwright)
├── frontend/         React 18 SPA (TypeScript, Vite, Shadcn/ui)
├── docs/             Architecture docs and ADRs
├── infrastructure/   Azure Bicep IaC
└── .github/          GitHub Actions CI/CD workflows
```

## Quickstart (Docker Compose)

**Prerequisites:** Docker Desktop, at minimum 6 GB RAM allocated.

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — fill AZURE_OPENAI_* and AZURE_*_CLIENT_ID / TENANT_ID

# 2. Start all services (SQL Server, Azurite, Service Bus emulator, API, Worker, Frontend)
docker compose up --build

# 3. Initialize the database (first run only)
docker compose run --rm db-init

# Services:
#   API:      http://localhost:8000   (OpenAPI docs: http://localhost:8000/docs)
#   Frontend: http://localhost:5173
#   SQL:      localhost:1433
#   Azurite:  localhost:10000 (Blob), 10001 (Queue)
```

## Local Dev (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp ../.env.example ../.env  # edit values
alembic upgrade head
uvicorn app.main:app --reload

# Worker (separate terminal)
python -m app.worker.service_bus_worker

# Frontend
cd frontend
npm install
cp .env.example .env.local  # edit values
npm run dev
```

## Running Tests

```bash
# Backend unit + integration tests
cd backend
pytest -v

# Frontend unit tests
cd frontend
npm run test

# E2E (requires running stack)
cd frontend
npm run test:e2e
```

## Documentation

| Document | Description |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture and component diagrams |
| [`docs/RBAC_MATRIX.md`](docs/RBAC_MATRIX.md) | Role-based access control permission matrix |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Database entity relationships and schemas |
| [`docs/API_DESIGN.md`](docs/API_DESIGN.md) | REST API design principles and endpoint reference |
| [`docs/ADR/001-tech-stack.md`](docs/ADR/001-tech-stack.md) | Technology stack decisions |
| [`docs/ADR/002-multi-tenancy.md`](docs/ADR/002-multi-tenancy.md) | Multi-tenancy approach |
| [`docs/ADR/003-ai-integration.md`](docs/ADR/003-ai-integration.md) | Azure OpenAI integration design |
| [`docs/ADR/004-crawler-design.md`](docs/ADR/004-crawler-design.md) | Playwright crawler design |

## Contributing

1. Install pre-commit hooks: `pre-commit install`
2. Branch from `main`: `git checkout -b feat/your-feature`
3. All PRs require passing CI (ruff, mypy, pytest ≥70% coverage, ESLint)
