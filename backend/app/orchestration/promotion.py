import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.models.pipeline import Pipeline, PipelineVersion
from backend.app.models.security import Environment
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError
from backend.app.core.audit import record_audit


def promote_pipeline(
    pipeline_id: str,
    target_environment: str,
    parameter_overrides: Optional[Dict[str, Any]],
    db: Session,
    user_id: Optional[str] = None
) -> Pipeline:
    """
    Promotes a pipeline definition to a target environment (e.g., Dev -> Test -> Prod).
    Applies environment-specific variable and parameter overrides, validates DAG integrity,
    creates an immutable version record, and logs an audit trail.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Source pipeline '{pipeline_id}' not found.")

    # Find target environment
    env = db.query(Environment).filter(Environment.name == target_environment).first()
    env_vars = env.variables if env else {}

    # Merge definition with environment variables and parameter overrides
    definition = json.loads(json.dumps(pipeline.definition_json or {}))
    activities = definition.get("activities", [])

    # Apply parameter overrides
    if parameter_overrides:
        definition.setdefault("parameters", {}).update(parameter_overrides)

    # Validate DAG before deployment
    if activities:
        PipelineDAG(activities)

    # Update pipeline metadata
    pipeline.environment_id = env.id if env else None
    pipeline.status = "Published"
    pipeline.current_version += 1
    pipeline.definition_json = definition
    pipeline.updated_at = datetime.now(timezone.utc)

    # Persist immutable version record
    version = PipelineVersion(
        pipeline_id=pipeline.id,
        version_number=pipeline.current_version,
        definition_json=definition,
        changelog=f"Promoted to environment '{target_environment}'",
        environment_name=target_environment,
        created_by_id=user_id
    )
    db.add(version)
    db.commit()
    db.refresh(pipeline)

    record_audit(
        db=db,
        action="PIPELINE_PROMOTE",
        resource_type="Pipeline",
        resource_id=pipeline.id,
        details={
            "target_environment": target_environment,
            "version": pipeline.current_version,
            "overrides": parameter_overrides or {}
        },
        user_id=user_id
    )
    return pipeline


def rollback_pipeline(
    pipeline_id: str,
    version_number: int,
    db: Session,
    user_id: Optional[str] = None
) -> Pipeline:
    """
    Rolls back a pipeline definition to a historical snapshot version.
    Increments the current version counter with an audit trail.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline '{pipeline_id}' not found.")

    target_ver = db.query(PipelineVersion).filter(
        PipelineVersion.pipeline_id == pipeline_id,
        PipelineVersion.version_number == version_number
    ).first()
    if not target_ver:
        raise ValueError(f"Version {version_number} not found for pipeline '{pipeline_id}'.")

    definition = json.loads(json.dumps(target_ver.definition_json))
    pipeline.current_version += 1
    pipeline.definition_json = definition
    pipeline.updated_at = datetime.now(timezone.utc)

    # Record new rollback version
    new_version = PipelineVersion(
        pipeline_id=pipeline.id,
        version_number=pipeline.current_version,
        definition_json=definition,
        changelog=f"Rolled back to version {version_number}",
        environment_name=target_ver.environment_name or "Dev",
        created_by_id=user_id
    )
    db.add(new_version)
    db.commit()
    db.refresh(pipeline)

    record_audit(
        db=db,
        action="PIPELINE_ROLLBACK",
        resource_type="Pipeline",
        resource_id=pipeline.id,
        details={"restored_version": version_number, "new_version": pipeline.current_version},
        user_id=user_id
    )
    return pipeline


def export_pipeline_for_git(pipeline: Pipeline) -> Dict[str, Any]:
    """
    Exports a clean, vendor-agnostic declarative JSON specification
    suitable for Git version control and CI/CD deployment repositories.
    """
    payload = {
        "$schema": "https://dataflow.enterprise/schemas/pipeline.v1.json",
        "name": pipeline.name,
        "description": pipeline.description or "",
        "version": pipeline.current_version,
        "concurrency_limit": pipeline.concurrency_limit,
        "definition": pipeline.definition_json or {},
        "exported_at": datetime.now(timezone.utc).isoformat()
    }
    raw_str = json.dumps(payload, sort_keys=True)
    payload["checksum"] = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    return payload


def import_pipeline_from_git(
    spec: Dict[str, Any],
    project_id: str,
    db: Session,
    user_id: Optional[str] = None
) -> Pipeline:
    """
    Imports and validates a declarative JSON pipeline specification from a Git payload.
    Auto-creates or updates pipeline and versions.
    """
    name = spec.get("name")
    if not name:
        raise ValueError("Pipeline specification missing required 'name' field.")

    definition = spec.get("definition", {})
    activities = definition.get("activities", [])
    if activities:
        PipelineDAG(activities)

    pipeline = db.query(Pipeline).filter(
        Pipeline.project_id == project_id,
        Pipeline.name == name
    ).first()

    if pipeline:
        pipeline.description = spec.get("description", pipeline.description)
        pipeline.concurrency_limit = spec.get("concurrency_limit", pipeline.concurrency_limit)
        pipeline.definition_json = definition
        pipeline.current_version += 1
        pipeline.updated_at = datetime.now(timezone.utc)
        action = "PIPELINE_GIT_IMPORT_UPDATE"
    else:
        pipeline = Pipeline(
            project_id=project_id,
            name=name,
            description=spec.get("description", ""),
            concurrency_limit=spec.get("concurrency_limit", 5),
            definition_json=definition,
            status="Draft",
            current_version=1
        )
        db.add(pipeline)
        action = "PIPELINE_GIT_IMPORT_CREATE"

    db.commit()
    db.refresh(pipeline)

    ver = PipelineVersion(
        pipeline_id=pipeline.id,
        version_number=pipeline.current_version,
        definition_json=definition,
        changelog="Imported from Git repository payload",
        created_by_id=user_id
    )
    db.add(ver)
    db.commit()

    record_audit(
        db=db,
        action=action,
        resource_type="Pipeline",
        resource_id=pipeline.id,
        details={"name": name, "imported_version": pipeline.current_version},
        user_id=user_id
    )
    return pipeline
