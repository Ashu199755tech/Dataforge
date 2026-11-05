from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend.app.models.data_quality import AuditLog


def record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None
) -> AuditLog:
    """
    Centralized enterprise audit logging.
    Records security, modification, deployment, and configuration actions.
    """
    audit = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
