import pytest
import time
from sqlalchemy.orm import Session

import backend.app.connectors.factory
import backend.app.activities.factory
from backend.app.core.database import SessionLocal
from backend.app.connectors.factory import get_connector
from backend.app.connectors.reverse_etl import ReverseETLConnector
from backend.app.activities.factory import get_activity_instance
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.reverse_etl import ReverseETLActivity
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
        ws = Workspace(name="ReverseETL_Test_WS", description="Workspace for Reverse ETL tests")
        db_session.add(ws)
        db_session.commit()
        db_session.refresh(ws)

    proj = db_session.query(Project).filter(Project.name == "ReverseETL_Project").first()
    if not proj:
        proj = Project(workspace_id=ws.id, name="ReverseETL_Project", description="Reverse ETL Project")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)
    return proj


# ==========================================
# 1. Reverse ETL Connector Tests
# ==========================================

def test_reverse_etl_connector_registration():
    """Verify Reverse ETL connector is registered in factory."""
    conn = get_connector("reverse_etl", {"destination_type": "salesforce", "mock_mode": True})
    assert isinstance(conn, ReverseETLConnector)
    assert conn.destination_type == "salesforce"

    conn_sf = get_connector("salesforce", {"mock_mode": True})
    assert isinstance(conn_sf, ReverseETLConnector)

    conn_hub = get_connector("hubspot", {"mock_mode": True})
    assert isinstance(conn_hub, ReverseETLConnector)

    conn_slack = get_connector("slack", {"mock_mode": True})
    assert isinstance(conn_slack, ReverseETLConnector)


def test_reverse_etl_connection_tests():
    """Test connection validation across destinations."""
    # Salesforce
    sf_conn = ReverseETLConnector({"destination_type": "salesforce", "mock_mode": True})
    res_sf = sf_conn.test_connection()
    assert res_sf.success is True
    assert "SALESFORCE" in res_sf.message

    # HubSpot
    hub_conn = ReverseETLConnector({"destination_type": "hubspot", "mock_mode": True})
    res_hub = hub_conn.test_connection()
    assert res_hub.success is True
    assert "HUBSPOT" in res_hub.message

    # Slack
    slack_conn = ReverseETLConnector({"destination_type": "slack", "mock_mode": True})
    res_slack = slack_conn.test_connection()
    assert res_slack.success is True
    assert "SLACK" in res_slack.message


def test_salesforce_sync_with_field_mappings():
    """Test syncing analytical gold models to Salesforce with field mappings."""
    connector = ReverseETLConnector({
        "destination_type": "salesforce",
        "mock_mode": True
    })

    analytical_records = [
        {"account_uuid": "A001", "firm_name": "Acme Global", "total_arr": 150000.0, "vip": True},
        {"account_uuid": "A002", "firm_name": "Globex Corp", "total_arr": 85000.0, "vip": False}
    ]

    field_mappings = [
        {"source": "account_uuid", "destination": "External_Id__c"},
        {"source": "firm_name", "destination": "Name"},
        {"source": "total_arr", "destination": "AnnualRevenue"}
    ]

    res = connector.sync_batch(
        records=analytical_records,
        object_name="Account",
        sync_mode="upsert",
        external_id_field="External_Id__c",
        field_mappings=field_mappings
    )

    assert res["synced"] == 2
    assert res["failed"] == 0
    assert len(connector._mock_synced_records) == 2
    assert connector._mock_synced_records[0]["External_Id__c"] == "A001"
    assert connector._mock_synced_records[0]["Name"] == "Acme Global"
    assert connector._mock_synced_records[0]["AnnualRevenue"] == 150000.0


def test_hubspot_crm_batch_upsert():
    """Test syncing contact records to HubSpot CRM."""
    connector = ReverseETLConnector({
        "destination_type": "hubspot",
        "mock_mode": True
    })

    contacts = [
        {"email": "john.doe@example.com", "firstname": "John", "lastname": "Doe", "score": 98},
        {"email": "jane.smith@example.com", "firstname": "Jane", "lastname": "Smith", "score": 95}
    ]

    res = connector.sync_batch(
        records=contacts,
        object_name="contacts",
        sync_mode="upsert",
        external_id_field="email"
    )

    assert res["synced"] == 2
    assert res["failed"] == 0


def test_slack_operational_alerts():
    """Test dispatching KPI alert cards to Slack channel."""
    connector = ReverseETLConnector({
        "destination_type": "slack",
        "channel": "#revops-alerts",
        "mock_mode": True
    })

    alerts = [
        {"metric": "ARR Churn", "threshold": 0.02, "current": 0.05, "severity": "CRITICAL"}
    ]

    res = connector.sync_batch(records=alerts, object_name="#revops-alerts")
    assert res["synced"] == 1
    assert res["failed"] == 0


# ==========================================
# 2. Reverse ETL Activity Tests
# ==========================================

def test_reverse_etl_activity_registration(db_session: Session):
    """Verify ReverseETL is cataloged in ActivityRegistry and Factory."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}
    assert "ReverseETL" in types

    context = ActivityExecutionContext(
        activity_id="act-rev-reg",
        activity_name="SyncToSalesforce",
        activity_type="ReverseETL",
        pipeline_run_id="run-rev-1",
        config={
            "destination": {"destination_type": "salesforce", "mock_mode": True}
        }
    )
    inst = get_activity_instance(context, db_session)
    assert isinstance(inst, ReverseETLActivity)


def test_reverse_etl_activity_execution_flow(db_session: Session, test_project: Project):
    """
    Test ReverseETLActivity dispatching warehouse records into operational SaaS:
      - Pulls 3 customer records
      - Maps analytical fields to Salesforce Contact fields
      - Dispatches in batches of 2
    """
    sf_conn_rec = Connection(
        project_id=test_project.id,
        name="Salesforce_RevOps",
        connector_type="salesforce",
        config_encrypted=encrypt_secret({
            "destination_type": "salesforce",
            "instance_url": "https://mock.salesforce.com",
            "access_token": "mock_token_123",
            "mock_mode": True
        })
    )
    db_session.add(sf_conn_rec)
    db_session.commit()
    db_session.refresh(sf_conn_rec)

    raw_analytics = [
        {"cid": "C101", "email": "ceo@acme.com", "ltv": 250000.0},
        {"cid": "C102", "email": "vp@globex.com", "ltv": 120000.0},
        {"cid": "C103", "email": "cto@initech.com", "ltv": 95000.0}
    ]

    field_mappings = [
        {"source": "cid", "destination": "External_Id__c"},
        {"source": "email", "destination": "Email"},
        {"source": "ltv", "destination": "Customer_LTV__c"}
    ]

    context = ActivityExecutionContext(
        activity_id="act-rev-exec",
        activity_name="PushLTVToSalesforce",
        activity_type="ReverseETL",
        pipeline_run_id="run-rev-2",
        config={
            "source": {"records": raw_analytics},
            "destination": {
                "connection_id": sf_conn_rec.id,
                "target_object": "Contact",
                "external_id_field": "External_Id__c"
            },
            "target_object": "Contact",
            "external_id_field": "External_Id__c",
            "field_mappings": field_mappings,
            "sync_mode": "upsert",
            "batch_size": 2
        }
    )

    activity = ReverseETLActivity(context=context, db_session=db_session)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.rows_read == 3
    assert result.rows_written == 3
    assert result.output_variables["records_synced"] == 3
    assert result.output_variables["records_failed"] == 0
    assert result.output_variables["target_object"] == "Contact"
