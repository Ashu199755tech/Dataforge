from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.connection import Connection
from backend.app.schemas.connection import (
    ConnectionCreate, ConnectionUpdate, ConnectionResponse, ConnectionTestResponse
)
from backend.app.core.security import encrypt_secret, decrypt_secret, mask_secret_dict
from backend.app.connectors.factory import get_connector
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/connections", tags=["Connections"])


def _to_response(conn: Connection) -> ConnectionResponse:
    decrypted = decrypt_secret(conn.config_encrypted)
    masked = mask_secret_dict(decrypted)
    return ConnectionResponse(
        id=conn.id,
        project_id=conn.project_id,
        name=conn.name,
        connector_type=conn.connector_type,
        description=conn.description,
        status=conn.status,
        config_masked=masked,
        last_tested_at=conn.last_tested_at,
        created_at=conn.created_at,
        updated_at=conn.updated_at
    )


@router.get("", response_model=List[ConnectionResponse])
def list_connections(project_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Connection)
    if project_id:
        query = query.filter(Connection.project_id == project_id)
    return [_to_response(c) for c in query.all()]


@router.post("", response_model=ConnectionResponse)
def create_connection(conn_in: ConnectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    encrypted_config = encrypt_secret(conn_in.config)
    conn = Connection(
        project_id=conn_in.project_id,
        name=conn_in.name,
        connector_type=conn_in.connector_type,
        description=conn_in.description,
        config_encrypted=encrypted_config,
        status="Unverified"
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return _to_response(conn)


@router.get("/{connection_id}", response_model=ConnectionResponse)
def get_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _to_response(conn)


@router.delete("/{connection_id}")
def delete_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
    return {"message": "Connection deleted successfully"}


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    decrypted = decrypt_secret(conn.config_encrypted)
    try:
        connector = get_connector(conn.connector_type, decrypted)
        result = connector.test_connection()
        conn.status = "Active" if result.success else "Failed"
        conn.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        return ConnectionTestResponse(
            success=result.success,
            message=result.message,
            latency_ms=result.latency_ms,
            server_version=result.server_version
        )
    except Exception as e:
        conn.status = "Failed"
        conn.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        return ConnectionTestResponse(success=False, message=str(e))


@router.get("/{connection_id}/schemas")
def discover_schemas(connection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    decrypted = decrypt_secret(conn.config_encrypted)
    connector = get_connector(conn.connector_type, decrypted)
    return {"schemas": connector.discover_schemas()}


@router.get("/{connection_id}/tables")
def discover_tables(connection_id: str, schema_name: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    decrypted = decrypt_secret(conn.config_encrypted)
    connector = get_connector(conn.connector_type, decrypted)
    tables = connector.discover_tables(schema_name)
    return {"tables": [t.model_dump() for t in tables]}


@router.get("/{connection_id}/tables/{table_name}/columns")
def discover_columns(connection_id: str, table_name: str, schema_name: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    decrypted = decrypt_secret(conn.config_encrypted)
    connector = get_connector(conn.connector_type, decrypted)
    cols = connector.discover_columns(table_name, schema_name)
    return {"columns": [c.model_dump() for c in cols]}


@router.get("/{connection_id}/tables/{table_name}/preview")
def preview_table_data(connection_id: str, table_name: str, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    decrypted = decrypt_secret(conn.config_encrypted)
    connector = get_connector(conn.connector_type, decrypted)
    stream = connector.read_data_stream(table_name=table_name, batch_size=limit)
    rows = []
    for chunk in stream:
        rows.extend(chunk)
        if len(rows) >= limit:
            break
    return {"rows": rows[:limit]}
