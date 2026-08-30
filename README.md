# ChangeGuard

ChangeGuard imports real pull-request evidence, computes dependency blast radius, applies deterministic deployment policy, and reads live rollout health before promotion.

## What works

- **Change review:** imports PR metadata, changed files, commit SHA, and check runs from GitHub REST APIs. Public repositories work without a token; private repositories use `GITHUB_TOKEN`.
- **Dependencies:** loads a versioned service catalog and calculates transitive downstream impact from changed paths.
- **Rollout signals:** queries Prometheus for service request/error rates and reads an Argo Rollout custom resource through the Kubernetes API.
- **Audit:** stores source evidence and policy decisions in SQLite.
- **Webhook:** verifies GitHub HMAC signatures and analyzes supported pull-request events.
- **AI Release Ops:** uses LangChain and `gpt-4o-mini` specialists to interpret release requests, then persists a deterministic execution plan.
- **Guarded execution:** verifies an approved GitHub change-request issue before dispatching `release-deploy.yml`; GitHub Environment approval remains mandatory for production.

Missing connectors are reported as **not configured**. ChangeGuard does not substitute sample metrics or simulated rollout state.

## Run locally

```powershell
Copy-Item .env.example .env
docker compose up --build 
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

For a public GitHub repository, no secret is needed. Enter `owner/repository` and a PR number in **Change review**.

## Connect an environment

Set these values in `.env` before starting Compose:

| Variable | Purpose |
| --- | --- |
| `GITHUB_TOKEN` | Private repository access and higher GitHub API rate limits |
| `GITHUB_WEBHOOK_SECRET` | Validates `X-Hub-Signature-256` on incoming webhooks |
| `OPENAI_API_KEY` | Enables LangChain release intent and specialist agents |
| `OPENAI_MODEL` | Defaults to `gpt-4o-mini` |
| `SERVICE_CATALOG_PATH` | Catalog location; Compose uses `/app/config/service-catalog.json` |
| `PROMETHEUS_URL` | Prometheus base URL reachable by the backend |
| `KUBERNETES_API_URL` | Kubernetes control-plane URL |
| `KUBERNETES_TOKEN` | Read-only service-account token for Argo Rollout resources |

Grant the Kubernetes service account only `get` access to `rollouts.argoproj.io` in the namespaces ChangeGuard observes.

## Service catalog

Create a real catalog from the clearly marked example, then edit it to match your repositories and service paths:

```powershell
Copy-Item backend/config/service-catalog.example.json backend/config/service-catalog.json
```

```json
{
  "services": [
    {
      "name": "checkout-api",
      "repository": "company/commerce-platform",
      "paths": ["services/checkout/"],
      "depends_on": ["payments-api", "orders-api"]
    }
  ]
}
```

When an imported PR changes a matching path, ChangeGuard finds every transitive dependant and includes that blast radius in risk scoring.

## Decision boundary

GitHub, the service catalog, Prometheus, and Kubernetes supply evidence. The deterministic risk engine decides whether controls are met. Current rollout integration is read-only: it observes rollout state but does not promote or abort resources.

## AI Release Ops

The submenu accepts a developer request, target repository, semantic version, and optional change-request issue. Planning calls three structured LangChain roles and stores their opinions, but their output cannot bypass these code-level controls:

- only `main` or `master` can be released;
- production requires a change-request issue;
- immediately before dispatch, the issue must still be open and labeled `change-approved`;
- only the fixed `.github/workflows/release-deploy.yml` workflow can be dispatched;
- the target repository's protected `production` environment performs the final human approval.

`GITHUB_TOKEN` needs repository Actions write access and Issues read access on the delivery repository. Do not place the token or OpenAI key in source control.
