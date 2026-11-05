from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.execution import PipelineRun
from backend.app.schemas.pipeline import PipelineCreate, PipelineUpdate, PipelineResponse, PipelineRunRequest
from backend.app.schemas.execution import PipelineRunResponse
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError
from backend.app.execution.runner import PipelineRunner
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])


def _run_worker_job(run_id: str):
    runner = PipelineRunner(run_id)
    runner.execute_sync()


@router.get("", response_model=List[PipelineResponse])
def list_pipelines(project_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Pipeline)
    if project_id:
        query = query.filter(Pipeline.project_id == project_id)
    return query.all()


@router.post("", response_model=PipelineResponse)
def create_pipeline(pipe_in: PipelineCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pipeline = Pipeline(
        project_id=pipe_in.project_id,
        name=pipe_in.name,
        description=pipe_in.description,
        definition_json=pipe_in.definition_json,
        status="Draft",
        current_version=1
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    # Initial version record
    ver = PipelineVersion(
        pipeline_id=pipeline.id,
        version_number=1,
        definition_json=pipe_in.definition_json,
        changelog="Initial creation"
    )
    db.add(ver)
    db.commit()

    return pipeline


@router.get("/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(pipeline_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(pipeline_id: str, pipe_in: PipelineUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipe_in.name is not None:
        pipeline.name = pipe_in.name
    if pipe_in.description is not None:
        pipeline.description = pipe_in.description
    if pipe_in.status is not None:
        pipeline.status = pipe_in.status

    if pipe_in.definition_json is not None:
        pipeline.definition_json = pipe_in.definition_json
        pipeline.current_version += 1
        # Create immutable version record
        ver = PipelineVersion(
            pipeline_id=pipeline.id,
            version_number=pipeline.current_version,
            definition_json=pipe_in.definition_json,
            changelog=f"Version {pipeline.current_version} updated"
        )
        db.add(ver)

    pipeline.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@router.delete("/{pipeline_id}")
def delete_pipeline(pipeline_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    db.delete(pipeline)
    db.commit()
    return {"message": "Pipeline deleted successfully"}


@router.post("/{pipeline_id}/validate")
def validate_pipeline(pipeline_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    definition = pipeline.definition_json or {}
    activities = definition.get("activities", [])

    if not activities:
        return {"valid": False, "message": "Pipeline contains no activities."}

    try:
        dag = PipelineDAG(activities)
        return {
            "valid": True,
            "message": f"Pipeline DAG is valid. Contains {len(activities)} activities with {len(dag.get_root_activities())} root entry points."
        }
    except DAGValidationError as e:
        return {"valid": False, "message": str(e)}


@router.post("/{pipeline_id}/run", response_model=PipelineRunResponse)
def trigger_pipeline_run(
    pipeline_id: str,
    run_req: Optional[PipelineRunRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    params = run_req.parameters if run_req else {}

    run = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Pending",
        parameters=params,
        started_at=datetime.now(timezone.utc)
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Dispatch to background task runner
    background_tasks.add_task(_run_worker_job, run.id)

    return run
