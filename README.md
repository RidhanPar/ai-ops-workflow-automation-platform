# AI Operations & Workflow Automation Platform

**A workflow automation platform for support and operations teams. A custom rule-based engine written in Python and FastAPI turns ticket events into routing, escalation, and notification actions, with an optional LLM assistant (OpenAI or Anthropic) for ticket analysis and Prometheus-backed monitoring dashboards.**

This portfolio project turns operational events into auditable automated actions. The core is a rule-based workflow engine: configurable triggers match ticket attributes and run ordered actions that route events, notify teams, and queue sensitive escalations for human approval instead of executing them silently. An optional LangGraph agent retrieves knowledge, checks history, and produces a Pydantic-validated recommendation through a provider-agnostic LLM layer that supports both OpenAI and Anthropic, selectable by config. When no API key is set for the selected provider it falls back to deterministic keyword rules, so the demo runs at zero cost.

[Live dashboard](https://ridhan-ai-ops-dashboard.onrender.com) · [API documentation](https://ridhan-ai-ops-api.onrender.com/docs) · [API health](https://ridhan-ai-ops-api.onrender.com/health)

`workflow-engine` `fastapi` `langgraph` `openai` `anthropic`

![Secure agent dashboard](assets/screenshots/secure-agent-dashboard.png)

## Reviewer Guide

| Capability | Evidence |
|---|---|
| LangGraph agent and explicit tools | [`backend/app/services/agent.py`](backend/app/services/agent.py) |
| Provider-agnostic LLM layer (OpenAI and Anthropic) | [`backend/app/services/llm_provider.py`](backend/app/services/llm_provider.py) |
| RAG/vector search | [`backend/app/services/knowledge.py`](backend/app/services/knowledge.py), pgvector migration |
| Authentication and RBAC | [`backend/app/core/security.py`](backend/app/core/security.py) |
| Audit, approvals, idempotency | [`backend/app/services/audit.py`](backend/app/services/audit.py), [`backend/app/services/workflows.py`](backend/app/services/workflows.py) |
| Tracing, latency, cost | [`backend/app/core/observability.py`](backend/app/core/observability.py), dashboard trace panel |
| LLM evaluation | [`backend/evaluations/`](backend/evaluations/) |
| CI and tests | [`backend/tests/`](backend/tests/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Migrations and production deployment | [`backend/migrations/`](backend/migrations/), [`docker-compose.prod.yml`](docker-compose.prod.yml), [`render.yaml`](render.yaml) |
| Prometheus metrics and Grafana dashboard | [`monitoring/`](monitoring/), [`docker-compose.monitoring.yml`](docker-compose.monitoring.yml) |
| Kubernetes manifests and autoscaling | [`k8s/`](k8s/), [`.github/workflows/k8s-validate.yml`](.github/workflows/k8s-validate.yml) |
| AI assistant offline evaluation (CI) | [`backend/evaluations/eval_ai_assistant.py`](backend/evaluations/eval_ai_assistant.py) |
| Risk review: RBAC, packages, assessments, decisions | [`backend/app/routers/risks.py`](backend/app/routers/risks.py) |
| Risk decision-package evaluation (CI) | [`backend/evaluations/eval_decision_packages.py`](backend/evaluations/eval_decision_packages.py) |
| Risk review design, separation of duties | [`docs/RISK_REVIEW.md`](docs/RISK_REVIEW.md) |

## Implemented Production Signals

- LangGraph orchestration with explicit `search_knowledge_base`, `get_customer_history`, and approval-gated update-request tools.
- Pydantic structured output validation with separate invalid-output, provider-failure, and unexpected-failure fallbacks.
- PostgreSQL pgvector HNSW index with deterministic local-vector fallback for zero-cost demos and SQLite tests.
- JWT authentication and viewer/operator/manager/admin role-based access control.
- Human approvals for sensitive agent and workflow actions.
- Idempotency keys, optimistic ticket versions, and persistent audit events.
- Trace IDs on every request, persisted workflow/agent/LLM spans, structured JSON logs, latency, token, and cost fields.
- Golden-dataset evaluation for ticket routing, priority, schema validity and latency, plus a risk package evaluation that runs the real pipeline over 43 cases.
- Risk review with four-role RBAC, LangGraph decision packages, multi-reviewer assessments, separation of duties checks, and retrieval of similar past decisions.
- Alembic migrations, separate demo seeding, development and production Docker Compose profiles.
- GitHub Actions for linting, tests/coverage, evaluation, frontend build, migrations, and container configuration.

## Optional n8n integration

The [`n8n/`](n8n/) directory contains a standalone Docker Compose file and example workflow definitions for connecting this platform to n8n, a self-hosted workflow automation tool. It is an optional local integration example and is not required to run the main platform.

## Architecture

```mermaid
flowchart LR
    UI[React operations dashboard] -->|JWT + trace ID| API[FastAPI API]
    API --> AUTH[RBAC and governance]
    API --> AGENT[LangGraph ticket agent]
    AGENT --> KB[search_knowledge_base]
    AGENT --> HISTORY[get_customer_history]
    AGENT --> LLM[Pydantic-validated LLM analysis]
    AGENT --> APPROVAL[update_ticket approval request]
    API --> ENGINE[Idempotent workflow engine]
    ENGINE --> APPROVAL
    API --> RISK[LangGraph risk package engine]
    RISK --> BESTPRACTICE[Best practice search, pgvector on PostgreSQL]
    RISK --> SIMILAR[Similar past decisions, local embeddings in Python]
    RISK --> PERSPECTIVES[Security, compliance and business perspectives]
    API --> HUMANGATE[Decision endpoint, manager or admin with two reviews]
    API --> DB[(PostgreSQL + pgvector)]
    AGENT --> DB
    ENGINE --> DB
    RISK --> DB
    DB --> TRACE[Audit events and execution traces]
    TRACE --> UI
```

## Five-Minute Quick Start

Requirements: Docker Desktop and Docker Compose.

```bash
git clone https://github.com/RidhanPar/ai-ops-workflow-automation-platform.git
cd ai-ops-workflow-automation-platform
cp .env.example .env
docker compose up --build
```

The startup command inside the container runs `alembic upgrade head` and `seed_demo.py` automatically before the API starts, so no separate migration or seeding step is needed. Demo seeding is controlled by `DEMO_SEED_ENABLED=true` in `.env.example`.

Open:

- Dashboard: `http://localhost:5173`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Demo users:

| Username | Password | Role |
|---|---|---|
| `viewer` | `viewer-demo` | Read-only |
| `operator` | `operator-demo` | Analyze tickets and run workflows |
| `manager` | `manager-demo` | Review approvals and create workflows |
| `admin` | `admin-demo` | Full access |

Do not use demo credentials or the example JWT secret outside local development.

## Workflow Automation Engine

The automation engine lives in [`backend/app/services/workflows.py`](backend/app/services/workflows.py). It is a custom rule-based engine written in Python, inspired by event-driven trigger and action workflow concepts but not built on any external workflow tool.

Each workflow rule has a `trigger` (a set of ticket attributes to match, including derived `sla_status`) and an ordered list of `actions`. When a ticket matches a rule's trigger, the engine runs its actions in order:

| Action | Effect |
|---|---|
| `assign_team` | Assigns the ticket to the least-loaded agent on a team |
| `set_priority` | Sets the ticket priority |
| `escalate` | Queues a sensitive escalation as an approval request rather than escalating directly |
| `approval_required` | Flags the ticket for human approval |
| `notify` | Records a notification for a target audience |
| `mark_in_progress` | Moves the ticket to `in_progress` |

Every run is idempotent: an `idempotency_key` scoped per ticket and rule prevents duplicate execution on retries. Each execution records the rule name, actions taken, trace ID, and a before/after audit entry.

## LLM Provider Layer

Ticket analysis runs through a provider-agnostic layer in [`backend/app/services/llm_provider.py`](backend/app/services/llm_provider.py). Both providers implement one `LLMProvider` interface with a single `complete()` method that takes the prompt payload and returns the model's text response and token usage:

- `OpenAIProvider` calls the OpenAI Responses API with a JSON output format.
- `AnthropicProvider` calls the Anthropic Messages API (`client.messages.create`) with the same system instructions.

The active provider is chosen by the `LLM_PROVIDER` setting (`openai` or `anthropic`, default `openai`). The LangGraph agent in [`backend/app/services/agent.py`](backend/app/services/agent.py) calls through this layer rather than any single SDK, parses the response into a Pydantic `TicketAnalysis`, and records latency, token, and cost spans.

When no API key is set for the selected provider, the agent skips the LLM call and uses the deterministic keyword-rule fallback, so the platform runs end to end with no external calls and no cost.

| Setting | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | Selects `openai` or `anthropic` | `openai` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider credentials (absent means fallback) | empty |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` | Model id per provider | `gpt-4o` / `claude-sonnet-4-5` |
| `*_TIMEOUT_SECONDS`, `*_MAX_RETRIES` | Per-provider timeout and retry budget | `20`, `2` |
| `ANTHROPIC_MAX_TOKENS` | Response token cap (required by the Messages API) | `1024` |
| `*_INPUT_COST_PER_1M`, `*_OUTPUT_COST_PER_1M` | Per-provider pricing used for cost spans | provider-specific |

## Risk Review

The risk review workflow is documented in full in [`docs/RISK_REVIEW.md`](docs/RISK_REVIEW.md). A short summary follows.

Operators create risk items (title, description, business unit, owner, impact 1-5, likelihood 1-5, proposed mitigation). Posting a risk to `POST /risks/{id}/decision-package` runs a LangGraph pipeline that:

1. Checks completeness: owner present, impact and likelihood between 1 and 5, a proposed mitigation, and a description of at least 20 characters. If anything is missing it stops, returns `needs_info=true` with the gaps, and makes no LLM call. The same step checks the title and description for five known injection phrases and records matches in `safety_flags`.
2. Attaches the 3 closest best practice documents from the knowledge base (pgvector on PostgreSQL, a local vector ranking on SQLite).
3. Attaches the 3 most similar decided past risks. This step embeds text with a deterministic local hashing function and ranks every decided risk by cosine similarity in Python. It does not use pgvector.
4. Generates security, compliance and business perspectives through the provider-agnostic LLM layer, or deterministic fallback perspectives when no key is configured.
5. Sets `risk_score` (impact × likelihood) and `recommended_treatment` (the most common suggested treatment across the three perspectives).

The pipeline never decides. It saves the package, moves a draft risk to `in_review`, and never creates a decision or sets a risk to `decided`. Reviewers then submit assessments (perspective, vote, comment), and only a manager or admin can record the decision, after at least two assessments from reviewers other than themselves.

| Endpoint | Role | Effect |
|---|---|---|
| `POST /risks` | operator+ | Create risk item |
| `POST /risks/{id}/decision-package` | operator+ | Generate or idempotently retrieve a package |
| `GET /risks/{id}/latest-package` | any authenticated | Retrieve the most recent package |
| `POST /decision-packages/{id}/assessments` | any authenticated | Add a perspective assessment |
| `POST /risks/{id}/decision` | manager/admin | Record a final decision |

Risk creation, package generation, assessments and decisions each write an audit event with the actor, trace ID, resource, and state before and after.

## Observability

The platform exposes a Prometheus `/metrics` endpoint and ships a pre-built Grafana dashboard covering the four signals that matter most for an AI operations backend.

### Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `http_requests_total` | Counter | method, handler, status_code | All HTTP requests (via prometheus-fastapi-instrumentator) |
| `http_request_duration_seconds` | Histogram | method, handler | HTTP request latency with p50/p95 breakdowns |
| `agentic_requests_total` | Counter | source | Total LangGraph agent invocations by analysis path |
| `llm_call_latency_seconds` | Histogram | source | Per-LLM-call latency in seconds |
| `llm_tokens_used_total` | Counter | direction (input/output) | Cumulative token consumption |
| `human_approval_gates_triggered_total` | Counter | action_type | Agent and workflow approval gate triggers |

### Dashboard panels

![Grafana dashboard placeholder](assets/screenshots/grafana-dashboard.png)

The pre-built Grafana dashboard (`monitoring/grafana-dashboard.json`) contains five panels:

1. **HTTP Request Rate** - `rate(http_requests_total[5m])` grouped by method and handler
2. **HTTP Latency p95 and p50** - `histogram_quantile` over `http_request_duration_seconds`
3. **LLM Token Usage Rate** - stacked input/output token throughput per second
4. **Approval Gate Triggers** - bar chart of `human_approval_gates_triggered_total` by action type
5. **Cumulative Totals** - stat panel showing lifetime agent invocations, approval gates, and token totals

### Spin up the monitoring stack

Start the main platform first, then:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Open:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (login: admin / admin)

The Prometheus datasource and the AI Ops dashboard are provisioned automatically on first start. No manual import needed.

To verify metrics are being collected:

```bash
curl http://localhost:8000/metrics | grep agentic_requests_total
```

To stop the monitoring stack:

```bash
docker compose -f docker-compose.monitoring.yml down
```

## API Examples

Get a token:

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=operator&password=operator-demo"
```

Run the agent and request a governed ticket update:

```bash
curl -X POST http://localhost:8000/ai/analyze-ticket \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: reviewer-demo-001" \
  -d '{"ticket_id":2,"allow_write_tools":true}'
```

Run workflows with retry-safe idempotency:

```bash
curl -X POST http://localhost:8000/workflows/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":2,"idempotency_key":"reviewer-run-2026-001"}'
```

## Evaluation Results

Run locally:

```bash
cd backend
python evaluations/run_evaluations.py         # 5 golden tickets, writes results.json
python evaluations/eval_ai_assistant.py       # 8 synthetic assistant cases
python evaluations/eval_decision_packages.py  # 43 risk cases, writes risk_results.json
# live LLM run, needs that provider's API key, writes risk_results_<provider>.json:
python evaluations/eval_decision_packages.py --provider anthropic
```

### Ticket assistant (5 golden tickets, `backend/evaluations/results.json`)

| Quality gate | Required | Actual |
|---|---:|---:|
| Routing accuracy | >= 80% | 80% (4/5) |
| Priority accuracy | >= 80% | 100% (5/5) |
| JSON schema validity | 100% | 100% (5/5) |
| Injection check on one fixed phrase | flagged | flagged |

These gates are asserted in `backend/tests/test_evaluations.py`, which also requires the average latency per ticket to stay under 50 ms. The script prints that latency but keeps it out of `results.json`, because it changes on every run and the committed file should only change when a result changes. `results.json` also contains `fallback_available` and `estimated_cost_usd`, but both are constants in the script rather than measurements, so they are not reported here. `eval_ai_assistant.py` runs 8 further synthetic cases against the fallback rules, needs 6 to pass, and currently passes 8.

### Risk decision packages (43 cases, fallback mode, `backend/evaluations/risk_results.json`)

Every case runs through the real `generate_decision_package` on a temporary in-memory SQLite database built from the app's models and seeded with the 5 risk management knowledge documents and 12 decided past risks (`backend/evaluations/risk_past_decisions.json`). Fallback mode uses no API key, so the perspectives come from the deterministic fallback. The 43 cases are 34 complete (18 clear, 16 borderline) and 9 incomplete, with 7 injection attempts (5 in descriptions) and 10 cases that name the past decision a reviewer would cite. Labelling rules are at the top of `backend/evaluations/risk_golden_set.json`.

| Metric | Result | CI floor |
|---|---:|---:|
| Completeness precision | 100% (8/8) | >= 1.00 |
| Completeness recall | 88.9% (8/9) | >= 0.88 |
| Gap fields match the label | 100% (8/8) | >= 1.00 |
| Package schema validity | 100% (43/43) | >= 1.00 |
| Treatment agreement | 55.9% (19/34) | >= 0.55 |
| Expected past decision in the top 3 | 60% (6/10) | >= 0.60 |
| Injection attempts flagged | 42.9% (3/7) | >= 0.42 |
| Clean cases falsely flagged | 2.8% (1/36) | <= 0.03 |
| Cases that produced a decision without a human | 0 of 43 | 0 |

The floors sit at the measured values, so CI fails if any metric gets worse. What the misses show:

- **Completeness.** The one missed case has `TBD` as its mitigation, which passes the non-empty check.
- **Treatment.** The fallback chooses a treatment from the score band alone and maps every score from 6 to 11 to transfer, so it disagrees with reviewers on mid-band risks that need controls. It agrees on 8 of 18 clear cases and 11 of 16 borderline cases.
- **Past decisions.** 4 of the 10 expected precedents are not in the top 3, and one past risk about a flooded server room appears in 6 of the 10 top-3 lists. The cause has not been isolated yet.
- **Injection.** The detector looks for five fixed phrases in the title and description. It caught 3 of the 5 attempts in descriptions, missed both attempts placed in `proposed_mitigation` and `business_unit` (fields the model receives but the detector never reads), and flagged a genuine risk that uses the word "bypass".

A provider run needs that provider's API key, writes `risk_results_<provider>.json`, and leaves `risk_results.json` untouched. It fails unless every complete package used the provider's output, so a run that silently fell back cannot pass as an LLM result. Completeness, injection flags and past decision retrieval happen before the model call, so only treatment agreement and schema validity can differ between modes. No provider run has been committed yet. The provider code path is exercised in CI by `backend/tests/test_eval_decision_packages.py` with a mocked provider.

CI runs all three scripts and uploads `results.json` and `risk_results.json` as the `llm-evaluation-results` artifact. `eval_decision_packages.py` and `eval_ai_assistant.py` exit with an error when a threshold fails, which fails the build.

## Security and Governance

- Ticket and knowledge text is treated as untrusted data.
- Agent recommendations never directly perform sensitive escalations or ticket changes; they create approval requests.
- RBAC protects operational writes and approval decisions.
- Optimistic versions reject stale ticket updates.
- Idempotency keys prevent duplicate workflow execution.
- Every governed action records actor, trace ID, resource, before/after state, and timestamp.
- Secrets are environment variables and production Compose requires explicit values.

Read the threat model and operating controls in [`docs/SECURITY_AND_GOVERNANCE.md`](docs/SECURITY_AND_GOVERNANCE.md).

## Kubernetes Deployment

The [`k8s/`](k8s/) directory contains production-grade manifests for deploying to any Kubernetes cluster (schema-validated with kubeconform against Kubernetes 1.30).

Architecture: 2-10 API pods (auto-scaled by HPA) + 1 PostgreSQL StatefulSet with 10Gi persistent volume + ClusterIP Services + nginx Ingress with TLS.

| Component | Kind | Replicas | Auto-scale |
|---|---|---|---|
| API | Deployment | 3 | Yes (HPA 2-10, CPU 70%, memory 80%) |
| PostgreSQL | StatefulSet | 1 | No (stateful) |
| Ingress | Ingress | -- | nginx + TLS via cert-manager |

### Deploy

```bash
# 1. Set secrets (replace placeholders with base64-encoded values)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml      # edit first
kubectl apply -f k8s/configmap.yaml

# 2. Deploy database first
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n ai-ops --timeout=120s

# 3. Deploy API
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml
```

### Verify

```bash
kubectl get pods -n ai-ops
kubectl get hpa -n ai-ops
kubectl describe ingress -n ai-ops
```

Manifest YAML is validated on every push to `k8s/**` via the [`k8s-validate`](.github/workflows/k8s-validate.yml) GitHub Actions workflow using kubeconform against the Kubernetes 1.30 schemas.

## Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
DEMO_SEED_ENABLED=true python seed_demo.py
pytest -q
ruff check app tests evaluations seed_demo.py
```

```bash
cd frontend
npm ci
npm run build
```

## Production Deployment

Use `docker-compose.prod.yml` for a self-hosted deployment or `render.yaml` as a Render Blueprint. Production mode uses:

- `pgvector/pgvector:pg16`
- Alembic migrations before API startup
- Required database credentials, JWT secret, CORS origins, and public API URL
- Nginx-served static React build
- No automatic demo seeding

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) and [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Limits

- All ticket, risk, knowledge, and user data are fictional demo data seeded for local development. No real incidents, decisions, or customers are represented.
- Embeddings are a deterministic 64-dimension hash of word tokens, built for zero-cost reproducible demos rather than semantic quality. Knowledge base search uses pgvector on PostgreSQL, but past decision retrieval always ranks every decided risk in Python, which will not scale to a large risk register.
- The evaluation sets are small and synthetic: 5 golden tickets, 8 synthetic assistant cases, and 43 risk cases with 12 decided past risks. They catch regressions in CI but are not production benchmarks. Treatment and precedent labels in the risk set reflect a single reviewer's judgement.
- Fallback and LLM risk results go to separate files (`risk_results.json` and `risk_results_<provider>.json`) and are never mixed. Only fallback results are committed, so no LLM quality numbers are claimed.
- The prompt injection check is a list of five phrases matched in the title and description only. It records flags but blocks nothing, and the evaluation above shows what it misses.
- Human approval and separation of duties checks are demonstration controls implemented in application code. A production deployment would need to integrate with an organization's identity provider and authorization policy.
- A real deployment should use managed secrets, SSO/OIDC, external telemetry export, backups, rate limiting, and organization-specific evaluation data.

## Resume Bullet

Built a Dockerized FastAPI/PostgreSQL operations platform that routes and escalates tickets through configurable workflows and an optional LLM assistant behind a provider-agnostic layer supporting OpenAI and Anthropic; added LangGraph orchestration, a deterministic fallback, automated evaluations, trace evidence, CI tests, and approval controls.
