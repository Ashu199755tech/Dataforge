from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.workspace import Project
from backend.app.models.lineage import LineageNode
from backend.app.schemas.lineage import (
    LineageNodeResponse,
    LineageGraphResponse,
    ColumnTraceResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    LineageExtractResponse
)
from backend.app.services.lineage_service import LineageService

router = APIRouter(prefix="/lineage", tags=["Lineage & Impact Analysis"])


def _resolve_project_id(project_id: Optional[str], db: Session) -> str:
    """Helper to resolve or fallback to first available project."""
    if project_id:
        return project_id
    first_project = db.query(Project).first()
    if not first_project:
        raise HTTPException(status_code=400, detail="No projects found in workspace.")
    return first_project.id


@router.get("/graph", response_model=LineageGraphResponse)
def get_lineage_graph(
    project_id: Optional[str] = Query(None),
    root_id: Optional[str] = Query(None),
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    depth: int = Query(5, ge=1, le=20),
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full or sub-graph data lineage for the project.
    Supports upstream origin tracing, downstream consumption tracing, and filtering by entity type.
    """
    pid = _resolve_project_id(project_id, db)
    return LineageService.get_lineage_graph(
        db=db,
        project_id=pid,
        root_node_id=root_id,
        direction=direction,
        depth=depth,
        entity_type=entity_type
    )


@router.get("/nodes", response_model=List[LineageNodeResponse])
def list_lineage_nodes(
    project_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all lineage nodes (datasets, tables, files, pipelines) in the project."""
    pid = _resolve_project_id(project_id, db)
    query = db.query(LineageNode).filter(LineageNode.project_id == pid)
    if node_type:
        query = query.filter(LineageNode.node_type == node_type)
    return query.order_by(LineageNode.name.asc()).all()


@router.get("/column-trace", response_model=ColumnTraceResponse)
def get_column_trace(
    node_id: str = Query(..., description="LineageNode ID containing the column"),
    column: str = Query(..., description="Column name to trace"),
    direction: str = Query("upstream", pattern="^(upstream|downstream)$"),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Traces column-level lineage backwards to its root sources or forwards to its downstream destinations,
    identifying exact transformation formulas and confidence tiers.
    """
    pid = _resolve_project_id(project_id, db)
    return LineageService.get_column_lineage_trace(
        db=db,
        project_id=pid,
        node_id=node_id,
        column_name=column,
        direction=direction
    )


@router.post("/impact-analysis", response_model=ImpactAnalysisResponse)
def run_impact_analysis(
    req: ImpactAnalysisRequest,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates downstream blast radius of modifying, renaming, or deleting a dataset or column.
    Returns affected pipelines, sink tables, risk category (High/Medium/Low), and dependency subgraph.
    """
    pid = _resolve_project_id(project_id, db)
    try:
        return LineageService.analyze_impact(
            db=db,
            project_id=pid,
            node_id=req.node_id,
            qualified_name=req.qualified_name,
            column_name=req.column_name
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/extract", response_model=LineageExtractResponse)
def trigger_lineage_extraction(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extracts and updates data lineage graph across all project pipelines, activities, and datasets.
    """
    pid = _resolve_project_id(project_id, db)
    return LineageService.extract_project_lineage(db=db, project_id=pid)


@router.get("/export")
def export_lineage(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exports full project lineage graph in JSON format."""
    pid = _resolve_project_id(project_id, db)
    graph = LineageService.get_lineage_graph(db=db, project_id=pid, direction="both", depth=20)
    return {
        "project_id": pid,
        "exported_at": "now",
        "nodes": [n.model_dump(mode="json") for n in graph.nodes],
        "edges": [e.model_dump(mode="json") for e in graph.edges],
        "column_lineage": [c.model_dump(mode="json") for c in graph.column_lineage]
    }
