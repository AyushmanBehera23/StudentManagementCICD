import logging

from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("audit")


def record(
    db: Session, *, actor: str, action: str, resource: str, outcome: str, detail: str = ""
) -> None:
    """Persist an audit row immediately (own commit) so denials survive the error response."""
    db.add(
        models.AuditLog(
            actor=actor, action=action, resource=resource, outcome=outcome, detail=detail[:500]
        )
    )
    db.commit()
    log.info(
        "audit",
        extra={"actor": actor, "action": action, "resource": resource, "outcome": outcome},
    )
