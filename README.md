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
- Golden-dataset evaluation for routing, priority, schema, prompt injection, fallback, latency, and cost.
- Risk review with four-role RBAC, LangGraph decision packages, multi-reviewer assessments, separation-of-duties enforcement, and pgvector similar-case retrieval.
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
    RISK --> PERSPECTIVES[Three-area perspective generation]
    RISK --> SIMILAR[pgvector similar-case retrieval]
    RISK --> HUMANGATE[Human decision gate - RBAC SoD]
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

Operators create risk items (title, description, business unit, owner, impact 1-5, likelihood 1-5, proposed mitigation). Posting a risk to `POST /risks/{id}/decision-package` triggers a LangGraph pipeline that:

1. Checks completeness: a package that would be generated without a mitigation plan, a meaningful description, or an owner is returned as `needs_info=true` with a list of gaps rather than calling the LLM.
2. Generates three perspective analyses (security, compliance, business) via the provider-agnostic LLM layer. When no key is configured it uses the deterministic fallback.
3. Retrieves similar past decisions via pgvector cosine search ranked by similarity score.
4. Sets `needs_human_decision=true` unconditionally. The AI never sets a decision.

Reviewers submit assessments (perspective, vote, comment) against the package. A manager or admin can then make a final decision, subject to separation-of-duties enforcement: at least two qualifying assessments from reviewers other than the deciding manager are required.

| Endpoint | Role | Effect |
|---|---|---|
| `POST /risks` | operator+ | Create risk item |
| `POST /risks/{id}/decision-package` | operator+ | Generate or idempotently retrieve a package |
| `GET /risks/{id}/latest-package` | any authenticated | Retrieve the most recent package |
| `POST /decision-packages/{id}/assessments` | any authenticated | Add a perspective assessment |
| `POST /risks/{id}/decision` | manager/admin | Record a final decision |

All create and decision events are written to the audit log with actor, trace ID, resource, and version.

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
python evaluations/run_evaluations.py        # ticket assistant (8 cases)
python evaluations/eval_ai_assistant.py      # ticket assistant offline (8 cases)
python evaluations/eval_decision_packages.py # risk packages fallback (25 cases)
# with a live provider (writes a separate file, never mixed with fallback):
python evaluations/eval_decision_packages.py --provider openai
```

### Ticket assistant (8 cases, fallback mode, `backend/evaluations/results.json`)

| Quality gate | Required | Actual |
|---|---:|---:|
| Routing accuracy | >= 80% | 80% |
| Priority accuracy | >= 80% | 100% |
| JSON schema validity | 100% | 100% |
| Prompt-injection detection | Pass | Pass |
| Fallback availability | Pass | Pass |
| Local average latency | < 50 ms | < 1 ms |
| Local evaluation cost | USD 0 | USD 0 |

### Risk decision packages (25 cases, fallback mode, `backend/evaluations/risk_results.json`)

| Quality gate | Threshold | Actual (fallback, 25 cases) |
|---|---:|---:|
| Completeness precision | >= 80% | 100% |
| Completeness recall | >= 80% | 100% |
| Package schema validity | >= 95% | 100% |
| Prompt-injection flagging | 100% | 100% (3/3 cases) |
| No auto-decision | Must pass | Pass |
| Past-decision hit rate top-3 | >= 0% | 0% (fallback has no DB) |

The past-decision hit rate is 0% in fallback mode because the offline evaluator does not connect to a database. A live LLM run (`--provider openai`) writes results to `risk_results_openai.json` and is never mixed with fallback numbers.

CI uploads both results files as the `llm-evaluation-results` artifact and fails the build if any threshold is breached.

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
- The local deterministic embedding is designed for zero-cost reproducibility, not semantic-search benchmark performance. pgvector similarity scores in the demo reflect embedding distances between synthetic strings.
- Evaluation golden sets are small (8 cases for the ticket assistant, 25 for risk packages) and cover synthetic scenarios. They establish a CI baseline but do not constitute production quality benchmarks.
- Fallback and LLM evaluation results are always reported in separate files (`results.json` / `risk_results.json` vs `risk_results_openai.json`) and are never mixed, because LLM-generated perspectives vary with model version and prompt.
- The past-decision hit rate in the risk evaluation is 0% in fallback mode. The offline evaluator does not connect to a database, so no similar past decisions are retrieved. A live run against a seeded database would produce non-zero hit rates.
- Human approval and separation-of-duties checks are demonstration controls implemented in application code. A production deployment would need to integrate with an organization's identity provider and authorization policy.
- A real deployment should use managed secrets, SSO/OIDC, external telemetry export, backups, rate limiting, and organization-specific evaluation data.

## Resume Bullet

Built a Dockerized FastAPI/PostgreSQL operations platform that routes and escalates tickets through configurable workflows and an optional LLM assistant behind a provider-agnostic layer supporting OpenAI and Anthropic; added LangGraph orchestration, a deterministic fallback, automated evaluations, trace evidence, CI tests, and approval controls.
