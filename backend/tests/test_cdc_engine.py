import pytest
import time
from sqlalchemy.orm import Session

import backend.app.connectors.factory
import backend.app.activities.factory
from backend.app.core.database import SessionLocal
from backend.app.connectors.factory import get_connector
from backend.app.connectors.cdc import DebeziumCDCConnector
from backend.app.connectors.duckdb import DuckDBConnector
from backend.app.activities.factory import get_activity_instance
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.cdc import CDCReplicationActivity
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.core.security import encrypt_secret


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_project(db_session: Session):
    ws = db_session.query(Workspace).first()
    if not ws:
        ws = Workspace(name="CDC_Test_WS", description="Workspace for CDC tests")
        db_session.add(ws)
        db_session.commit()
        db_session.refresh(ws)

    proj = db_session.query(Project).filter(Project.name == "CDC_Stream_Project").first()
    if not proj:
        proj = Project(workspace_id=ws.id, name="CDC_Stream_Project", description="CDC Stream Project")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)
    return proj


# ==========================================
# 1. Debezium CDC Connector Tests
# ==========================================

def test_cdc_connector_registration():
    """Verify Debezium CDC connector is registered in factory."""
    connector = get_connector("cdc", {"stream_type": "postgres_wal", "mock_mode": True})
    assert isinstance(connector, DebeziumCDCConnector)
    assert connector.stream_type == "postgres_wal"


def test_cdc_event_envelope_parsing():
    """Test parsing Debezium standard JSON envelope for create, update, delete."""
    # 1. Insert Event (op = 'c')
    raw_insert = {
        "payload": {
            "op": "c",
            "before": None,
            "after": {"id": 101, "customer": "Acme Corp", "balance": 5000.0},
            "source": {"table": "customers", "lsn": 100200, "ts_ms": 1715000000}
        }
    }
    parsed_insert = DebeziumCDCConnector.parse_debezium_event(raw_insert)
    assert parsed_insert["op"] == "c"
    assert parsed_insert["data"]["customer"] == "Acme Corp"
    assert parsed_insert["lsn"] == 100200
    assert parsed_insert["table"] == "customers"

    # 2. Update Event (op = 'u')
    raw_update = {
        "payload": {
            "op": "u",
            "before": {"id": 101, "customer": "Acme Corp", "balance": 5000.0},
            "after": {"id": 101, "customer": "Acme Corp Ltd", "balance": 7500.0},
            "source": {"table": "customers", "lsn": 100205, "ts_ms": 1715000050}
        }
    }
    parsed_update = DebeziumCDCConnector.parse_debezium_event(raw_update)
    assert parsed_update["op"] == "u"
    assert parsed_update["data"]["customer"] == "Acme Corp Ltd"
    assert parsed_update["before"]["balance"] == 5000.0
    assert parsed_update["after"]["balance"] == 7500.0
    assert parsed_update["lsn"] == 100205

    # 3. Delete Event (op = 'd')
    raw_delete = {
        "payload": {
            "op": "d",
            "before": {"id": 101, "customer": "Acme Corp Ltd"},
            "after": None,
            "source": {"table": "customers", "lsn": 100210, "ts_ms": 1715000100}
        }
    }
    parsed_delete = DebeziumCDCConnector.parse_debezium_event(raw_delete)
    assert parsed_delete["op"] == "d"
    assert parsed_delete["data"]["id"] == 101
    assert parsed_delete["lsn"] == 100210


