# GitHub Repository Setup Guide

Complete setup instructions for KAATS CI/CD pipelines, OIDC federation, branch
protection, and environment protection rules.

---

## 1. GitHub Environments

Create three environments in **Settings → Environments**:

| Environment | Purpose | Protection |
|---|---|---|
| `staging` | Auto-deploy from `main` | No approval required |
| `production` | Manual deploy or tag push | **2 approvals required** |

### Creating environments

1. Go to **Settings → Environments → New environment**
2. Name: `staging` — leave protection unchecked
3. Name: `production` — enable **Required reviewers**, add the `production-approvers` team (minimum 2)

---

## 2. OIDC Federation with Azure

No long-lived service principal secrets are stored in GitHub. All Azure
operations use OIDC tokens federated to a User-Assigned Managed Identity.

### Step 1 — Create a dedicated GitHub Actions managed identity

```bash
# One identity per environment is recommended (staging and prod)
az identity create \
  --name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --location eastus
```

### Step 2 — Assign required roles

```bash
IDENTITY_ID=$(az identity show \
  --name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --query id --output tsv)

PRINCIPAL_ID=$(az identity show \
  --name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --query principalId --output tsv)

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Contributor on the resource group (for Container App updates)
az role assignment create \
  --assignee "${PRINCIPAL_ID}" \
  --role "Contributor" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/rg-kaats-staging"

# AcrPush on the Container Registry (for image push)
ACR_ID=$(az acr show --name kaatsstagingacr --resource-group rg-kaats-staging --query id --output tsv)
az role assignment create \
  --assignee "${PRINCIPAL_ID}" \
  --role "AcrPush" \
  --scope "${ACR_ID}"
```

### Step 3 — Add federated credentials to the managed identity

```bash
CLIENT_ID=$(az identity show \
  --name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --query clientId --output tsv)

# For the main branch (build + deploy-staging workflows)
az identity federated-credential create \
  --name github-main \
  --identity-name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:YOUR_ORG/agentic-uat-app:ref:refs/heads/main \
  --audiences api://AzureADTokenExchange

# For the staging environment (deploy-staging workflow)
az identity federated-credential create \
  --name github-env-staging \
  --identity-name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:YOUR_ORG/agentic-uat-app:environment:staging \
  --audiences api://AzureADTokenExchange

# For the production environment (deploy-production workflow)
az identity federated-credential create \
  --name github-env-production \
  --identity-name kaats-github-actions \
  --resource-group rg-kaats-prod \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:YOUR_ORG/agentic-uat-app:environment:production \
  --audiences api://AzureADTokenExchange

# For pull requests (pr-preview workflow)
az identity federated-credential create \
  --name github-prs \
  --identity-name kaats-github-actions \
  --resource-group rg-kaats-staging \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:YOUR_ORG/agentic-uat-app:pull_request \
  --audiences api://AzureADTokenExchange
```

Replace `YOUR_ORG` with your GitHub organisation or username.

---

## 3. Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**.

### Repository secrets (available to all workflows)

| Secret | Description | How to get |
|---|---|---|
| `AZURE_CLIENT_ID` | Client ID of the GitHub Actions managed identity | `az identity show --name kaats-github-actions --query clientId` |
| `AZURE_TENANT_ID` | Azure AD tenant ID | `az account show --query tenantId` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | `az account show --query id` |
| `ACR_LOGIN_SERVER` | ACR login server URL | `az acr show --name <name> --query loginServer` |
| `SLACK_WEBHOOK_URL` | Incoming webhook URL for deploy notifications | Slack → App directory → Incoming Webhooks |
| `CODECOV_TOKEN` | Coverage reporting token | [codecov.io](https://codecov.io) → Settings |

### Environment secrets (staging)

Set these under **Settings → Environments → staging → Environment secrets**:

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | Can be the same identity or a staging-specific one |
| `VITE_AZURE_CLIENT_ID` | Azure AD App Registration client ID for MSAL |
| `VITE_API_BASE_URL_STAGING` | Staging API base URL (set after first infra deploy) |

### Environment secrets (production)

Set these under **Settings → Environments → production → Environment secrets**:

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | Production managed identity client ID |
| `VITE_AZURE_CLIENT_ID` | Azure AD App Registration client ID for MSAL |
| `VITE_API_BASE_URL_PROD` | Production API base URL |

---

## 4. Branch Protection Rules

Go to **Settings → Branches → Add branch protection rule** for `main`:

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ |
| Required approvals | 1 |
| Dismiss stale reviews on new commits | ✅ |
| Require review from Code Owners | ✅ (after adding CODEOWNERS) |
| Require status checks to pass | ✅ |
| **Required status checks** | see below |
| Require branches to be up to date | ✅ |
| Restrict force pushes | ✅ |
| Restrict deletions | ✅ |

### Required status checks (paste exact names):

```
Backend — Lint & Type-check
Backend — Tests & Coverage
Frontend — Lint, Type-check & Tests
Security — SAST & Dependency Audit
```

---

## 5. Workflow Trigger Summary

| Workflow | Trigger |
|---|---|
| **CI** (`ci.yml`) | Push to any branch except `main`/`release/**`; PR to `main` |
| **Build** (`build.yml`) | Push to `main`; tag push `v*.*.*` |
| **Deploy Staging** (`deploy-staging.yml`) | After **Build** workflow succeeds on `main` |
| **Deploy Production** (`deploy-production.yml`) | Manual `workflow_dispatch`; tag push `v*.*.*` |
| **PR Preview** (`pr-preview.yml`) | PR opened/synchronised/closed against `main` |
| **DB Migration Check** (`database-migration.yml`) | Push/PR touching `backend/migrations/**` |
| **Security Audit** (`security.yml`) | Daily at 02:00 UTC; manual dispatch |

---

## 6. Cosign & SBOM Setup

The build workflow uses keyless Cosign signing (OIDC-backed, no key management):

```bash
# Verify an image signature after deployment
cosign verify \
  --certificate-identity-regexp "https://github.com/YOUR_ORG/agentic-uat-app" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  YOUR_ACR.azurecr.io/kaats-api:latest
```

SBOMs are uploaded as GitHub Actions artifacts and can be downloaded per-run.

---

## 7. First-time Deployment Checklist

```
[ ] Infrastructure deployed via infrastructure/bicep/scripts/deploy.sh dev
[ ] Azure AD App Registration created and MSAL configured
[ ] GitHub Actions managed identity created with federated credentials
[ ] All repository secrets populated
[ ] staging and production GitHub environments created
[ ] Production environment: 2 required approvers configured
[ ] Branch protection on main with required checks
[ ] Dockerfiles present: backend/Dockerfile, backend/Dockerfile.worker, frontend/Dockerfile
[ ] First push to main → Build workflow triggers → images pushed to ACR
[ ] Deploy Staging triggers automatically after Build
[ ] Smoke tests pass against https://kaats-staging-api.<domain>
[ ] Manual production deploy: Actions → Deploy — Production → Run workflow
```
