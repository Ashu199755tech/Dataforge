from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from backend.app.core.database import SessionLocal
from backend.app.models.dataflow import DataFlow
from backend.app.models.workspace import Project
from backend.app.dataflow.engine import DataFlowEngine

router = APIRouter(prefix="/dataflows", tags=["DataFlows"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DataFlowCreateRequest(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    graph_json: Optional[Dict[str, Any]] = None


class DataFlowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    graph_json: Optional[Dict[str, Any]] = None


@router.get("")
def list_dataflows(project_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(DataFlow)
    if project_id:
        query = query.filter(DataFlow.project_id == project_id)
    dfs = query.order_by(DataFlow.created_at.desc()).all()
    return [
        {
            "id": df.id,
            "project_id": df.project_id,
            "name": df.name,
            "description": df.description,
            "node_count": len(df.graph_json.get("nodes", [])),
            "created_at": df.created_at.isoformat(),
            "updated_at": df.updated_at.isoformat()
        }
        for df in dfs
    ]


@router.post("")
def create_dataflow(req: DataFlowCreateRequest, db: Session = Depends(get_db)):
    # Verify project
    proj = db.query(Project).filter(Project.id == req.project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    default_graph = req.graph_json or {
        "nodes": [
            {
                "id": "source_1",
                "type": "dataFlowNode",
                "position": {"x": 100, "y": 200},
                "data": {"label": "Source Data", "operatorType": "Source", "config": {}}
            },
            {
                "id": "sink_1",
                "type": "dataFlowNode",
                "position": {"x": 500, "y": 200},
                "data": {"label": "Target Sink", "operatorType": "Sink", "config": {}}
            }
        ],
        "edges": [
            {
                "id": "e_source1_sink1",
                "source": "source_1",
                "target": "sink_1"
            }
        ]
    }

    df = DataFlow(
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        graph_json=default_graph
    )
    db.add(df)
    db.commit()
    db.refresh(df)
    return df


@router.get("/{id}")
def get_dataflow(id: str, db: Session = Depends(get_db)):
    df = db.query(DataFlow).filter(DataFlow.id == id).first()
    if not df:
        raise HTTPException(status_code=404, detail="DataFlow not found")
    return {
        "id": df.id,
        "project_id": df.project_id,
        "name": df.name,
        "description": df.description,
        "graph_json": df.graph_json,
        "created_at": df.created_at.isoformat(),
        "updated_at": df.updated_at.isoformat()
    }


@router.put("/{id}")
def update_dataflow(id: str, req: DataFlowUpdateRequest, db: Session = Depends(get_db)):
    df = db.query(DataFlow).filter(DataFlow.id == id).first()
    if not df:
        raise HTTPException(status_code=404, detail="DataFlow not found")

    if req.name is not None:
        df.name = req.name
    if req.description is not None:
        df.description = req.description
    if req.graph_json is not None:
        df.graph_json = req.graph_json

    db.commit()
    db.refresh(df)
    return {"message": "DataFlow updated successfully", "id": df.id}


@router.delete("/{id}")
def delete_dataflow(id: str, db: Session = Depends(get_db)):
    df = db.query(DataFlow).filter(DataFlow.id == id).first()
    if not df:
        raise HTTPException(status_code=404, detail="DataFlow not found")
    db.delete(df)
    db.commit()
    return {"message": "DataFlow deleted successfully"}


@router.post("/{id}/preview/{node_id}")
def preview_node_output(id: str, node_id: str, db: Session = Depends(get_db)):
    df = db.query(DataFlow).filter(DataFlow.id == id).first()
    if not df:
        raise HTTPException(status_code=404, detail="DataFlow not found")

    engine = DataFlowEngine(db_session=db)
    res = engine.execute_graph(df.graph_json, limit_preview=50)

    if res.status != "Succeeded":
        raise HTTPException(status_code=400, detail=f"Data preview failed: {res.error_message}")

    preview = res.node_outputs.get(node_id)
    if not preview:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' produced no preview records.")

    return preview


@router.post("/{id}/execute")
def execute_dataflow(id: str, db: Session = Depends(get_db)):
    df = db.query(DataFlow).filter(DataFlow.id == id).first()
    if not df:
        raise HTTPException(status_code=404, detail="DataFlow not found")

    engine = DataFlowEngine(db_session=db)
    res = engine.execute_graph(df.graph_json)

    if res.status != "Succeeded":
        raise HTTPException(status_code=500, detail=f"Execution failed: {res.error_message}")

    return res.to_dict()
