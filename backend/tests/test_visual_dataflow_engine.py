import pytest
import tempfile
import os
import polars as pl
from sqlalchemy.orm import Session

# Import factory to register ExecuteDataFlowActivity
import backend.app.activities.factory
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.models.workspace import Workspace, Project
from backend.app.models.dataflow import DataFlow
from backend.app.dataflow.engine import DataFlowEngine
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.data_flow import ExecuteDataFlowActivity


@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    ws = db.query(Workspace).first()
    ws_id = ws.id if ws else "ws_test"
    proj = db.query(Project).filter(Project.name == "DataFlow_Test_Project").first()
    if not proj:
        proj = Project(workspace_id=ws_id, name="DataFlow_Test_Project", description="Phase 6 Data Flows")
        db.add(proj)
        db.commit()
        db.refresh(proj)
    yield {"project_id": proj.id, "db": db}
    db.close()


def test_registry_contains_dataflow_activity():
    """Verify that ExecuteDataFlow is registered in ActivityRegistry."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}

    assert "ExecuteDataFlow" in types
    meta = activity_registry.get_metadata("ExecuteDataFlow")
    assert meta.category == "Move & Transform"
    assert "dataflow" in meta.tags[0].lower()


def test_dataflow_stream_linear_transformations():
    """Test Source -> Filter -> DerivedColumn -> Select -> Sort -> Sink."""
    sample_records = [
        {"order_id": 101, "customer": "alice", "price": 50, "qty": 2, "status": "COMPLETED"},
        {"order_id": 102, "customer": "bob", "price": 100, "qty": 1, "status": "CANCELLED"},
        {"order_id": 103, "customer": "charlie", "price": 25, "qty": 4, "status": "COMPLETED"},
        {"order_id": 104, "customer": "david", "price": 10, "qty": 10, "status": "COMPLETED"}
    ]

    graph = {
        "nodes": [
            {
                "id": "src",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": sample_records}}
            },
            {
                "id": "filt",
                "type": "dataFlowNode",
                "data": {"operatorType": "Filter", "config": {"column": "status", "operator": "==", "value": "COMPLETED"}}
            },
            {
                "id": "derived",
                "type": "dataFlowNode",
                "data": {
                    "operatorType": "DerivedColumn",
                    "config": {
                        "derived_columns": [
                            {"column_name": "total_amount", "type": "multiply", "col1": "price", "col2": "qty"},
                            {"column_name": "customer_upper", "type": "uppercase", "input_column": "customer"}
                        ]
                    }
                }
            },
            {
                "id": "sel",
                "type": "dataFlowNode",
                "data": {
                    "operatorType": "Select",
                    "config": {
                        "columns": ["order_id", "customer_upper", "total_amount"],
                        "rename_columns": {"customer_upper": "customer_name"}
                    }
                }
            },
            {
                "id": "sort",
                "type": "dataFlowNode",
                "data": {"operatorType": "Sort", "config": {"columns": ["total_amount"], "descending": True}}
            },
            {
                "id": "snk",
                "type": "dataFlowNode",
                "data": {"operatorType": "Sink", "config": {}}
            }
        ],
        "edges": [
            {"id": "e1", "source": "src", "target": "filt"},
            {"id": "e2", "source": "filt", "target": "derived"},
            {"id": "e3", "source": "derived", "target": "sel"},
            {"id": "e4", "source": "sel", "target": "sort"},
            {"id": "e5", "source": "sort", "target": "snk"}
        ]
    }

    engine = DataFlowEngine()
    result = engine.execute_graph(graph)

    assert result.status == "Succeeded"
    assert result.total_rows_read == 4
    assert result.total_rows_written == 3  # Only 3 completed orders

    sink_preview = result.node_outputs["snk"]
    rows = sink_preview["preview_rows"]
    assert len(rows) == 3
    # Check descending order by total_amount (100, 100, 100)
    assert rows[0]["customer_name"] in ("ALICE", "CHARLIE", "DAVID")
    assert rows[0]["total_amount"] == 100
    assert "status" not in rows[0]  # Dropped in Select step


def test_dataflow_multi_stream_join():
    """Test two input streams joined on key (Orders JOIN Customers)."""
    orders_data = [
        {"order_id": 1, "cust_id": 10, "product": "Laptop"},
        {"order_id": 2, "cust_id": 20, "product": "Phone"},
        {"order_id": 3, "cust_id": 30, "product": "Monitor"}
    ]
    customers_data = [
        {"cust_id": 10, "cust_name": "Acme Corp", "tier": "Enterprise"},
        {"cust_id": 20, "cust_name": "Globex", "tier": "Standard"}
    ]

    graph = {
        "nodes": [
            {
                "id": "src_orders",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": orders_data}}
            },
            {
                "id": "src_customers",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": customers_data}}
            },
            {
                "id": "join_step",
                "type": "dataFlowNode",
                "data": {
                    "operatorType": "Join",
                    "config": {"join_type": "inner", "left_on": "cust_id", "right_on": "cust_id"}
                }
            },
            {
                "id": "sink_step",
                "type": "dataFlowNode",
                "data": {"operatorType": "Sink", "config": {}}
            }
        ],
        "edges": [
            {"id": "e_ord", "source": "src_orders", "target": "join_step"},
            {"id": "e_cust", "source": "src_customers", "target": "join_step"},
            {"id": "e_out", "source": "join_step", "target": "sink_step"}
        ]
    }

    engine = DataFlowEngine()
    result = engine.execute_graph(graph)

    assert result.status == "Succeeded"
    assert result.total_rows_read == 5
    assert result.total_rows_written == 2  # Only orders 1 and 2 match cust_id 10 and 20

    rows = result.node_outputs["sink_step"]["preview_rows"]
    assert len(rows) == 2
    assert rows[0]["cust_name"] in ("Acme Corp", "Globex")
    assert "tier" in rows[0]
    assert "product" in rows[0]


def test_dataflow_aggregate_and_window():
    """Test group-by aggregation and window row numbering."""
    sales_data = [
        {"region": "North", "rep": "John", "amount": 100},
        {"region": "North", "rep": "Jane", "amount": 200},
        {"region": "South", "rep": "Bob", "amount": 150},
        {"region": "South", "rep": "Alice", "amount": 250}
    ]

    # Test 1: Aggregation
    graph_agg = {
        "nodes": [
            {
                "id": "src",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": sales_data}}
            },
            {
                "id": "agg",
                "type": "dataFlowNode",
                "data": {
                    "operatorType": "Aggregate",
                    "config": {
                        "group_by": ["region"],
                        "aggregates": [
                            {"function": "sum", "column": "amount", "alias": "total_sales"},
                            {"function": "count", "column": "rep", "alias": "rep_count"}
                        ]
                    }
                }
            }
        ],
        "edges": [{"id": "e1", "source": "src", "target": "agg"}]
    }

    engine = DataFlowEngine()
    res_agg = engine.execute_graph(graph_agg)
    assert res_agg.status == "Succeeded"
    agg_rows = res_agg.node_outputs["agg"]["preview_rows"]
    assert len(agg_rows) == 2
    north = [r for r in agg_rows if r["region"] == "North"][0]
    south = [r for r in agg_rows if r["region"] == "South"][0]
    assert north["total_sales"] == 300
    assert south["total_sales"] == 400


def test_dataflow_surrogate_key_and_union():
    """Test Union of two streams and SurrogateKey generation."""
    stream_a = [{"item": "A1"}, {"item": "A2"}]
    stream_b = [{"item": "B1"}, {"item": "B2"}]

    graph = {
        "nodes": [
            {
                "id": "src_a",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": stream_a}}
            },
            {
                "id": "src_b",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": stream_b}}
            },
            {
                "id": "union_step",
                "type": "dataFlowNode",
                "data": {"operatorType": "Union", "config": {}}
            },
            {
                "id": "sk_step",
                "type": "dataFlowNode",
                "data": {"operatorType": "SurrogateKey", "config": {"key_name": "row_id", "start_value": 100}}
            }
        ],
        "edges": [
            {"id": "e1", "source": "src_a", "target": "union_step"},
            {"id": "e2", "source": "src_b", "target": "union_step"},
            {"id": "e3", "source": "union_step", "target": "sk_step"}
        ]
    }

    engine = DataFlowEngine()
    result = engine.execute_graph(graph)

    assert result.status == "Succeeded"
    rows = result.node_outputs["sk_step"]["preview_rows"]
    assert len(rows) == 4
    # Sequential keys starting from 100
    keys = [r["row_id"] for r in rows]
    assert keys == [100, 101, 102, 103]


def test_execute_dataflow_pipeline_activity(setup_db):
    """Test pipeline activity ExecuteDataFlowActivity invoking a DataFlow."""
    db: Session = setup_db["db"]
    proj_id = setup_db["project_id"]

    # Persist a DataFlow record in database
    sample_data = [{"val": 10}, {"val": 20}, {"val": 30}]
    graph = {
        "nodes": [
            {
                "id": "s1",
                "type": "dataFlowNode",
                "data": {"operatorType": "Source", "config": {"inline_data": sample_data}}
            },
            {
                "id": "sink1",
                "type": "dataFlowNode",
                "data": {"operatorType": "Sink", "config": {}}
            }
        ],
        "edges": [{"id": "e1", "source": "s1", "target": "sink1"}]
    }

    df = DataFlow(
        project_id=proj_id,
        name="ETL_Sample_Transform",
        graph_json=graph
    )
    db.add(df)
    db.commit()
    db.refresh(df)

    context = ActivityExecutionContext(
        activity_id="act-df-1",
        activity_name="ExecuteETLFlow",
        activity_type="ExecuteDataFlow",
        pipeline_run_id="run-df-1",
        config={
            "dataflow_id": df.id
        }
    )

    activity = ExecuteDataFlowActivity(context=context, db_session=db)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.rows_read == 3
    assert result.rows_written == 3
    assert result.output_variables["total_rows_read"] == 3
    assert result.output_variables["total_rows_written"] == 3
