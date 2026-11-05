from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.api.deps import get_current_user
from backend.app.models.dataset import Dataset, DatasetVersion
from backend.app.models.connection import Connection
from backend.app.services.dataset_service import DatasetService
from backend.app.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetVersionResponse,
    SchemaDriftReport,
    DatasetPreviewRequest,
    DatasetPreviewResponse,
    DatasetUsageResponse
)

router = APIRouter(prefix="/datasets", tags=["Reusable Datasets"])


def _to_dataset_response(ds: Dataset, db: Session) -> DatasetResponse:
    conn = db.query(Connection).filter(Connection.id == ds.connection_id).first()
    return DatasetResponse(
        id=ds.id,
        project_id=ds.project_id,
        connection_id=ds.connection_id,
        name=ds.name,
        description=ds.description,
        dataset_type=ds.dataset_type,
        location_config=ds.location_config or {},
        format_settings=ds.format_settings or {},
        parameters=ds.parameters or {},
        schema_definition=ds.schema_definition or [],
        current_version=ds.current_version,
        schema_status=ds.schema_status,
        last_drift_check_at=ds.last_drift_check_at,
        last_drift_summary=ds.last_drift_summary,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        connection_name=conn.name if conn else None,
        connector_type=conn.connector_type if conn else None
    )


@router.get("", response_model=List[DatasetResponse])
@router.get("/", response_model=List[DatasetResponse])
def list_datasets(
    project_id: Optional[str] = None,
    connection_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all reusable datasets for the workspace/project."""
    datasets = DatasetService.list_datasets(db, project_id=project_id, connection_id=connection_id)
    return [_to_dataset_response(ds, db) for ds in datasets]


@router.post("", response_model=DatasetResponse)
@router.post("/", response_model=DatasetResponse)
def create_dataset(
    dataset_in: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new reusable dataset with optional auto-discovery of physical schema."""
    try:
        dataset = DatasetService.create_dataset(db, dataset_in)
        return _to_dataset_response(dataset, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {str(e)}")


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves a single dataset by ID."""
    try:
        dataset = DatasetService.get_dataset(db, dataset_id)
        return _to_dataset_response(dataset, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{dataset_id}", response_model=DatasetResponse)
def update_dataset(
    dataset_id: str,
    dataset_in: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates dataset configuration and increments schema version if columns altered."""
    try:
        dataset = DatasetService.update_dataset(db, dataset_id, dataset_in)
        return _to_dataset_response(dataset, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a reusable dataset and its version history."""
    try:
        DatasetService.delete_dataset(db, dataset_id)
        return {"status": "deleted", "message": "Dataset deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dataset_id}/versions", response_model=List[DatasetVersionResponse])
def get_dataset_versions(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves all schema version snapshots for this dataset."""
    versions = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(DatasetVersion.version_number.desc()).all()
    return versions


@router.post("/{dataset_id}/infer-schema")
def infer_dataset_schema(
    dataset_id: str,
    payload: Dict[str, Any] = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Infers schema directly from the underlying physical source (table or storage file)."""
    try:
        dataset = DatasetService.get_dataset(db, dataset_id)
        columns = DatasetService.infer_schema(db, dataset, parameter_values=payload.get("parameters"))
        return {"columns": columns, "count": len(columns)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema inference error: {str(e)}")


@router.post("/{dataset_id}/detect-drift", response_model=SchemaDriftReport)
def detect_dataset_schema_drift(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compares the stored dataset schema against the live physical data source to detect drift."""
    try:
        report = DatasetService.detect_schema_drift(db, dataset_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drift detection error: {str(e)}")


@router.post("/{dataset_id}/sync-schema", response_model=DatasetResponse)
def sync_dataset_schema(
    dataset_id: str,
    payload: Dict[str, Any] = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Synchronizes stored schema with live source, creating a new version snapshot and resolving drift."""
    try:
        notes = payload.get("notes") or "Synchronized with source schema"
        dataset, _ = DatasetService.sync_schema(db, dataset_id, change_summary=notes)
        return _to_dataset_response(dataset, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema sync error: {str(e)}")


@router.post("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset_data(
    dataset_id: str,
    req: DatasetPreviewRequest = DatasetPreviewRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Previews up to row_limit records safely within memory constraints."""
    try:
        res = DatasetService.preview_data(
            db=db,
            dataset_id=dataset_id,
            row_limit=req.row_limit,
            parameter_values=req.parameter_values
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")


@router.get("/{dataset_id}/usages", response_model=DatasetUsageResponse)
def get_dataset_usages(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyzes pipeline dependencies to find which pipelines and activities reference this dataset."""
    try:
        return DatasetService.get_dataset_usages(db, dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
