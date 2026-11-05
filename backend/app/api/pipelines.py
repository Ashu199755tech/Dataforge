from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.execution import PipelineRun
from backend.app.schemas.pipeline import (
    PipelineCreate,
    PipelineUpdate,
    PipelineResponse,
    PipelineRunRequest,
    PipelineVersionResponse
)
from backend.app.schemas.security import (
    PipelinePromoteRequest,
    PipelineRollbackRequest,
    PipelineGitImportRequest
)
from backend.app.schemas.execution import PipelineRunResponse
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError
from backend.app.execution.runner import PipelineRunner
from backend.app.api.deps import get_current_user
from backend.app.core.rbac import require_role
from backend.app.core.audit import record_audit
from backend.app.models.user import User
from backend.app.orchestration.promotion import (
    promote_pipeline,
    rollback_pipeline,
    export_pipeline_for_git,
    import_pipeline_from_git
)
from backend.app.orchestration.recovery import enforce_concurrency_and_idempotency

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])


def _run_worker_job(run_id: str):
    runner = PipelineRunner(run_id)
    runner.execute_sync()


@router.get("", response_model=List[PipelineResponse])
def list_pipelines(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Viewer"]))
):
    query = db.query(Pipeline)
    if project_id:
        query = query.filter(Pipeline.project_id == project_id)
    return query.all()


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    pipe_in: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    pipeline = Pipeline(
        project_id=pipe_in.project_id,
        name=pipe_in.name,
        description=pipe_in.description,
        definition_json=pipe_in.definition_json,
        concurrency_limit=pipe_in.concurrency_limit or 5,
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
        changelog="Initial creation",
        environment_name="Dev",
        created_by_id=current_user.id
    )
    db.add(ver)
    db.commit()

    record_audit(
        db=db,
        action="PIPELINE_CREATE",
        resource_type="Pipeline",
        resource_id=pipeline.id,
        details={"name": pipeline.name, "project_id": pipeline.project_id},
        user_id=current_user.id
    )
    return pipeline


@router.get("/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Viewer"]))
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(
    pipeline_id: str,
    pipe_in: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipe_in.name is not None:
        pipeline.name = pipe_in.name
    if pipe_in.description is not None:
        pipeline.description = pipe_in.description
    if pipe_in.status is not None:
        pipeline.status = pipe_in.status
    if pipe_in.concurrency_limit is not None:
        pipeline.concurrency_limit = pipe_in.concurrency_limit

    if pipe_in.definition_json is not None:
        pipeline.definition_json = pipe_in.definition_json
        pipeline.current_version += 1
        # Create immutable version record
        ver = PipelineVersion(
            pipeline_id=pipeline.id,
            version_number=pipeline.current_version,
            definition_json=pipe_in.definition_json,
            changelog=f"Version {pipeline.current_version} updated",
            environment_name="Dev",
            created_by_id=current_user.id
        )
        db.add(ver)

    pipeline.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pipeline)

    record_audit(
        db=db,
        action="PIPELINE_UPDATE",
        resource_type="Pipeline",
        resource_id=pipeline.id,
        details={"version": pipeline.current_version},
        user_id=current_user.id
    )
    return pipeline


@router.delete("/{pipeline_id}")
def delete_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    pipe_name = pipeline.name
    db.delete(pipeline)
    db.commit()

    record_audit(
        db=db,
        action="PIPELINE_DELETE",
        resource_type="Pipeline",
        resource_id=pipeline_id,
        details={"name": pipe_name},
        user_id=current_user.id
    )
    return {"message": "Pipeline deleted successfully"}


@router.post("/{pipeline_id}/validate")
def validate_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Viewer"]))
):
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
    current_user: User = Depends(require_role(["Operator", "Contributor", "Admin"]))
):
    """
    Triggers execution with strict concurrency control and idempotency guarantees.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    params = run_req.parameters if run_req else {}
    idempotency_key = run_req.idempotency_key if run_req else None

    # Enforce concurrency limit and check idempotency duplicate window
    existing_run = enforce_concurrency_and_idempotency(pipeline, idempotency_key, db)
    if existing_run:
        # Idempotent response: return previously initiated run
        return existing_run

    run = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Pending",
        idempotency_key=idempotency_key,
        parameters=params,
        started_at=datetime.now(timezone.utc)
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    record_audit(
        db=db,
        action="PIPELINE_RUN_TRIGGER",
        resource_type="PipelineRun",
        resource_id=run.id,
        details={"pipeline_id": pipeline.id, "run_type": "Manual"},
        user_id=current_user.id
    )

    # Dispatch to background task runner
    background_tasks.add_task(_run_worker_job, run.id)
    return run


@router.get("/{pipeline_id}/versions", response_model=List[PipelineVersionResponse])
def get_pipeline_versions(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Viewer"]))
):
    """Returns immutable history of pipeline versions with changelogs and environments."""
    versions = db.query(PipelineVersion).filter(
        PipelineVersion.pipeline_id == pipeline_id
    ).order_by(PipelineVersion.version_number.desc()).all()
    return versions


@router.post("/{pipeline_id}/promote", response_model=PipelineResponse)
def promote_pipeline_endpoint(
    pipeline_id: str,
    promote_req: PipelinePromoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    """Promotes pipeline definition to target stage (Dev -> Test -> Prod) with parameter overrides."""
    try:
        promoted = promote_pipeline(
            pipeline_id=pipeline_id,
            target_environment=promote_req.target_environment,
            parameter_overrides=promote_req.parameter_overrides,
            db=db,
            user_id=current_user.id
        )
        return promoted
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/{pipeline_id}/rollback", response_model=PipelineResponse)
def rollback_pipeline_endpoint(
    pipeline_id: str,
    rollback_req: PipelineRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    """Rolls back pipeline definition to historical version snapshot."""
    try:
        rolled_back = rollback_pipeline(
            pipeline_id=pipeline_id,
            version_number=rollback_req.version_number,
            db=db,
            user_id=current_user.id
        )
        return rolled_back
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/{pipeline_id}/export-git")
def export_pipeline_git_endpoint(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Viewer"]))
):
    """Exports declarative JSON specification formatted for Git version control and CI/CD."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return export_pipeline_for_git(pipeline)


@router.post("/import-git", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def import_pipeline_git_endpoint(
    import_req: PipelineGitImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    """Imports and validates declarative JSON pipeline specification from Git repository payload."""
    try:
        pipeline = import_pipeline_from_git(
            spec=import_req.spec,
            project_id=import_req.project_id,
            db=db,
            user_id=current_user.id
        )
        return pipeline
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
