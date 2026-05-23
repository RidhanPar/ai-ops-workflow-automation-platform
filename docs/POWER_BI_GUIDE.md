# Power BI Guide

## Option 1: Import CSV

1. Open Power BI Desktop
2. Select Get Data
3. Choose Text/CSV
4. Import `data/sample_tickets.csv`
5. Build visuals for:
   - Tickets by status
   - SLA status by priority
   - Backlog by team
   - Resolved vs open tickets
   - Escalation count

## Option 2: Use Web API

1. Start the backend with Docker Compose
2. Open Power BI Desktop
3. Select Get Data → Web
4. Use this endpoint:

```text
http://localhost:8000/reports/powerbi/tickets
```

5. Convert the JSON result into a table
6. Expand records and load the dataset

## Suggested Power BI Measures

```DAX
Total Tickets = COUNTROWS(Tickets)
Open Tickets = CALCULATE(COUNTROWS(Tickets), Tickets[status] <> "resolved")
Escalated Tickets = CALCULATE(COUNTROWS(Tickets), Tickets[escalated] = TRUE())
SLA Breached = CALCULATE(COUNTROWS(Tickets), Tickets[sla_status] IN {"breached", "breached_resolved"})
SLA At Risk = CALCULATE(COUNTROWS(Tickets), Tickets[sla_status] = "at_risk")
```

## Dashboard Pages To Build

1. Executive Summary
2. SLA and Backlog Risk
3. Workforce Productivity
4. Ticket Category Analysis
5. Escalation Monitoring
