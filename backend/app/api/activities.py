from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from backend.app.activities.registry import activity_registry
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/activities", tags=["Activities"])


@router.get("", response_model=List[Dict[str, Any]])
def list_activities(current_user: User = Depends(get_current_user)):
    """Returns the full catalog of registered activities and their metadata."""
    return activity_registry.list_activities()


@router.get("/{activity_type}", response_model=Dict[str, Any])
def get_activity_metadata(activity_type: str, current_user: User = Depends(get_current_user)):
    """Returns detailed metadata and configuration schema for a specific activity."""
    meta = activity_registry.get_metadata(activity_type)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Activity type '{activity_type}' not found.")
    return meta.to_dict()


@router.post("/{activity_type}/validate")
def validate_activity_configuration(
    activity_type: str,
    config: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Validates an activity's configuration against its declared schema."""
    valid, err = activity_registry.validate_config(activity_type, config)
    return {
        "activity_type": activity_type,
        "valid": valid,
        "error": err
    }
