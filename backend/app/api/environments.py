from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.models.security import Environment
from backend.app.schemas.security import EnvironmentCreate, EnvironmentResponse
from backend.app.core.rbac import require_role
from backend.app.models.user import User
from backend.app.core.audit import record_audit

router = APIRouter(prefix="/environments", tags=["Environment Management"])


@router.get("", response_model=List[EnvironmentResponse])
def list_environments(db: Session = Depends(get_db), current_user: User = Depends(require_role(["Viewer"]))):
    envs = db.query(Environment).order_by(Environment.created_at.asc()).all()
    # If no environments exist, seed standard default Dev/Test/Prod
    if not envs:
        defaults = [
            Environment(name="Dev", description="Development environment for authoring pipelines", is_default=True),
            Environment(name="Test", description="Automated QA and integration testing stage", is_default=False),
            Environment(name="Prod", description="Mission-critical enterprise production workload stage", is_default=False)
        ]
        db.add_all(defaults)
        db.commit()
        envs = db.query(Environment).order_by(Environment.created_at.asc()).all()
    return envs


@router.post("", response_model=EnvironmentResponse, status_code=201)
def create_environment(
    env_in: EnvironmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    existing = db.query(Environment).filter(Environment.name == env_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Environment '{env_in.name}' already exists.")

    env = Environment(
        name=env_in.name,
        description=env_in.description,
        is_default=env_in.is_default,
        variables=env_in.variables
    )
    db.add(env)
    db.commit()
    db.refresh(env)

    record_audit(
        db=db,
        action="ENVIRONMENT_CREATE",
        resource_type="Environment",
        resource_id=env.id,
        details={"name": env.name},
        user_id=current_user.id
    )
    return env


@router.delete("/{env_id}")
def delete_environment(
    env_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    if env.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default environment.")

    db.delete(env)
    db.commit()

    record_audit(
        db=db,
        action="ENVIRONMENT_DELETE",
        resource_type="Environment",
        resource_id=env_id,
        details={"name": env.name},
        user_id=current_user.id
    )
    return {"message": "Environment deleted successfully"}
