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

## Quick Start

### 1. Clone or unzip the project

```bash
cd ai-ops-automation-platform
cp .env.example .env
```

### 2. Optional: add OpenAI API key

Open `.env` and add:

```bash
OPENAI_API_KEY=your_api_key_here
```

Without this key, the project still works using a local fallback assistant.

### 3. Start with Docker

```bash
docker compose up --build
```

### 4. Open the apps

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

### 5. Seed demo data

When the backend starts, it automatically creates demo tickets, agents, and workflows if the database is empty.

## Useful API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | App health check |
| GET | `/tickets` | List tickets |
| POST | `/tickets` | Create a ticket |
| PATCH | `/tickets/{ticket_id}` | Update ticket |
| POST | `/ai/analyze-ticket` | AI summary and next-action recommendation |
| GET | `/kpis/overview` | Dashboard KPIs |
| GET | `/kpis/trends` | Ticket trend data |
| GET | `/workflows` | List automation workflows |
| POST | `/workflows/run` | Run automation rules manually |
| GET | `/reports/powerbi/tickets` | Power BI-ready ticket dataset |

## Portfolio Description

AI Operations & Workflow Automation Platform

Tech: Python, FastAPI, React, PostgreSQL, Docker, OpenAI API, Power BI

- Developed an AI-driven operations and workflow automation platform focused on SLA monitoring, ticket management, and process optimization within support operations environments.
- Built workflow automation modules inspired by n8n concepts to automate ticket routing, escalation handling, notifications, and approval processes.
- Integrated AI-powered ticket summarization and operational assistance using OpenAI APIs to improve issue analysis and knowledge retrieval efficiency.
- Designed interactive dashboards for monitoring KPIs, backlog trends, SLA performance, workforce productivity, and operational insights in real time.
- Implemented analytics and reporting features to support workload visibility and data-driven operational decision-making.

## Resume Version

AI Operations & Workflow Automation Platform | Python, FastAPI, React, PostgreSQL, Docker, OpenAI API, Power BI

- Built an AI-driven operations platform for SLA monitoring, ticket routing, backlog visibility, and workflow automation in support operations.
- Created FastAPI services and PostgreSQL models for tickets, agents, SLA risk, workflow rules, and operational KPI reporting.
- Integrated OpenAI-powered ticket summarization and recommendation features with a fallback rules engine for local demos.
- Designed React dashboards showing SLA performance, backlog trends, ticket volume, workload distribution, and agent productivity.
- Added Power BI-ready reporting exports to support real-time operational visibility and data-driven decision-making.

## Suggested GitHub Repository Name

`ai-ops-workflow-automation-platform`

## Suggested Live Deployment

- Frontend: Vercel or Netlify
- Backend: Render, Railway, Fly.io, or Azure App Service
- Database: Neon PostgreSQL, Supabase, Railway PostgreSQL, or Render PostgreSQL
