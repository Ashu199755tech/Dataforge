from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.app.core.database import get_db
from backend.app.schemas.security import SecretCreate, SecretResponse, SecretRotateRequest
from backend.app.security.vault import secret_vault
from backend.app.core.rbac import require_role
from backend.app.models.user import User

router = APIRouter(prefix="/secrets", tags=["Secrets Management & Encryption"])


@router.get("", response_model=List[SecretResponse])
def list_secrets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    """Returns metadata list of all vault secrets. Secret values are NEVER leaked."""
    return secret_vault.list_secrets(db)


@router.post("", response_model=SecretResponse, status_code=201)
def store_secret(
    secret_in: SecretCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Contributor", "DataEngineer", "Admin"]))
):
    """Encrypts secret value using AES-256 and stores in enterprise vault."""
    entry = secret_vault.store_secret(
        name=secret_in.name,
        value=secret_in.value,
        description=secret_in.description,
        db=db,
        user_id=current_user.id
    )
    return {
        "id": entry.id,
        "name": entry.name,
        "description": entry.description,
        "vault_provider": entry.vault_provider,
        "is_masked": True,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
    }


@router.delete("/{name}")
def delete_secret(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    """Deletes secret from vault with audit logging."""
    success = secret_vault.delete_secret(name, db, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found.")
    return {"message": f"Secret '{name}' successfully deleted."}


@router.post("/rotate")
def rotate_vault_keys(
    rotate_req: SecretRotateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin"]))
):
    """Re-encrypts all stored secrets under a new AES-256 encryption key."""
    if len(rotate_req.new_encryption_key) < 16:
        raise HTTPException(status_code=400, detail="New encryption key must be at least 16 characters.")
    rotated_count = secret_vault.rotate_keys(rotate_req.new_encryption_key, db, current_user.id)
    return {"message": f"Key rotation complete. {rotated_count} secrets re-encrypted.", "rotated_entries": rotated_count}
