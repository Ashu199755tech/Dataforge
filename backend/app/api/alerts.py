from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.schemas.alert import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertEventResponse
)
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.monitoring.alert_engine import AlertEngine

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])


@router.get("/rules", response_model=List[AlertRuleResponse])
def list_alert_rules(
    pipeline_id: Optional[str] = None,
    target_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AlertRule).order_by(AlertRule.created_at.desc())
    if pipeline_id:
        query = query.filter((AlertRule.pipeline_id == pipeline_id) | (AlertRule.target_type == "Global"))
    if target_type:
        query = query.filter(AlertRule.target_type == target_type)
    return query.all()


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
def create_alert_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rule = AlertRule(
        name=payload.name,
        description=payload.description,
        target_type=payload.target_type,
        pipeline_id=payload.pipeline_id,
        condition_type=payload.condition_type,
        threshold_value=payload.threshold_value,
        action_type=payload.action_type,
        action_config=payload.action_config,
        is_enabled=payload.is_enabled
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
def get_alert_rule(rule_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(
    rule_id: str,
    payload: AlertRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    data = payload.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(rule, k, v)

    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_alert_rule(rule_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Alert rule deleted successfully", "id": rule_id}


@router.get("/events", response_model=List[AlertEventResponse])
def list_alert_events(
    pipeline_run_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AlertEvent).order_by(AlertEvent.created_at.desc())
    if pipeline_run_id:
        query = query.filter(AlertEvent.pipeline_run_id == pipeline_run_id)
    if severity:
        query = query.filter(AlertEvent.severity == severity)
    return query.limit(limit).all()


@router.post("/rules/{rule_id}/test", response_model=AlertEventResponse)
def test_alert_rule(rule_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Simulates triggering the alert rule to test webhook/slack/log connectivity."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    event = AlertEvent(
        alert_rule_id=rule.id,
        title=f"Test Alert: {rule.name}",
        severity="Info",
        message=f"Manual test notification triggered for alert rule '{rule.name}' ({rule.condition_type}).",
        payload={"is_test": True, "condition": rule.condition_type, "action": rule.action_type},
        status="Triggered"
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    AlertEngine.dispatch_notification(event, rule, db)
    return event
