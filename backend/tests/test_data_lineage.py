import pytest
import uuid
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.models.dataset import Dataset
from backend.app.models.dataflow import DataFlow
from backend.app.models.lineage import LineageNode, LineageEdge, ColumnLineage
from backend.app.services.lineage_service import LineageService
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_setup(db_session: Session):
    uid = str(uuid.uuid4())[:8]
    user = User(
        id=str(uuid.uuid4()),
        email=f"lineage_admin_{uid}@dataflow.enterprise",
        full_name="Lineage Test Admin",
        hashed_password=get_password_hash("TestPass123!"),
        role="Admin",
        is_active=True
    )
    ws = Workspace(id=str(uuid.uuid4()), name=f"Lineage WS {uid}")
    proj = Project(id=str(uuid.uuid4()), workspace_id=ws.id, name=f"Lineage Project {uid}")
    
    conn = Connection(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Lineage Postgres DW",
        connector_type="postgres",
        config_encrypted="test_encrypted"
    )

    db_session.add_all([user, ws, proj, conn])
    db_session.commit()

    token = create_access_token({"sub": user.id, "role": user.role})
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    return {
        "user": user,
        "workspace": ws,
        "project": proj,
        "connection": conn,
        "client": client,
        "token": token
    }


def test_lineage_extraction_from_copy_data(db_session: Session, test_setup):
    """Verifies lineage node, edge, and column-level mapping extraction from Copy Data."""
    proj = test_setup["project"]
    conn = test_setup["connection"]

    # 1. Create Pipeline with CopyData activity
    pipe = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Ingest_Sales_Orders",
        definition_json={
            "activities": [
                {
                    "name": "Copy_Orders_To_Bronze",
                    "type": "CopyData",
                    "config": {
                        "source": {
                            "connection_id": conn.id,
                            "table_name": "raw_orders",
                            "schema_name": "erp"
                        },
                        "destination": {
                            "connection_id": conn.id,
                            "container": "corp-datalake",
                            "path": "bronze/orders.parquet"
                        },
                        "column_mappings": [
                            {"source": "order_id", "destination": "id"},
                            {"source": "customer_id", "destination": "cust_id"},
                            {"source": "order_total", "destination": "amount"}
                        ]
                    }
                }
            ]
        }
    )
    db_session.add(pipe)
    db_session.commit()

    # 2. Extract lineage
    n, e, c = LineageService.extract_from_copy_data(
        db_session,
        proj.id,
        pipe,
        pipe.definition_json["activities"][0]
    )

    assert n >= 2
    assert e >= 1
    assert c == 3

    # 3. Verify Nodes
    src_node = db_session.query(LineageNode).filter(
        LineageNode.project_id == proj.id,
        LineageNode.qualified_name == f"postgres://erp.raw_orders"
    ).first()
    assert src_node is not None
    assert src_node.node_type == "Table"

    dst_node = db_session.query(LineageNode).filter(
        LineageNode.project_id == proj.id,
        LineageNode.qualified_name == "postgres://corp-datalake/bronze/orders.parquet"
    ).first()
    assert dst_node is not None
    assert dst_node.node_type == "StorageFile"

    # 4. Verify Edge & Column Lineages
    edge = db_session.query(LineageEdge).filter(
        LineageEdge.source_node_id == src_node.id,
        LineageEdge.target_node_id == dst_node.id
    ).first()
    assert edge is not None
    assert edge.confidence == "exact"
    assert edge.pipeline_id == pipe.id

    cols = db_session.query(ColumnLineage).filter(ColumnLineage.edge_id == edge.id).all()
    assert len(cols) == 3
    col_dict = {col.source_column: col.target_column for col in cols}
    assert col_dict["order_id"] == "id"
    assert col_dict["customer_id"] == "cust_id"
    assert col_dict["order_total"] == "amount"


