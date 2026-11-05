from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.core.database import get_db
from backend.app.models.trigger import Trigger, TriggerRun
from backend.app.models.pipeline import Pipeline
from backend.app.schemas.trigger import (
    TriggerCreate,
    TriggerUpdate,
    TriggerResponse,
    TriggerRunResponse
)
from backend.app.services.trigger_service import TriggerService
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/triggers", tags=["Triggers & Scheduling"])


@router.get("", response_model=List[TriggerResponse])
def list_triggers(
    pipeline_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists triggers with optional filtering by pipeline, type, or active status."""
    query = db.query(Trigger)
    if pipeline_id:
        query = query.filter(
            (Trigger.pipeline_id == pipeline_id) |
            (Trigger.pipelines_to_run.cast(str).contains(pipeline_id))
        )
    if trigger_type:
        query = query.filter(Trigger.trigger_type == trigger_type.lower())
    if is_active is not None:
        query = query.filter(Trigger.is_active == is_active)
    return query.order_by(Trigger.name.asc()).all()


@router.get("/runs/all", response_model=List[TriggerRunResponse])
def list_all_trigger_runs(
    trigger_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns execution history across all triggers with optional status and trigger filtering."""
    query = db.query(TriggerRun)
    if trigger_id:
        query = query.filter(TriggerRun.trigger_id == trigger_id)
    if status:
        query = query.filter(TriggerRun.run_status == status)
    return query.order_by(TriggerRun.fired_at.desc()).limit(limit).all()


@router.get("/{trigger_id}", response_model=TriggerResponse)
def get_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full configuration and runtime state for a single trigger."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return trigger


@router.post("", response_model=TriggerResponse)
def create_trigger(
    trigger_in: TriggerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new trigger supporting Schedule, Tumbling Window, Storage Events, Pipeline Dependency, or Manual."""
    try:
        trigger = TriggerService.create_trigger(db, trigger_in)
        return trigger
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create trigger: {str(e)}")


@router.put("/{trigger_id}", response_model=TriggerResponse)
def update_trigger(
    trigger_id: str,
    trigger_in: TriggerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates trigger settings, recalculating schedules and validating dependencies."""
    try:
        return TriggerService.update_trigger(db, trigger_id, trigger_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update trigger: {str(e)}")


@router.delete("/{trigger_id}")
def delete_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a trigger and its historical runs."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    db.delete(trigger)
    db.commit()
    return {"message": "Trigger deleted successfully"}


@router.post("/{trigger_id}/activate", response_model=TriggerResponse)
def activate_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Activates an existing trigger and schedules its next fire timestamp."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.is_active = True
    ttype = trigger.trigger_type.lower()
    if ttype in ("cron", "schedule"):
        trigger.next_fire_time = TriggerService.calculate_next_schedule_fire(
            ttype, trigger.cron_expression, trigger.schedule_config
        )
    elif ttype == "tumbling_window":
        curr_w_start = (trigger.window_state or {}).get("current_window_start")
        _, _, fire_due = TriggerService.calculate_tumbling_window_bounds(trigger.tumbling_window_config, curr_w_start)
        trigger.next_fire_time = fire_due

    trigger.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(trigger)
    return trigger


@router.post("/{trigger_id}/deactivate", response_model=TriggerResponse)
def deactivate_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivates a trigger, clearing next fire time."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.is_active = False
    trigger.next_fire_time = None
    trigger.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(trigger)
    return trigger


@router.post("/{trigger_id}/fire-now")
def fire_trigger_now(
    trigger_id: str,
    override_parameters: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Triggers immediate on-demand execution of all target pipelines."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    try:
        tr_run = TriggerService.fire_trigger_now(
            db,
            trigger,
            event_payload={"invokedBy": current_user.email if hasattr(current_user, "email") else "User", "mode": "ManualTriggerFire"},
            override_parameters=override_parameters
        )

        primary_run_id = None
        if tr_run.triggered_pipeline_runs:
            primary_run_id = tr_run.triggered_pipeline_runs[0].get("pipeline_run_id")

        return {
            "message": "Trigger dispatched",
            "trigger_run_id": tr_run.id,
            "run_id": primary_run_id,
            "status": tr_run.run_status,
            "triggered_pipeline_runs": tr_run.triggered_pipeline_runs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fire trigger: {str(e)}")


@router.get("/{trigger_id}/runs", response_model=List[TriggerRunResponse])
def get_trigger_run_history(
    trigger_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves execution history and dispatched pipeline runs for a specific trigger."""
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    runs = db.query(TriggerRun).filter(
        TriggerRun.trigger_id == trigger_id
    ).order_by(TriggerRun.fired_at.desc()).limit(limit).all()
    return runs


@router.post("/validate-dependency-cycle")
def validate_dependency_cycle(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Validates that a proposed upstream -> downstream pipeline dependency graph has no circular loops."""
    upstream_id = payload.get("upstream_pipeline_id")
    downstream_ids = payload.get("downstream_pipeline_ids", [])
    current_trigger_id = payload.get("trigger_id")

    if not upstream_id or not downstream_ids:
        raise HTTPException(status_code=400, detail="Must supply upstream_pipeline_id and downstream_pipeline_ids")

    try:
        TriggerService.detect_circular_dependency(db, current_trigger_id, upstream_id, downstream_ids)
        return {"valid": True, "message": "No circular dependency detected"}
    except ValueError as e:
        return {"valid": False, "error": str(e)}