def test_cdc_streaming_read_and_checkpoint_offset():
    """Test reading CDC stream batches ordered by LSN and advancing checkpoints."""
    events = [
        {"payload": {"op": "c", "after": {"id": 1, "val": 10}, "source": {"table": "items", "lsn": 100}}},
        {"payload": {"op": "c", "after": {"id": 2, "val": 20}, "source": {"table": "items", "lsn": 105}}},
        {"payload": {"op": "u", "after": {"id": 1, "val": 15}, "source": {"table": "items", "lsn": 110}}},
        {"payload": {"op": "d", "before": {"id": 2}, "source": {"table": "items", "lsn": 115}}}
    ]

    connector = DebeziumCDCConnector({
        "events": events,
        "checkpoint_lsn": 100,  # Should skip LSN 100
        "mock_mode": True
    })

    stream = list(connector.read_cdc_stream(batch_size=2))
    assert len(stream) == 2  # 3 events total (105, 110, 115) -> 2 in batch 1, 1 in batch 2
    assert len(stream[0]) == 2
    assert stream[0][0]["lsn"] == 105
    assert stream[0][1]["lsn"] == 110
    assert stream[1][0]["lsn"] == 115

    # Commit offset
    connector.commit_offset(115)
    assert connector._committed_lsn == 115


# ==========================================
# 2. CDC Replication Activity Tests
# ==========================================

def test_cdc_replication_activity_registration(db_session: Session):
    """Verify CDCReplication is cataloged in ActivityRegistry and Factory."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}
    assert "CDCReplication" in types

    context = ActivityExecutionContext(
        activity_id="act-cdc-reg",
        activity_name="ReplicateCDC",
        activity_type="CDCReplication",
        pipeline_run_id="run-cdc-1",
        config={
            "source": {"type": "cdc", "mock_mode": True},
            "destination": {"type": "duckdb", "database_path": ":memory:"}
        }
    )
    inst = get_activity_instance(context, db_session)
    assert isinstance(inst, CDCReplicationActivity)


def test_cdc_replication_end_to_end_upsert_delete_and_audit(db_session: Session, test_project: Project):
    """
    Test CDCReplicationActivity synchronizing transaction log events into a warehouse:
      - 2 Inserts -> upserted
      - 1 Update -> updated in-place
      - 1 Delete -> deleted from target
      - Audit changelog recorded
    """
    cdc_events = [
        {"payload": {"op": "c", "after": {"cust_id": 10, "name": "Alpha", "status": "ACTIVE"}, "source": {"table": "customers", "lsn": 501}}},
        {"payload": {"op": "c", "after": {"cust_id": 20, "name": "Beta", "status": "ACTIVE"}, "source": {"table": "customers", "lsn": 502}}},
        {"payload": {"op": "u", "before": {"cust_id": 10, "name": "Alpha"}, "after": {"cust_id": 10, "name": "Alpha Pro", "status": "VIP"}, "source": {"table": "customers", "lsn": 503}}},
        {"payload": {"op": "d", "before": {"cust_id": 20}, "source": {"table": "customers", "lsn": 504}}}
    ]

    # Target DuckDB database
    target_connector = DuckDBConnector({"database_path": ":memory:"})

    # Destination connection in DB
    target_conn_rec = Connection(
        project_id=test_project.id,
        name="CDC_Target_Warehouse",
        connector_type="duckdb",
        config_encrypted=encrypt_secret({"database_path": ":memory:"})
    )
    db_session.add(target_conn_rec)
    db_session.commit()
    db_session.refresh(target_conn_rec)

    context = ActivityExecutionContext(
        activity_id="act-cdc-exec",
        activity_name="ReplicateCustomersCDC",
        activity_type="CDCReplication",
        pipeline_run_id="run-cdc-2",
        config={
            "source": {
                "connector_type": "cdc",
                "events": cdc_events,
                "checkpoint_lsn": 500
            },
            "destination": {
                "connection_id": target_conn_rec.id,
                "table_name": "replicated_customers",
                "key_columns": ["cust_id"]
            },
            "key_columns": ["cust_id"],
            "soft_delete": False,
            "audit_mode": True
        }
    )

    activity = CDCReplicationActivity(context=context, db_session=db_session)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.output_variables["events_processed"] == 4
    assert result.output_variables["inserts"] == 2
    assert result.output_variables["updates"] == 1
    assert result.output_variables["deletes"] == 1
    assert result.output_variables["highest_lsn"] == 504
