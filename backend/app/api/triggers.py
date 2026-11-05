from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.pipeline import Trigger, Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.schemas.trigger import TriggerCreate, TriggerUpdate, TriggerResponse
from backend.app.orchestration.scheduler import scheduler
from backend.app.execution.runner import PipelineRunner
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/triggers", tags=["Triggers & Scheduling"])


@router.get("", response_model=List[TriggerResponse])
def list_triggers(
    pipeline_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Trigger)
    if pipeline_id:
        query = query.filter(Trigger.pipeline_id == pipeline_id)
    return query.all()


@router.post("", response_model=TriggerResponse)
def create_trigger(
    trigger_in: TriggerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == trigger_in.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    next_fire = None
    if trigger_in.cron_expression and trigger_in.is_active:
        try:
            next_fire = scheduler.calculate_next_fire(trigger_in.cron_expression)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {str(e)}")

    trigger = Trigger(
        pipeline_id=trigger_in.pipeline_id,
        name=trigger_in.name,
        trigger_type=trigger_in.trigger_type,
        cron_expression=trigger_in.cron_expression,
        is_active=trigger_in.is_active,
        parameters=trigger_in.parameters,
        next_fire_time=next_fire
    )
    db.add(trigger)
    db.commit()
    db.refresh(trigger)
    return trigger


@router.put("/{trigger_id}", response_model=TriggerResponse)
def update_trigger(
    trigger_id: str,
    trigger_in: TriggerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    if trigger_in.name is not None:
        trigger.name = trigger_in.name
    if trigger_in.cron_expression is not None:
        trigger.cron_expression = trigger_in.cron_expression
        if trigger.is_active:
            trigger.next_fire_time = scheduler.calculate_next_fire(trigger_in.cron_expression)
    if trigger_in.is_active is not None:
        trigger.is_active = trigger_in.is_active
        if trigger.is_active and trigger.cron_expression:
            trigger.next_fire_time = scheduler.calculate_next_fire(trigger.cron_expression)
        else:
            trigger.next_fire_time = None
    if trigger_in.parameters is not None:
        trigger.parameters = trigger_in.parameters

    db.commit()
    db.refresh(trigger)
    return trigger


@router.delete("/{trigger_id}")
def delete_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    trigger.is_active = True
    if trigger.cron_expression:
        trigger.next_fire_time = scheduler.calculate_next_fire(trigger.cron_expression)
    db.commit()
    db.refresh(trigger)
    return trigger


@router.post("/{trigger_id}/deactivate", response_model=TriggerResponse)
def deactivate_trigger(
    trigger_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    trigger.is_active = False
    trigger.next_fire_time = None
    db.commit()
    db.refresh(trigger)
    return trigger


@router.post("/{trigger_id}/fire-now")
def fire_trigger_now(
    trigger_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    run = PipelineRun(
        pipeline_id=trigger.pipeline_id,
        run_type="Manual:TriggerFire",
        status="Pending",
        parameters=trigger.parameters or {},
        started_at=datetime.now(timezone.utc)
    )
    db.add(run)
    trigger.last_fired_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(lambda: PipelineRunner(run.id).execute_sync())
    return {"message": "Trigger dispatched", "run_id": run.id}
