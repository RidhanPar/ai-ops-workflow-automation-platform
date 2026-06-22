# n8n Workflow Automation - Setup Guide

This directory contains two n8n workflows that integrate with the AI Operations platform backend, plus a Docker Compose file to run n8n locally.

## Prerequisites

- Docker and Docker Compose installed
- The main platform stack running: `docker compose up --build` from the project root
- A free [webhook.site](https://webhook.site) URL (used as the mock notification endpoint)

## Step 1: Get a mock endpoint URL

1. Go to https://webhook.site
2. Copy your unique URL (e.g. `https://webhook.site/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
3. Keep that tab open to see incoming requests

You will paste this URL into both workflow JSON files before importing them.

## Step 2: Update the webhook.site URL in the workflow files

Open each workflow JSON and replace every occurrence of `YOUR_UNIQUE_ID_HERE` with your actual webhook.site path segment:

```
workflows/workflow_a_ticket_event_handler.json   (2 occurrences)
workflows/workflow_b_scheduled_report_digest.json (1 occurrence)
```

For example, change:
```
https://webhook.site/YOUR_UNIQUE_ID_HERE
```
to:
```
https://webhook.site/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## Step 3: Start n8n

The n8n container joins the same Docker network as the backend so it can reach `http://aiops_backend:8000`.

Start the main stack first (if not already running):
```bash
docker compose up -d
```

Then start n8n from this directory:
```bash
docker compose -f n8n/docker-compose.n8n.yml up -d
```

n8n will be available at http://localhost:5678

On first launch, n8n prompts you to create an owner account. Fill in any email and password - this is a local dev instance only.

## Step 4: Import the workflows

1. Open http://localhost:5678 in your browser
2. Go to **Workflows** in the left sidebar
3. Click **Add Workflow**, then the three-dot menu, then **Import from File**
4. Import `workflows/workflow_a_ticket_event_handler.json`
5. Repeat for `workflows/workflow_b_scheduled_report_digest.json`
6. Open each workflow and click **Save**, then toggle it to **Active**

## Step 5: Test Workflow A

Send a test POST request to the n8n webhook trigger from your terminal:

High-priority ticket (routes to urgent notification):
```bash
curl -X POST http://localhost:5678/webhook/ticket-event \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": 42, "priority": "high", "category": "billing", "customer": "Acme Corp"}'
```

Low-priority ticket (routes to log endpoint):
```bash
curl -X POST http://localhost:5678/webhook/ticket-event \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": 99, "priority": "low", "category": "general", "customer": "Example Ltd"}'
```

Check your webhook.site page to see the routed payloads.

Alternatively, the backend's workflow engine can fire Workflow A by sending a POST to the n8n webhook URL after running `/workflows/run`.

## Step 6: Test Workflow B

Workflow B runs daily at 08:00 UTC by schedule. To test it manually:

1. Open the workflow in n8n
2. Click **Execute Workflow** (the play button in the toolbar)

n8n will call `http://aiops_backend:8000/reports/powerbi/tickets`, aggregate the data, and post the digest to your webhook.site URL.

## Node structure

### Workflow A - Ticket Event Handler

```
[Webhook POST /ticket-event]
        |
[Priority Router - IF node]
        |           |
   (true branch)  (false branch)
priority = high   priority = low
or critical       or medium
        |           |
[Notify Endpoint] [Log Endpoint]
 (URGENT alert)   (INFO log)
```

- **Webhook - Ticket Event**: Listens for POST requests at `/webhook/ticket-event`. Expects JSON body with `ticket_id`, `priority`, `category`, `customer`.
- **Priority Router**: IF node with OR combinator. True branch fires when `priority` equals `high` or `critical`. False branch fires for anything else.
- **Notify - High or Critical**: HTTP POST to webhook.site with `alert_level: URGENT` and full ticket context.
- **Log - Low or Medium**: HTTP POST to the same endpoint with `log_level: INFO` for queue processing records.

### Workflow B - Scheduled Report Digest

```
[Schedule Trigger - daily 08:00 UTC]
        |
[Fetch Ticket Report - GET /reports/powerbi/tickets]
        |
[Build Digest Summary - Code node]
        |
[Post Digest to Endpoint - HTTP POST]
```

- **Schedule - Daily 08:00**: Cron trigger `0 8 * * *`. Fires once per day at 08:00 UTC.
- **Fetch Ticket Report**: HTTP GET to `http://aiops_backend:8000/reports/powerbi/tickets`. Returns the full ticket dataset.
- **Build Digest Summary**: JavaScript code node. Aggregates tickets by priority, status, and category. Computes SLA breach count and risk count. Produces a summary JSON with an alert message.
- **Post Digest to Endpoint**: HTTP POST to webhook.site with the complete digest payload and `X-Report-Source: aiops-n8n-digest` header.

## Connecting Workflow A to the backend

To fire Workflow A automatically when a ticket triggers the workflow engine, the backend's `services/workflows.py` notify action can POST to the n8n webhook URL. The webhook URL when running locally is:

```
http://localhost:5678/webhook/ticket-event
```

From inside another Docker container on the same network, use:

```
http://aiops_n8n:5678/webhook/ticket-event
```

## Stopping n8n

```bash
docker compose -f n8n/docker-compose.n8n.yml down
```

To remove the persistent n8n data volume as well:
```bash
docker compose -f n8n/docker-compose.n8n.yml down -v
```
