# Interview Talk Track

## 30-Second Explanation

I built an operations automation platform that combines deterministic workflow rules with a governed LangGraph ticket agent. The agent retrieves relevant knowledge, checks customer history, produces a Pydantic-validated recommendation, and creates an approval request before any sensitive ticket change. The platform records trace IDs, audit events, latency, token usage, and estimated cost.

## What Is Actually Running

- FastAPI API, React dashboard, PostgreSQL/pgvector deployment, and JWT role controls.
- LangGraph nodes that explicitly invoke knowledge-search and customer-history tools.
- Optional OpenAI Responses API analysis when a key is configured.
- Deterministic local fallback so the demo and evaluations remain reproducible.
- Approval-gated workflow actions, idempotency keys, audit events, and execution traces.

## Important Distinction

The current model produces structured recommendations; it does not independently choose arbitrary functions. Tool execution is explicit in the LangGraph workflow, and sensitive writes create approval requests. This makes the behavior easier to test and defend than unrestricted autonomous execution.

## Design Decisions To Explain

- Why untrusted ticket text is separated from system instructions.
- Why local fallback behavior is labeled and evaluated separately from provider behavior.
- Why pgvector is used in PostgreSQL while SQLite tests use deterministic local vectors.
- Why write-capable actions require approval, idempotency, and optimistic versions.
- Why traces include source, tools used, latency, token usage, and estimated cost.

## Honest Limits

The deployed data and knowledge corpus are fictional. A real implementation would replace demo users with SSO/OIDC, use organization-specific evaluations, export telemetry, add rate limiting and backups, and adapt approval policy to the business.
