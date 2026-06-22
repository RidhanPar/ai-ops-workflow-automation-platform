# Security and Governance

## Threat Model

The platform assumes ticket text, customer content, and retrieved documents may be malicious or incorrect. It also assumes workflow retries, concurrent edits, compromised low-privilege accounts, and LLM/provider failures are normal operating conditions.

## Implemented Controls

- JWT authentication with viewer, operator, manager, and admin roles.
- Approval gates for sensitive escalations and agent-requested changes.
- Prompt-injection indicator detection and explicit untrusted-data instructions.
- Pydantic output validation and allow-listed categories, priorities, and teams.
- Idempotency keys for workflow runs and optimistic ticket versions for concurrent writes.
- Audit events with actor, trace ID, resource, and before/after state.
- Structured logs and persisted traces for workflow, agent, and LLM activity.
- Optional OpenTelemetry OTLP export to Arize Phoenix or another compatible observability backend.
- Environment-based secrets and required production Compose variables.

## Production Requirements

- Replace demo users with SSO/OIDC and organization-managed roles.
- Store secrets in a managed secret service and rotate them.
- Add API rate limiting, network controls, database encryption/backups, and retention policy.
- Export OpenTelemetry-compatible logs/traces to a managed backend.
- Review and approve the knowledge corpus before indexing.
- Run organization-specific red-team and regression evaluations before prompt/model changes.