def test_lineage_extraction_with_reusable_datasets(db_session: Session, test_setup):
    """Verifies dataset-level lineage linkages when Copy Data references reusable datasets."""
    proj = test_setup["project"]
    conn = test_setup["connection"]

    # 1. Create source and sink datasets
    ds_src = Dataset(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        connection_id=conn.id,
        name="Customer_Bronze_DS",
        dataset_type="RelationalTable",
        location_config={"table": "customers", "schema": "crm"},
        schema_definition=[
            {"name": "cust_id", "type": "INTEGER"},
            {"name": "cust_name", "type": "VARCHAR"}
        ]
    )
    ds_dst = Dataset(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        connection_id=conn.id,
        name="Customer_Silver_DS",
        dataset_type="AzureBlob",
        location_config={"container": "silver", "path": "customers.parquet"},
        schema_definition=[
            {"name": "cust_id", "type": "INTEGER"},
            {"name": "cust_name", "type": "VARCHAR"}
        ]
    )
    db_session.add_all([ds_src, ds_dst])
    db_session.commit()

    # 2. Pipeline referencing both datasets
    pipe = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Sync_Customer_Datasets",
        definition_json={
            "activities": [
                {
                    "name": "Copy_Customer_Bronze_To_Silver",
                    "type": "CopyData",
                    "config": {
                        "source": {"dataset_id": ds_src.id},
                        "destination": {"dataset_id": ds_dst.id},
                        "column_mappings": [
                            {"source": "cust_id", "destination": "cust_id"},
                            {"source": "cust_name", "destination": "cust_name"}
                        ]
                    }
                }
            ]
        }
    )
    db_session.add(pipe)
    db_session.commit()

    # 3. Extract lineage
    n, e, c = LineageService.extract_from_copy_data(
        db_session,
        proj.id,
        pipe,
        pipe.definition_json["activities"][0]
    )

    src_node = db_session.query(LineageNode).filter(LineageNode.dataset_id == ds_src.id).first()
    dst_node = db_session.query(LineageNode).filter(LineageNode.dataset_id == ds_dst.id).first()
    assert src_node is not None
    assert dst_node is not None
    assert src_node.node_type == "Dataset"
    assert dst_node.node_type == "Dataset"

    edge = db_session.query(LineageEdge).filter(
        LineageEdge.source_node_id == src_node.id,
        LineageEdge.target_node_id == dst_node.id
    ).first()
    assert edge is not None


def test_lineage_extraction_from_dataflow_transformations(db_session: Session, test_setup):
    """Verifies transformation lineage and derived expressions extracted from DataFlow DAGs."""
    proj = test_setup["project"]

    df = DataFlow(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Enrich_User_Profiles",
        graph_json={
            "nodes": [
                {
                    "id": "src_1",
                    "type": "source",
                    "data": {
                        "label": "Raw Users Source",
                        "connector_type": "postgres",
                        "schema": ["first_name", "last_name", "email"]
                    }
                },
                {
                    "id": "derive_1",
                    "type": "derived_column",
                    "data": {
                        "label": "Add Full Name",
                        "derivations": [
                            {"column": "full_name", "expression": "CONCAT(first_name, ' ', last_name)"}
                        ]
                    }
                },
                {
                    "id": "sink_1",
                    "type": "sink",
                    "data": {
                        "label": "Enriched Users Sink",
                        "connector_type": "azure_blob"
                    }
                }
            ],
            "edges": [
                {"source": "src_1", "target": "derive_1"},
                {"source": "derive_1", "target": "sink_1"}
            ]
        }
    )
    db_session.add(df)
    db_session.commit()

    n, e, c = LineageService.extract_from_dataflow(db_session, proj.id, None, df)
    assert n >= 3
    assert e >= 2
    assert c >= 1

    # Check that derived column captured expression
    col = db_session.query(ColumnLineage).filter(
        ColumnLineage.target_column == "full_name"
    ).first()
    assert col is not None
    assert col.transformation_type == "derived"
    assert "CONCAT" in col.expression


def test_lineage_graph_traversal_upstream_and_downstream(db_session: Session, test_setup):
    """Verifies multi-hop upstream and downstream graph traversal from a focal root node."""
    proj = test_setup["project"]

    # Build 3-tier chain: Node A -> Node B -> Node C
    node_a = LineageService.get_or_create_node(
        db_session, proj.id, "Table", "Tier_A_Raw", f"test://tier_a_{uuid.uuid4()}"
    )
    node_b = LineageService.get_or_create_node(
        db_session, proj.id, "Dataset", "Tier_B_Silver", f"test://tier_b_{uuid.uuid4()}"
    )
    node_c = LineageService.get_or_create_node(
        db_session, proj.id, "Table", "Tier_C_Gold", f"test://tier_c_{uuid.uuid4()}"
    )

    edge_ab = LineageEdge(
        id=str(uuid.uuid4()), project_id=proj.id,
        source_node_id=node_a.id, target_node_id=node_b.id,
        edge_type="FlowsTo", confidence="exact"
    )
    edge_bc = LineageEdge(
        id=str(uuid.uuid4()), project_id=proj.id,
        source_node_id=node_b.id, target_node_id=node_c.id,
        edge_type="FlowsTo", confidence="exact"
    )
    db_session.add_all([edge_ab, edge_bc])
    db_session.commit()

    # 1. Traverse Upstream from Node B -> should only find Node A and Node B
    up_graph = LineageService.get_lineage_graph(
        db_session, proj.id, root_node_id=node_b.id, direction="upstream", depth=5
    )
    node_ids = {n.id for n in up_graph.nodes}
    assert node_b.id in node_ids
    assert node_a.id in node_ids
    assert node_c.id not in node_ids

    # 2. Traverse Downstream from Node B -> should only find Node B and Node C
    down_graph = LineageService.get_lineage_graph(
        db_session, proj.id, root_node_id=node_b.id, direction="downstream", depth=5
    )
    down_ids = {n.id for n in down_graph.nodes}
    assert node_b.id in down_ids
    assert node_c.id in down_ids
    assert node_a.id not in down_ids

    # 3. Traverse Both from Node B -> should find all 3
    both_graph = LineageService.get_lineage_graph(
        db_session, proj.id, root_node_id=node_b.id, direction="both", depth=5
    )
    both_ids = {n.id for n in both_graph.nodes}
    assert node_a.id in both_ids
    assert node_b.id in both_ids
    assert node_c.id in both_ids


