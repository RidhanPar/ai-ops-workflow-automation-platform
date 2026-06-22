# Operations Runbook

## Provider Failure

The agent retries timeout, connection, and rate-limit errors with exponential backoff. If retries fail, it returns a labeled local fallback. Search traces by `trace_id` and inspect `source` plus `error_type`.

## Invalid Model Output

Pydantic validation rejects outputs outside the allowed schema. The response is labeled `fallback_invalid_output`. Add the failure case to the golden dataset before changing prompts.

## Duplicate Workflow Request

Reuse the same idempotency key when retrying an uncertain client request. Existing executions are returned without repeating actions.

## Stale Ticket Update

HTTP 409 means another actor changed the ticket. Fetch the current ticket version, review the new state, and submit a deliberate update.

## Approval Queue

Managers and admins review pending actions through `/governance/approvals`. Approved escalations update the ticket; rejected actions remain auditable and do not change operational state.
