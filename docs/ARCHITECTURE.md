# Architecture

## System Overview

The platform has four core layers:

1. React dashboard for operations monitoring and workflow control
2. FastAPI backend for ticket, KPI, workflow, AI, and report APIs
3. PostgreSQL database for tickets, agents, workflow rules, executions, and notifications
4. Power BI/reporting layer using CSV and web API exports

## Main Data Flow

1. Ticket enters the system through API or demo seed data
2. SLA status is calculated based on `created_at`, `sla_due_at`, `resolved_at`, and status
3. Workflow rules check trigger conditions such as priority, category, status, or SLA risk
4. Matching workflows perform actions such as escalation, assignment, notification, or approval flagging
5. AI assistant summarizes ticket context and recommends category, priority, team, and next action
6. Dashboard displays operational KPIs, backlog, ticket trend, and workforce metrics
7. Power BI connects to `/reports/powerbi/tickets` or imports `/data/sample_tickets.csv`

## Workflow Rule Format

Example:

```json
{
  "name": "Critical Ticket Escalation",
  "trigger": { "priority": "critical" },
  "actions": [
    { "type": "escalate" },
    { "type": "assign_team", "team": "Escalations Desk" },
    { "type": "notify", "audience": "operations_lead" }
  ]
}
```

## AI Assistant Design

The assistant uses OpenAI when `OPENAI_API_KEY` is configured. If the key is missing or the API call fails, a local rule-based fallback still returns a useful summary and recommendation. This makes the project easy to demo without external cost.

## Production Improvements To Add Later

- Authentication and role-based access
- Real-time WebSocket updates
- Drag-and-drop workflow builder
- Advanced forecasting for SLA breach prediction
- Vector search over internal knowledge base
- CI/CD pipeline
- Unit and integration tests
- Cloud deployment with managed PostgreSQL