def test_column_lineage_tracing_and_impact_analysis(db_session: Session, test_setup):
    """Verifies column-level lineage back-tracing and downstream blast radius risk assessment."""
    proj = test_setup["project"]

    # Create root source table with column "order_amt"
    root_node = LineageService.get_or_create_node(
        db_session, proj.id, "Table", "ERP_Invoices", f"test://erp_invoices_{uuid.uuid4()}"
    )
    mid_node = LineageService.get_or_create_node(
        db_session, proj.id, "Dataset", "Clean_Invoices_DS", f"test://clean_invoices_{uuid.uuid4()}"
    )
    sink_node = LineageService.get_or_create_node(
        db_session, proj.id, "Table", "Finance_Fact_Invoices", f"test://fact_invoices_{uuid.uuid4()}"
    )

    e1 = LineageEdge(
        id=str(uuid.uuid4()), project_id=proj.id,
        source_node_id=root_node.id, target_node_id=mid_node.id,
        edge_type="FlowsTo", confidence="exact"
    )
    e2 = LineageEdge(
        id=str(uuid.uuid4()), project_id=proj.id,
        source_node_id=mid_node.id, target_node_id=sink_node.id,
        edge_type="FlowsTo", confidence="derived"
    )
    db_session.add_all([e1, e2])
    db_session.flush()

    c1 = ColumnLineage(
        id=str(uuid.uuid4()), edge_id=e1.id,
        source_column="order_amt", target_column="net_amt",
        transformation_type="direct", expression="order_amt", confidence="exact"
    )
    c2 = ColumnLineage(
        id=str(uuid.uuid4()), edge_id=e2.id,
        source_column="net_amt", target_column="total_revenue",
        transformation_type="derived", expression="SUM(net_amt)", confidence="derived"
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    # 1. Trace column "total_revenue" upstream from sink_node
    trace = LineageService.get_column_lineage_trace(
        db_session, proj.id, node_id=sink_node.id, column_name="total_revenue", direction="upstream"
    )
    assert trace.column_name == "total_revenue"
    assert len(trace.trace_steps) >= 2
    # Verify origin step references "order_amt"
    orig_step = next(s for s in trace.trace_steps if s.source_node_id == root_node.id)
    assert orig_step.source_column == "order_amt"

    # 2. Run Impact Analysis on root_node
    impact = LineageService.analyze_impact(
        db_session, proj.id, node_id=root_node.id, column_name="order_amt"
    )
    assert impact.target_node_id == root_node.id
    assert impact.risk_level in ["Medium", "High"]
    assert len(impact.affected_nodes) >= 2
    assert impact.affected_columns_count >= 1
    assert "Clean_Invoices_DS" in [n["name"] for n in impact.affected_nodes]

    # 3. Run Impact Analysis on leaf sink_node -> Risk must be Low (no downstream dependents)
    sink_impact = LineageService.analyze_impact(
        db_session, proj.id, node_id=sink_node.id
    )
    assert sink_impact.risk_level == "Low"
    assert len(sink_impact.affected_nodes) == 0


def test_lineage_rest_api_endpoints(test_setup):
    """Verifies all FastAPI REST endpoints under /api/v1/lineage."""
    client: TestClient = test_setup["client"]
    proj = test_setup["project"]

    # 1. Trigger extraction
    res = client.post(f"/api/v1/lineage/extract?project_id={proj.id}")
    assert res.status_code == 200
    extract_data = res.json()
    assert extract_data["status"] == "Succeeded"
    assert "nodes_discovered" in extract_data

    # 2. Get full graph
    res = client.get(f"/api/v1/lineage/graph?project_id={proj.id}")
    assert res.status_code == 200
    graph = res.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert "column_lineage" in graph
    assert len(graph["nodes"]) > 0

    first_node_id = graph["nodes"][0]["id"]

    # 3. List nodes
    res = client.get(f"/api/v1/lineage/nodes?project_id={proj.id}")
    assert res.status_code == 200
    nodes = res.json()
    assert len(nodes) > 0

    # 4. Impact Analysis endpoint
    res = client.post(
        f"/api/v1/lineage/impact-analysis?project_id={proj.id}",
        json={"node_id": first_node_id}
    )
    assert res.status_code == 200
    imp = res.json()
    assert "risk_level" in imp
    assert "summary_message" in imp
    assert "impact_graph" in imp

    # 5. Export endpoint
    res = client.get(f"/api/v1/lineage/export?project_id={proj.id}")
    assert res.status_code == 200
    export_doc = res.json()
    assert export_doc["project_id"] == proj.id
    assert "nodes" in export_doc
