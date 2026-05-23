# AI Operations & Workflow Automation Platform

A portfolio-ready enterprise MVP for support operations teams. It combines SLA monitoring, ticket management, workflow automation, AI ticket assistance, KPI dashboards, and Power BI-ready reporting exports.

## Why this project is strong for Latvia job applications

This project matches roles such as Data Analyst, BI Analyst, Operations Analyst, Workforce Management Analyst, Real-Time Analyst, Process Improvement Specialist, Business Analyst, Junior Data Scientist, and AI Automation Specialist.

It demonstrates:

- Support operations domain knowledge
- SLA and backlog monitoring
- Ticket routing and escalation logic
- AI-assisted summarization and operational recommendations
- Workflow automation inspired by n8n concepts
- KPI dashboarding and reporting
- PostgreSQL data modelling
- Docker-based deployment
- Power BI export readiness

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, PostgreSQL
- Frontend: React, Vite, Recharts
- AI: OpenAI Python SDK using the Responses API
- DevOps: Docker, Docker Compose
- BI: CSV export files and API endpoints for Power BI

## Main Features

### Ticket Management

- Create, update, and view support tickets
- Priority, channel, status, owner, customer, SLA due time
- SLA breach risk detection
- Backlog visibility

### AI Ticket Assistant

- Summarizes ticket content
- Suggests priority, category, routing team, and next action
- Provides a fallback rules-based response when no API key is configured

### Workflow Automation

- Rule-based workflow engine inspired by n8n-style automation
- Triggers based on priority, status, SLA risk, channel, and category
- Actions such as assign team, escalate, send notification, and mark approval required

### Operations Dashboard

- Real-time KPI cards
- Ticket trend chart
- SLA performance view
- Backlog by status and priority
- Workforce productivity table

### Power BI Reporting

- CSV export files in `/data`
- Backend API endpoint: `/reports/powerbi/tickets`
- Can be connected to Power BI using Web connector or CSV import

