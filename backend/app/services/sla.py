from datetime import datetime, timezone
from app.models import Ticket


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_sla_status(ticket: Ticket) -> str:
    now = utc_now_naive()
    if ticket.resolved_at and ticket.resolved_at <= ticket.sla_due_at:
        return "met"
    if ticket.resolved_at and ticket.resolved_at > ticket.sla_due_at:
        return "breached_resolved"
    if now > ticket.sla_due_at:
        return "breached"
    hours_left = (ticket.sla_due_at - now).total_seconds() / 3600
    if hours_left <= 4:
        return "at_risk"
    return "on_track"


def is_sla_at_risk(ticket: Ticket) -> bool:
    return get_sla_status(ticket) == "at_risk"
