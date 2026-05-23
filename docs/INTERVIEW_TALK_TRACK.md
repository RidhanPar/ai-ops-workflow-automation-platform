# Interview Talk Track

## 30-second explanation

I built an AI Operations and Workflow Automation Platform for support operations teams. It monitors SLA risk, ticket backlog, workforce productivity, and operational KPIs. It also includes an n8n-inspired workflow engine that can automatically route, escalate, notify, and mark tickets for approval. I integrated an AI ticket assistant using OpenAI APIs to summarize issues and recommend next actions.

## Why I built it

I wanted to show a project that connects data analytics, support operations, process improvement, workflow automation, and AI assistance. It is directly relevant for operations analyst, WFM, real-time analyst, BI analyst, and AI automation roles.

## Best technical points to explain

- FastAPI backend with clean routers and service layers
- PostgreSQL schema for tickets, agents, workflow rules, workflow executions, and notifications
- SLA status calculation using due time and resolution time
- Workflow engine using trigger-action rules
- AI assistant with OpenAI integration and local fallback logic
- React dashboard with KPI cards and charts
- Power BI-ready API and CSV exports
- Docker Compose setup for full local deployment

## Best business points to explain

- Reduces manual ticket triage
- Improves SLA visibility
- Helps operations teams identify backlog risk earlier
- Supports data-driven workload decisions
- Converts support data into dashboard and BI insights
