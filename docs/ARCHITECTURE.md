# Architecture

## Request Path

Every HTTP request receives an `X-Trace-ID`. JWT authentication resolves the actor and RBAC role before protected endpoints execute. Operational changes write an audit event in the same database transaction.

## Agent Path

1. LangGraph routes the ticket through context gathering and reasoning nodes.
2. `search_knowledge_base` retrieves relevant guidance using PostgreSQL pgvector in production or deterministic local vectors in demo/test mode.
3. `get_customer_history` retrieves recent ticket context.
4. Ticket and retrieved content are treated as untrusted data; prompt-injection indicators are surfaced as safety flags.
5. OpenAI returns a Pydantic-validated structured recommendation when configured.
6. Invalid output, provider failure, and unexpected failure use separately identified fallbacks.
7. Write-enabled agent runs create a human approval request instead of directly updating the ticket.
8. LLM source, tools, knowledge sources, token counts, cost estimate, latency, and trace ID are persisted.
9. OpenTelemetry spans can be exported through OTLP to Arize Phoenix or another compatible backend.

## Workflow Path

Workflow rules use JSON triggers and actions. Every run requires an idempotency key. Sensitive escalation actions create approval requests; non-sensitive routing and notification actions execute transactionally. Each execution records its trace and audit event.

## Data Model

- Operational: tickets, agents, workflow rules, executions, notifications.
- Agent/RAG: knowledge documents and vector embeddings.
- Governance: users, approval requests, audit events.
- Observability: trace spans with latency, token, cost, and error fields.

## Deployment Boundaries

The production Compose profile runs PostgreSQL/pgvector, FastAPI workers, and an Nginx-served React build. Alembic owns schema creation and demo seeding is a separate, opt-in command.
