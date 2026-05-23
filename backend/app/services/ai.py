import json
from openai import OpenAI
from app.core.config import get_settings

settings = get_settings()

SYSTEM_INSTRUCTIONS = """
You are an operations support analyst assistant.
Analyze support tickets and return compact JSON with these keys:
summary, category, recommended_priority, recommended_team, next_action, confidence.
Priority must be one of: low, medium, high, critical.
Recommended team must be one of: Billing Ops, Technical Support, Policy Ops, Workforce Desk, Escalations Desk, General Support.
"""


def fallback_ticket_analysis(title: str, description: str, channel: str = "email") -> dict:
    text = f"{title} {description}".lower()
    priority = "medium"
    category = "general"
    team = "General Support"

    if any(word in text for word in ["payment", "invoice", "refund", "charge", "billing"]):
        category = "billing"
        team = "Billing Ops"
    if any(word in text for word in ["login", "bug", "error", "api", "system", "failed"]):
        category = "technical"
        team = "Technical Support"
    if any(word in text for word in ["policy", "appeal", "blocked", "restricted", "compliance"]):
        category = "policy"
        team = "Policy Ops"
    if any(word in text for word in ["urgent", "critical", "blocked", "outage", "cannot work"]):
        priority = "critical"
        team = "Escalations Desk"
    elif any(word in text for word in ["sla", "delay", "waiting", "escalate"]):
        priority = "high"

    return {
        "summary": f"Ticket about {category} issue raised via {channel}. Review customer context, validate impact, and act before SLA risk increases.",
        "category": category,
        "recommended_priority": priority,
        "recommended_team": team,
        "next_action": "Check the knowledge base, verify account/ticket history, assign the right owner, and update the customer with the next step.",
        "confidence": 0.72,
        "source": "local_fallback_rules"
    }


def analyze_ticket(title: str, description: str, customer: str = "Unknown", channel: str = "email") -> dict:
    if not settings.openai_api_key:
        return fallback_ticket_analysis(title, description, channel)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = {
        "title": title,
        "description": description,
        "customer": customer,
        "channel": channel,
    }

    try:
        response = client.responses.create(
            model=settings.openai_model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=json.dumps(prompt),
        )
        content = response.output_text
        parsed = json.loads(content)
        parsed["source"] = "openai_responses_api"
        return parsed
    except Exception:
        return fallback_ticket_analysis(title, description, channel)
