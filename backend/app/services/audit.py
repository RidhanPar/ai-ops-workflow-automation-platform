from sqlalchemy.orm import Session

from app.core.observability import current_trace_id
from app.models import AuditEvent


def record_audit(
    db: Session,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str | int,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        trace_id=current_trace_id(),
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        before_json=before or {},
        after_json=after or {},
    )
    db.add(event)
    return event
