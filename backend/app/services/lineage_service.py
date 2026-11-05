import re
import uuid
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import deque
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.lineage import LineageNode, LineageEdge, ColumnLineage
from backend.app.models.pipeline import Pipeline
from backend.app.models.dataset import Dataset
from backend.app.models.connection import Connection
from backend.app.models.dataflow import DataFlow
from backend.app.schemas.lineage import (
    LineageNodeResponse,
    LineageEdgeResponse,
    ColumnLineageResponse,
    LineageGraphResponse,
    ColumnTraceStep,
    ColumnTraceResponse,
    ImpactAnalysisResponse,
    LineageExtractResponse
)


class LineageService:
    """
    Enterprise Data Lineage and Impact Analysis Engine.
    Extracts end-to-end data flows from pipelines, Copy Data activities,
    DataFlow transformations, and SQL queries with column-level precision.
    """

    @classmethod
    def _parse_sql_query(cls, query: str) -> Tuple[List[str], List[str]]:
        """
        Extracts source tables and projected columns from a SQL query using regex.
        Returns: (tables, columns)
        """
        if not query:
            return [], []

        tables: List[str] = []
        columns: List[str] = []

        # Find FROM / JOIN tables
        from_matches = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)', query, re.IGNORECASE)
        for t in from_matches:
            clean_t = t.strip('`"[]')
            if clean_t and clean_t.upper() not in ['SELECT', 'WHERE', 'GROUP', 'ORDER']:
                tables.append(clean_t)

        # Find SELECT columns
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
        if select_match:
            raw_cols = select_match.group(1).split(',')
            for c in raw_cols:
                col = c.strip()
                # Handle alias: "expr AS alias"
                as_match = re.search(r'\s+AS\s+([a-zA-Z0-9_]+)', col, re.IGNORECASE)
                if as_match:
                    columns.append(as_match.group(1))
                else:
                    col_clean = col.split('.')[-1].strip('`"[]')
                    columns.append(col_clean)

        return tables, columns

    @classmethod
    def get_or_create_node(
        cls,
        db: Session,
        project_id: str,
        node_type: str,
        name: str,
        qualified_name: str,
        provider: str = "generic",
        location_uri: Optional[str] = None,
        dataset_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        schema_json: Optional[List[Dict[str, Any]]] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> LineageNode:
        """Finds or creates a LineageNode by its unique qualified_name."""
        node = db.query(LineageNode).filter(
            LineageNode.project_id == project_id,
            LineageNode.qualified_name == qualified_name
        ).first()

        if not node:
            node = LineageNode(
                id=str(uuid.uuid4()),
                project_id=project_id,
                node_type=node_type,
                name=name,
                qualified_name=qualified_name,
                provider=provider,
                location_uri=location_uri,
                dataset_id=dataset_id,
                pipeline_id=pipeline_id,
                connection_id=connection_id,
                schema_json=schema_json or [],
                metadata_json=metadata_json or {}
            )
            db.add(node)
            db.flush()
        else:
            # Update metadata if needed
            if schema_json and not node.schema_json:
                node.schema_json = schema_json
            if location_uri and not node.location_uri:
                node.location_uri = location_uri
            db.flush()

        return node

    @classmethod
    def extract_from_copy_data(
        cls,
        db: Session,
        project_id: str,
        pipeline: Pipeline,
        activity: Dict[str, Any]
    ) -> Tuple[int, int, int]:
        """
        Extracts source, sink, and column mappings from a Copy Data activity.
        Returns: (nodes_count, edges_count, columns_count)
        """
        config = activity.get("config", {}) or {}
        source_cfg = config.get("source", {}) or {}
        dest_cfg = config.get("destination", {}) or config.get("sink", {}) or {}
        activity_name = activity.get("name", "CopyDataActivity")

        nodes_added = 0
        edges_added = 0
        cols_added = 0

        # 1. Resolve Source Node
        source_node: Optional[LineageNode] = None
        source_cols: List[str] = []

        # Check for Reusable Dataset reference
        source_ds_id = source_cfg.get("dataset_id") or config.get("source_dataset_id")
        if source_ds_id:
            src_ds = db.query(Dataset).filter(Dataset.id == source_ds_id).first()
            if src_ds:
                loc = src_ds.location_config or {}
                source_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Dataset",
                    name=src_ds.name,
                    qualified_name=f"dataset:{src_ds.name}",
                    provider=src_ds.dataset_type,
                    location_uri=loc.get("path") or loc.get("table") or f"{src_ds.dataset_type}://location",
                    dataset_id=src_ds.id,
                    schema_json=src_ds.schema_definition or []
                )
                source_cols = [c.get("name") for c in (src_ds.schema_definition or []) if c.get("name")]
                nodes_added += 1

        if not source_node:
            # Check for direct connection + table/storage file
            conn_id = source_cfg.get("connection_id")
            conn = db.query(Connection).filter(Connection.id == conn_id).first() if conn_id else None
            provider = conn.connector_type if conn else "generic"

            if source_cfg.get("query"):
                tables, sql_cols = cls._parse_sql_query(source_cfg.get("query", ""))
                table_name = tables[0] if tables else "query_result"
                source_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Table",
                    name=table_name,
                    qualified_name=f"{provider}://{table_name}",
                    provider=provider,
                    connection_id=conn_id,
                    schema_json=[{"name": col, "type": "STRING"} for col in sql_cols]
                )
                source_cols = sql_cols
                nodes_added += 1
            elif source_cfg.get("table_name") or source_cfg.get("table"):
                tbl = source_cfg.get("table_name") or source_cfg.get("table")
                schema = source_cfg.get("schema_name") or source_cfg.get("schema") or "public"
                source_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Table",
                    name=tbl,
                    qualified_name=f"{provider}://{schema}.{tbl}",
                    provider=provider,
                    location_uri=f"{provider}://{schema}.{tbl}",
                    connection_id=conn_id
                )
                nodes_added += 1
            elif source_cfg.get("container") or source_cfg.get("bucket"):
                bucket = source_cfg.get("container") or source_cfg.get("bucket")
                path = source_cfg.get("path") or source_cfg.get("file_path") or ""
                source_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="StorageFile",
                    name=path.split('/')[-1] if path else bucket,
                    qualified_name=f"{provider}://{bucket}/{path}",
                    provider=provider,
                    location_uri=f"{provider}://{bucket}/{path}",
                    connection_id=conn_id
                )
                nodes_added += 1

        # 2. Resolve Destination / Sink Node
        dest_node: Optional[LineageNode] = None
        dest_ds_id = dest_cfg.get("dataset_id") or config.get("sink_dataset_id")
        if dest_ds_id:
            dst_ds = db.query(Dataset).filter(Dataset.id == dest_ds_id).first()
            if dst_ds:
                loc = dst_ds.location_config or {}
                dest_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Dataset",
                    name=dst_ds.name,
                    qualified_name=f"dataset:{dst_ds.name}",
                    provider=dst_ds.dataset_type,
                    location_uri=loc.get("path") or loc.get("table") or f"{dst_ds.dataset_type}://location",
                    dataset_id=dst_ds.id,
                    schema_json=dst_ds.schema_definition or []
                )
                nodes_added += 1

        if not dest_node:
            conn_id = dest_cfg.get("connection_id")
            conn = db.query(Connection).filter(Connection.id == conn_id).first() if conn_id else None
            provider = conn.connector_type if conn else "generic"

            if dest_cfg.get("table_name") or dest_cfg.get("table"):
                tbl = dest_cfg.get("table_name") or dest_cfg.get("table")
                schema = dest_cfg.get("schema_name") or dest_cfg.get("schema") or "public"
                dest_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Table",
                    name=tbl,
                    qualified_name=f"{provider}://{schema}.{tbl}",
                    provider=provider,
                    location_uri=f"{provider}://{schema}.{tbl}",
                    connection_id=conn_id
                )
                nodes_added += 1
            elif dest_cfg.get("container") or dest_cfg.get("bucket"):
                bucket = dest_cfg.get("container") or dest_cfg.get("bucket")
                path = dest_cfg.get("path") or dest_cfg.get("file_path") or ""
                dest_node = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="StorageFile",
                    name=path.split('/')[-1] if path else bucket,
                    qualified_name=f"{provider}://{bucket}/{path}",
                    provider=provider,
                    location_uri=f"{provider}://{bucket}/{path}",
                    connection_id=conn_id
                )
                nodes_added += 1

        if not source_node or not dest_node:
            return nodes_added, edges_added, cols_added

        # 3. Create Directed Lineage Edge: source_node -> dest_node
        raw_mappings = config.get("column_mappings") or config.get("translator", {}).get("mappings", [])
        confidence = "exact" if raw_mappings else "partial"

        # Check existing edge
        edge = db.query(LineageEdge).filter(
            LineageEdge.project_id == project_id,
            LineageEdge.source_node_id == source_node.id,
            LineageEdge.target_node_id == dest_node.id,
            LineageEdge.pipeline_id == pipeline.id
        ).first()

        if not edge:
            edge = LineageEdge(
                id=str(uuid.uuid4()),
                project_id=project_id,
                source_node_id=source_node.id,
                target_node_id=dest_node.id,
                edge_type="FlowsTo",
                pipeline_id=pipeline.id,
                activity_name=activity_name,
                confidence=confidence,
                metadata_json={"activity_type": "CopyData"}
            )
            db.add(edge)
            db.flush()
            edges_added += 1

        # 4. Create Column Lineages
        if raw_mappings:
            for m in raw_mappings:
                src_col = m.get("source") or m.get("source_column") or (m.get("source", {}).get("name") if isinstance(m.get("source"), dict) else None)
                dst_col = m.get("destination") or m.get("target_column") or m.get("sink_column") or (m.get("sink", {}).get("name") if isinstance(m.get("sink"), dict) else None)
                
                if src_col and dst_col:
                    existing_col = db.query(ColumnLineage).filter(
                        ColumnLineage.edge_id == edge.id,
                        ColumnLineage.source_column == str(src_col),
                        ColumnLineage.target_column == str(dst_col)
                    ).first()
                    if not existing_col:
                        cl = ColumnLineage(
                            id=str(uuid.uuid4()),
                            edge_id=edge.id,
                            source_column=str(src_col),
                            target_column=str(dst_col),
                            transformation_type="direct",
                            expression=str(src_col),
                            confidence="exact"
                        )
                        db.add(cl)
                        cols_added += 1
        elif source_cols:
            # Automatic 1-to-1 matching from query projection
            for col in source_cols:
                existing_col = db.query(ColumnLineage).filter(
                    ColumnLineage.edge_id == edge.id,
                    ColumnLineage.source_column == str(col),
                    ColumnLineage.target_column == str(col)
                ).first()
                if not existing_col:
                    cl = ColumnLineage(
                        id=str(uuid.uuid4()),
                        edge_id=edge.id,
                        source_column=str(col),
                        target_column=str(col),
                        transformation_type="direct",
                        expression=str(col),
                        confidence="exact"
                    )
                    db.add(cl)
                    cols_added += 1
        else:
            # Wildcard passthrough
            existing_col = db.query(ColumnLineage).filter(
                ColumnLineage.edge_id == edge.id,
                ColumnLineage.source_column == "*"
            ).first()
            if not existing_col:
                cl = ColumnLineage(
                    id=str(uuid.uuid4()),
                    edge_id=edge.id,
                    source_column="*",
                    target_column="*",
                    transformation_type="passthrough",
                    expression="*",
                    confidence="partial"
                )
                db.add(cl)
                cols_added += 1

        db.flush()
        return nodes_added, edges_added, cols_added

    @classmethod
    def extract_from_dataflow(
        cls,
        db: Session,
        project_id: str,
        pipeline: Optional[Pipeline],
        dataflow: DataFlow
    ) -> Tuple[int, int, int]:
        """
        Extracts lineage across transformation DAG nodes in a DataFlow.
        Traces sources through transformations (Derived Column, Select, Aggregate, Join) to sinks.
        """
        nodes_added = 0
        edges_added = 0
        cols_added = 0

        graph = dataflow.graph_json or {}
        df_nodes = graph.get("nodes", [])
        df_edges = graph.get("edges", [])

        if not df_nodes:
            return 0, 0, 0

        # Map operator node id to LineageNode
        node_map: Dict[str, LineageNode] = {}

        for op in df_nodes:
            op_id = op.get("id")
            op_type = op.get("type", "transform")
            op_data = op.get("data", {}) or {}
            op_label = op_data.get("label", op_id)

            if op_type == "source":
                ds_name = op_data.get("dataset_name") or op_label
                conn_type = op_data.get("connector_type", "database")
                ln = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Dataset",
                    name=ds_name,
                    qualified_name=f"dataflow_source:{dataflow.id}:{op_id}",
                    provider=conn_type,
                    schema_json=[{"name": c, "type": "STRING"} for c in op_data.get("schema", [])]
                )
            elif op_type == "sink":
                sink_name = op_data.get("sink_name") or op_label
                conn_type = op_data.get("connector_type", "database")
                ln = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="Dataset",
                    name=sink_name,
                    qualified_name=f"dataflow_sink:{dataflow.id}:{op_id}",
                    provider=conn_type
                )
            else:
                ln = cls.get_or_create_node(
                    db=db,
                    project_id=project_id,
                    node_type="DataFlow",
                    name=f"{dataflow.name} / {op_label}",
                    qualified_name=f"dataflow_transform:{dataflow.id}:{op_id}",
                    provider="polars",
                    metadata_json={"operator_type": op_type}
                )
            node_map[op_id] = ln
            nodes_added += 1

        # Connect edges between operators
        for edge in df_edges:
            src_id = edge.get("source")
            tgt_id = edge.get("target")
            src_node = node_map.get(src_id)
            tgt_node = node_map.get(tgt_id)

            if src_node and tgt_node:
                existing_edge = db.query(LineageEdge).filter(
                    LineageEdge.project_id == project_id,
                    LineageEdge.source_node_id == src_node.id,
                    LineageEdge.target_node_id == tgt_node.id
                ).first()

                if not existing_edge:
                    edge_rec = LineageEdge(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        source_node_id=src_node.id,
                        target_node_id=tgt_node.id,
                        edge_type="Transforms",
                        pipeline_id=pipeline.id if pipeline else None,
                        activity_name=dataflow.name,
                        confidence="derived",
                        metadata_json={"dataflow_id": dataflow.id}
                    )
                    db.add(edge_rec)
                    db.flush()
                    edges_added += 1
                else:
                    edge_rec = existing_edge

                # Check target operator for column derivations
                tgt_op = next((n for n in df_nodes if n.get("id") == tgt_id), {})
                tgt_data = tgt_op.get("data", {}) or {}
                derivations = tgt_data.get("derivations", []) or tgt_data.get("columns", [])

                if derivations:
                    for d in derivations:
                        target_col = d.get("column") or d.get("name")
                        expr = d.get("expression") or d.get("formula") or target_col
                        # Parse source columns referenced in expression
                        referenced_cols = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expr or "")
                        for ref_col in (referenced_cols or [target_col]):
                            if ref_col.upper() not in ['CONCAT', 'UPPER', 'LOWER', 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'CASE', 'WHEN', 'THEN']:
                                cl = ColumnLineage(
                                    id=str(uuid.uuid4()),
                                    edge_id=edge_rec.id,
                                    source_column=ref_col,
                                    target_column=target_col,
                                    transformation_type="derived",
                                    expression=expr,
                                    confidence="derived"
                                )
                                db.add(cl)
                                cols_added += 1

        db.flush()
        return nodes_added, edges_added, cols_added

    @classmethod
    def extract_project_lineage(cls, db: Session, project_id: str) -> LineageExtractResponse:
        """
        Scans all pipelines, activities, Copy Data configurations, and DataFlows
        in a project and builds the complete lineage graph.
        """
        total_nodes = 0
        total_edges = 0
        total_cols = 0

        # 1. Register standalone Reusable Datasets
        datasets = db.query(Dataset).filter(Dataset.project_id == project_id).all()
        for ds in datasets:
            loc = ds.location_config or {}
            cls.get_or_create_node(
                db=db,
                project_id=project_id,
                node_type="Dataset",
                name=ds.name,
                qualified_name=f"dataset:{ds.name}",
                provider=ds.dataset_type,
                location_uri=loc.get("path") or loc.get("table") or f"{ds.dataset_type}://location",
                dataset_id=ds.id,
                schema_json=ds.schema_definition or []
            )
            total_nodes += 1

        # 2. Extract from Pipelines & Activities
        pipelines = db.query(Pipeline).filter(Pipeline.project_id == project_id).all()
        for p in pipelines:
            acts = (p.definition_json or {}).get("activities", [])
            for act in acts:
                act_type = act.get("type") or act.get("activity_type")
                if act_type in ["CopyData", "Copy"]:
                    n, e, c = cls.extract_from_copy_data(db, project_id, p, act)
                    total_nodes += n
                    total_edges += e
                    total_cols += c
                elif act_type in ["ExecuteDataFlow", "DataFlow"]:
                    df_id = act.get("config", {}).get("dataflow_id")
                    if df_id:
                        df_rec = db.query(DataFlow).filter(DataFlow.id == df_id).first()
                        if df_rec:
                            n, e, c = cls.extract_from_dataflow(db, project_id, p, df_rec)
                            total_nodes += n
                            total_edges += e
                            total_cols += c

        # 3. Extract standalone DataFlows
        dataflows = db.query(DataFlow).filter(DataFlow.project_id == project_id).all()
        for df in dataflows:
            n, e, c = cls.extract_from_dataflow(db, project_id, None, df)
            total_nodes += n
            total_edges += e
            total_cols += c

        db.commit()

        return LineageExtractResponse(
            status="Succeeded",
            message=f"Lineage extraction completed for project {project_id}",
            nodes_discovered=total_nodes,
            edges_discovered=total_edges,
            columns_mapped=total_cols
        )

    @classmethod
    def get_lineage_graph(
        cls,
        db: Session,
        project_id: str,
        root_node_id: Optional[str] = None,
        direction: str = "both",
        depth: int = 5,
        entity_type: Optional[str] = None
    ) -> LineageGraphResponse:
        """
        Retrieves full or filtered lineage graph using BFS traversal.
        Direction: 'upstream', 'downstream', 'both'.
        """
        if not root_node_id:
            # Return full project lineage graph
            node_query = db.query(LineageNode).filter(LineageNode.project_id == project_id)
            if entity_type:
                node_query = node_query.filter(LineageNode.node_type == entity_type)
            nodes = node_query.all()

            edge_query = db.query(LineageEdge).filter(LineageEdge.project_id == project_id)
            edges = edge_query.all()

            edge_ids = [e.id for e in edges]
            col_lineages = db.query(ColumnLineage).filter(ColumnLineage.edge_id.in_(edge_ids)).all() if edge_ids else []

            return LineageGraphResponse(
                nodes=[LineageNodeResponse.model_validate(n) for n in nodes],
                edges=[LineageEdgeResponse.model_validate(e) for e in edges],
                column_lineage=[ColumnLineageResponse.model_validate(c) for c in col_lineages]
            )

        # BFS Traversal from root_node_id
        root = db.query(LineageNode).filter(
            LineageNode.id == root_node_id,
            LineageNode.project_id == project_id
        ).first()

        if not root:
            return LineageGraphResponse(nodes=[], edges=[], column_lineage=[])

        visited_node_ids: Set[str] = {root.id}
        collected_edges: List[LineageEdge] = []

        # Upstream BFS
        if direction in ["upstream", "both"]:
            queue = deque([(root.id, 0)])
            while queue:
                curr_id, curr_depth = queue.popleft()
                if curr_depth >= depth:
                    continue
                incoming = db.query(LineageEdge).filter(
                    LineageEdge.project_id == project_id,
                    LineageEdge.target_node_id == curr_id
                ).all()
                for e in incoming:
                    collected_edges.append(e)
                    if e.source_node_id not in visited_node_ids:
                        visited_node_ids.add(e.source_node_id)
                        queue.append((e.source_node_id, curr_depth + 1))

        # Downstream BFS
        if direction in ["downstream", "both"]:
            queue = deque([(root.id, 0)])
            while queue:
                curr_id, curr_depth = queue.popleft()
                if curr_depth >= depth:
                    continue
                outgoing = db.query(LineageEdge).filter(
                    LineageEdge.project_id == project_id,
                    LineageEdge.source_node_id == curr_id
                ).all()
                for e in outgoing:
                    collected_edges.append(e)
                    if e.target_node_id not in visited_node_ids:
                        visited_node_ids.add(e.target_node_id)
                        queue.append((e.target_node_id, curr_depth + 1))

        # Fetch nodes
        nodes = db.query(LineageNode).filter(LineageNode.id.in_(visited_node_ids)).all()

        # Deduplicate edges
        edge_dict = {e.id: e for e in collected_edges}
        final_edges = list(edge_dict.values())
        edge_ids = list(edge_dict.keys())

        col_lineages = db.query(ColumnLineage).filter(ColumnLineage.edge_id.in_(edge_ids)).all() if edge_ids else []

        return LineageGraphResponse(
            nodes=[LineageNodeResponse.model_validate(n) for n in nodes],
            edges=[LineageEdgeResponse.model_validate(e) for e in final_edges],
            column_lineage=[ColumnLineageResponse.model_validate(c) for c in col_lineages]
        )

    @classmethod
    def get_column_lineage_trace(
        cls,
        db: Session,
        project_id: str,
        node_id: str,
        column_name: str,
        direction: str = "upstream"
    ) -> ColumnTraceResponse:
        """
        Traces a single column backwards (upstream origin) or forwards (downstream destination).
        """
        root_node = db.query(LineageNode).filter(LineageNode.id == node_id).first()
        node_name = root_node.name if root_node else "Unknown"

        trace_steps: List[ColumnTraceStep] = []
        visited = set()

        if direction == "upstream":
            queue = deque([(node_id, column_name)])
            while queue:
                curr_node_id, curr_col = queue.popleft()
                incoming_edges = db.query(LineageEdge).filter(
                    LineageEdge.project_id == project_id,
                    LineageEdge.target_node_id == curr_node_id
                ).all()

                for e in incoming_edges:
                    cols = db.query(ColumnLineage).filter(
                        ColumnLineage.edge_id == e.id,
                        or_(ColumnLineage.target_column == curr_col, ColumnLineage.target_column == "*")
                    ).all()

                    for c in cols:
                        step_key = (e.id, c.source_column, c.target_column)
                        if step_key not in visited:
                            visited.add(step_key)
                            src_n = db.query(LineageNode).filter(LineageNode.id == e.source_node_id).first()
                            tgt_n = db.query(LineageNode).filter(LineageNode.id == e.target_node_id).first()
                            trace_steps.append(ColumnTraceStep(
                                edge_id=e.id,
                                source_node_id=e.source_node_id,
                                source_node_name=src_n.name if src_n else "Unknown",
                                source_column=c.source_column,
                                target_node_id=e.target_node_id,
                                target_node_name=tgt_n.name if tgt_n else "Unknown",
                                target_column=c.target_column,
                                transformation_type=c.transformation_type,
                                expression=c.expression,
                                confidence=c.confidence
                            ))
                            if c.source_column != "*":
                                queue.append((e.source_node_id, c.source_column))
        else: # downstream
            queue = deque([(node_id, column_name)])
            while queue:
                curr_node_id, curr_col = queue.popleft()
                outgoing_edges = db.query(LineageEdge).filter(
                    LineageEdge.project_id == project_id,
                    LineageEdge.source_node_id == curr_node_id
                ).all()

                for e in outgoing_edges:
                    cols = db.query(ColumnLineage).filter(
                        ColumnLineage.edge_id == e.id,
                        or_(ColumnLineage.source_column == curr_col, ColumnLineage.source_column == "*")
                    ).all()

                    for c in cols:
                        step_key = (e.id, c.source_column, c.target_column)
                        if step_key not in visited:
                            visited.add(step_key)
                            src_n = db.query(LineageNode).filter(LineageNode.id == e.source_node_id).first()
                            tgt_n = db.query(LineageNode).filter(LineageNode.id == e.target_node_id).first()
                            trace_steps.append(ColumnTraceStep(
                                edge_id=e.id,
                                source_node_id=e.source_node_id,
                                source_node_name=src_n.name if src_n else "Unknown",
                                source_column=c.source_column,
                                target_node_id=e.target_node_id,
                                target_node_name=tgt_n.name if tgt_n else "Unknown",
                                target_column=c.target_column,
                                transformation_type=c.transformation_type,
                                expression=c.expression,
                                confidence=c.confidence
                            ))
                            if c.target_column != "*":
                                queue.append((e.target_node_id, c.target_column))

        return ColumnTraceResponse(
            column_name=column_name,
            node_id=node_id,
            node_name=node_name,
            direction=direction,
            trace_steps=trace_steps
        )

    @classmethod
    def analyze_impact(
        cls,
        db: Session,
        project_id: str,
        node_id: Optional[str] = None,
        qualified_name: Optional[str] = None,
        column_name: Optional[str] = None
    ) -> ImpactAnalysisResponse:
        """
        Calculates the blast radius and downstream dependencies affected if an entity or column is modified or deleted.
        """
        target_node = None
        if node_id:
            target_node = db.query(LineageNode).filter(
                LineageNode.id == node_id,
                LineageNode.project_id == project_id
            ).first()
        elif qualified_name:
            target_node = db.query(LineageNode).filter(
                LineageNode.qualified_name == qualified_name,
                LineageNode.project_id == project_id
            ).first()

        if not target_node:
            raise ValueError(f"Lineage target entity not found for analysis.")

        # Downstream BFS to find all affected nodes and pipelines
        downstream_graph = cls.get_lineage_graph(
            db=db,
            project_id=project_id,
            root_node_id=target_node.id,
            direction="downstream",
            depth=10
        )

        affected_node_ids = {n.id for n in downstream_graph.nodes if n.id != target_node.id}
        affected_nodes_meta = []
        affected_pipelines: Set[str] = set()
        affected_datasets: Set[str] = set()
        affected_cols: Set[str] = set()

        for edge in downstream_graph.edges:
            if edge.pipeline_id:
                affected_pipelines.add(edge.pipeline_id)

        for n in downstream_graph.nodes:
            if n.id != target_node.id:
                if n.node_type == "Dataset":
                    affected_datasets.add(n.name)
                affected_nodes_meta.append({
                    "id": n.id,
                    "name": n.name,
                    "node_type": n.node_type,
                    "provider": n.provider
                })

        # If column-level impact requested
        if column_name:
            col_trace = cls.get_column_lineage_trace(
                db=db,
                project_id=project_id,
                node_id=target_node.id,
                column_name=column_name,
                direction="downstream"
            )
            for step in col_trace.trace_steps:
                affected_cols.add(f"{step.target_node_name}.{step.target_column}")

        # Assess Risk Level
        # High: Reaches >= 3 pipelines or >= 2 datasets
        # Medium: Reaches 1-2 pipelines or 1 dataset
        # Low: Reaches 0 downstream nodes (leaf)
        if len(affected_pipelines) >= 2 or len(affected_datasets) >= 2 or len(affected_node_ids) >= 4:
            risk_level = "High"
            summary = f"CRITICAL IMPACT: Modifying {target_node.name} affects {len(affected_datasets)} downstream datasets across {len(affected_pipelines)} production pipelines."
        elif len(affected_node_ids) > 0:
            risk_level = "Medium"
            summary = f"MODERATE IMPACT: Modifying {target_node.name} affects {len(affected_node_ids)} downstream assets."
        else:
            risk_level = "Low"
            summary = f"LOW IMPACT: {target_node.name} has no downstream dependencies. Safe to modify or decommission."

        return ImpactAnalysisResponse(
            target_node_id=target_node.id,
            target_node_name=target_node.name,
            target_column=column_name,
            risk_level=risk_level,
            summary_message=summary,
            affected_pipelines_count=len(affected_pipelines),
            affected_datasets_count=len(affected_datasets),
            affected_columns_count=len(affected_cols),
            affected_nodes=affected_nodes_meta,
            impact_graph=downstream_graph
        )
