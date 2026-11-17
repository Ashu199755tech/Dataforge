import os
import json
import uuid
import polars as pl
from datetime import datetime, timezone

from backend.app.core.database import SessionLocal
from backend.app.models.workspace import Project, Workspace
from backend.app.models.connection import Connection
from backend.app.models.dataset import Dataset
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.core.security import encrypt_secret
from backend.app.execution.runner import PipelineRunner
from backend.app.models.data_quality import FactDQExecutionLog, DQCleansingLog

def run_demo_setup():
    db = SessionLocal()

    # 1. Create Data Directory and Raw Mock Dataset
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    bronze_parquet = os.path.join(data_dir, "test_bronze_customers.parquet")
    bronze_csv = os.path.join(data_dir, "test_bronze_customers.csv")
    silver_parquet = os.path.join(data_dir, "silver_customers.parquet")
    quarantine_parquet = os.path.join(data_dir, "quarantine_customers.parquet")

    # Clean existing destination files if any
    for p in [silver_parquet, quarantine_parquet]:
        if os.path.exists(p):
            os.remove(p)

    df = pl.DataFrame({
        "customer_id": [101, 102, 103, None, 105, 106],
        "full_name": ["Alice Wonder", "   Bob   Smith   ", "Charlie Brown", "Ghost User", "  David   Miller  ", "Eva Green"],
        "email": ["alice@example.com", "bob@example.com", "charlie-invalid-email", "ghost@example.com", "david@example.com", "eva@example.com"],
        "status": ["ACTIVE", "N/A", "PENDING", "ACTIVE", "UNKNOWN", "ACTIVE"],
        "credit_score": [750.0, -25.0, 680.0, 710.0, 820.0, 640.0],
        "country_code": ["US", "US", "XX", "CA", "US", "GB"]
    })
    df.write_parquet(bronze_parquet)
    df.write_csv(bronze_csv)
    print(f"[OK] Raw test dataset created: {bronze_parquet} ({len(df)} rows)")

    # 2. Get or Create Workspace and Project
    project = db.query(Project).first()
    if not project:
        ws = Workspace(name="Default Enterprise Workspace", description="Default Workspace")
        db.add(ws)
        db.commit()
        project = Project(name="Core Analytics & Ingestion", workspace_id=ws.id)
        db.add(project)
        db.commit()

    # 3. Create or Update Linked Service Connection
    conn_name = "Local_Storage_Lake"
    conn = db.query(Connection).filter(Connection.name == conn_name).first()
    if not conn:
        conn = Connection(
            project_id=project.id,
            name=conn_name,
            connector_type="local_storage",
            description="Local Storage Data Lake (Bronze / Silver / Quarantine)",
            config_encrypted=encrypt_secret({"root_dir": data_dir}),
            status="Active"
        )
        db.add(conn)
        db.commit()
        print(f"[OK] Linked Service Connection created: {conn.name} ({conn.id})")
    else:
        print(f"[OK] Linked Service Connection exists: {conn.name} ({conn.id})")

    # 4. Create Datasets in Catalog
    def get_or_create_dataset(name, path, fmt="parquet"):
        ds = db.query(Dataset).filter(Dataset.name == name).first()
        if not ds:
            ds = Dataset(
                project_id=project.id,
                connection_id=conn.id,
                name=name,
                dataset_type="Parquet",
                description=f"Managed {name} dataset",
                location_config={"file_path": path, "format": fmt},
                format_settings={"format": fmt}
            )
            db.add(ds)
            db.commit()
            print(f"[OK] Dataset cataloged: {name}")
        return ds

    ds_bronze = get_or_create_dataset("Bronze_Customers_Lake", bronze_parquet)
    ds_silver = get_or_create_dataset("Silver_Customers_Lake", silver_parquet)
    ds_quarantine = get_or_create_dataset("Quarantine_Customers_Lake", quarantine_parquet)

    # 5. Define Rule Catalogue and Precedence Cleansing Map
    rules = [
        {
            "rule_id": "R_PK_NN",
            "rule_type": "ATR1",
            "target_column": "customer_id",
            "technical_description": "Primary Key customer_id must not be null"
        },
        {
            "rule_id": "R_EMAIL_FMT",
            "rule_type": "ATR4",
            "target_column": "email",
            "parameters": {"pattern": r"^[^@]+@[^@]+\.[^@]+$"},
            "technical_description": "Email address must match valid email format regex"
        },
        {
            "rule_id": "R_STATUS_PH",
            "rule_type": "ATR3",
            "target_column": "status",
            "placeholder_values": ["N/A", "UNKNOWN", ""],
            "technical_description": "Status column must not contain placeholder or sentinel values"
        },
        {
            "rule_id": "R_CREDIT_POS",
            "rule_type": "ATR6",
            "target_column": "credit_score",
            "technical_description": "Credit score must be non-negative"
        }
    ]

    cleansing_steps = [
        {
            "step_name": "Trim Full Names",
            "target_column": "full_name",
            "strategy": "trim",
            "fire": "always",
            "stage": 0
        },
        {
            "step_name": "Remediate Status Placeholders",
            "rule_id": "R_STATUS_PH",
            "target_column": "status",
            "strategy": "hardcode_constant",
            "params": {"value": "PENDING"},
            "fire": "on_failed_rule",
            "stage": 0
        },
        {
            "step_name": "Remediate Negative Credit Score",
            "rule_id": "R_CREDIT_POS",
            "target_column": "credit_score",
            "strategy": "hardcode_constant",
            "params": {"value": 500.0},
            "fire": "on_failed_rule",
            "stage": 0
        }
    ]

    # 6. Build ADF-Style Pipeline Definition JSON with Canvas Nodes & Edges
    act1_id = "act_assess_customers"
    act2_id = "act_enforce_customers"

    nodes = [
        {
            "id": act1_id,
            "type": "activityNode",
            "position": {"x": 120, "y": 180},
            "data": {
                "label": "DQ Assess (Audit)",
                "activityType": "DQAssessActivity",
                "state": "Active",
                "config": {
                    "sourceDataset": {"referenceName": ds_bronze.name, "file_path": bronze_parquet},
                    "connection_id": conn.id,
                    "file_path": bronze_parquet,
                    "format": "parquet",
                    "key_columns": ["customer_id"],
                    "dqiGateThreshold": 0.60,
                    "ruleCatalogue": {
                        "referenceName": "DQ_RULE_CATALOGUE",
                        "rules": rules
                    }
                }
            }
        },
        {
            "id": act2_id,
            "type": "activityNode",
            "position": {"x": 560, "y": 180},
            "data": {
                "label": "DQ Enforce (Dual-Sink)",
                "activityType": "DQEnforceActivity",
                "state": "Active",
                "config": {
                    "sourceDataset": {"referenceName": ds_bronze.name, "file_path": bronze_parquet},
                    "targetDataset": {"referenceName": ds_silver.name, "file_path": silver_parquet},
                    "quarantineDataset": {"referenceName": ds_quarantine.name, "file_path": quarantine_parquet},
                    "connection_id": conn.id,
                    "file_path": bronze_parquet,
                    "key_columns": ["customer_id"],
                    "writeStrategy": "merge",
                    "cleansingEnabled": True,
                    "dqiGateThreshold": 0.60,
                    "ruleCatalogue": {
                        "referenceName": "DQ_RULE_CATALOGUE",
                        "rules": rules
                    },
                    "cleansingMap": {
                        "referenceName": "Customer_Remediation_Rules",
                        "steps": cleansing_steps
                    }
                }
            }
        }
    ]

    edges = [
        {
            "id": f"e_{act1_id}_{act2_id}",
            "source": act1_id,
            "target": act2_id,
            "sourceHandle": "Succeeded",
            "targetHandle": "target",
            "data": {"condition": "Succeeded"},
            "label": "On Success"
        }
    ]

    activities = [
        {
            "id": act1_id,
            "name": "DQ Assess (Audit)",
            "type": "DQAssessActivity",
            "state": "Active",
            "dependsOn": [],
            "config": nodes[0]["data"]["config"],
            "typeProperties": nodes[0]["data"]["config"]
        },
        {
            "id": act2_id,
            "name": "DQ Enforce (Dual-Sink)",
            "type": "DQEnforceActivity",
            "state": "Active",
            "dependsOn": [{"activity": act1_id, "dependencyConditions": ["Succeeded"]}],
            "config": nodes[1]["data"]["config"],
            "typeProperties": nodes[1]["data"]["config"]
        }
    ]

    pipeline_def = {
        "parameters": {},
        "variables": {},
        "activities": activities,
        "nodes": nodes,
        "edges": edges
    }

    pipe_name = "E2E_Data_Quality_Governance_Pipeline"
    pipeline = db.query(Pipeline).filter(Pipeline.name == pipe_name).first()
    if not pipeline:
        pipeline = Pipeline(
            name=pipe_name,
            description="End-to-End Enterprise Data Quality Pipeline: Assess Quality -> Precedence Cleansing -> Dual-Sink Quarantine Routing",
            project_id=project.id,
            status="Published",
            definition_json=pipeline_def
        )
        db.add(pipeline)
        db.commit()
        print(f"[OK] Pipeline created: {pipeline.name} ({pipeline.id})")
    else:
        pipeline.definition_json = pipeline_def
        pipeline.status = "Published"
        db.commit()
        print(f"[OK] Pipeline updated: {pipeline.name} ({pipeline.id})")

    # 7. Execute Pipeline Run End-to-End
    print("\n--- TRIGGERING PIPELINE RUN ---")
    run = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Pending",
        started_at=datetime.now(timezone.utc)
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    print(f"Triggered Pipeline Run ID: {run.id}")
    runner_exec = PipelineRunner(run.id)
    runner_exec.execute_sync()
    db.refresh(run)
    print(f"Pipeline Execution Status: {run.status}")

    # 8. Inspect Generated Outputs & Audit Tables
    print("\n--- INSPECTING PERSISTED DATA QUALITY ARTIFACTS ---")
    if os.path.exists(silver_parquet):
        silver_df = pl.read_parquet(silver_parquet)
        print(f"\n[Silver Dataset] ({silver_parquet}) - {len(silver_df)} Clean Records:")
        print(silver_df.select(["customer_id", "full_name", "email", "status", "credit_score", "DQ_FLAG", "DQ_CLEANSED"]))

    if os.path.exists(quarantine_parquet):
        quar_df = pl.read_parquet(quarantine_parquet)
        print(f"\n[Quarantine Dataset] ({quarantine_parquet}) - {len(quar_df)} Rejected Records:")
        print(quar_df.select(["customer_id", "full_name", "email", "status", "credit_score", "DQ_FLAG", "DQ_FAILED_RULE_IDS"]))

    exec_logs = db.query(FactDQExecutionLog).filter(FactDQExecutionLog.pipeline_run_id == run.id).all()
    print(f"\n[FactDQExecutionLog] ({len(exec_logs)} execution audit records):")
    for el in exec_logs:
        print(f"  Activity: {el.activity_type} | Total: {el.total_records} | Clean: {el.clean_records} | Cleansed: {el.cleansed_records} | Soft Reject: {el.soft_reject_records} | Hard Reject: {el.hard_reject_records} | DQI: {el.overall_dqi:.4f} | Gate: {el.gate_passed}")

    cell_logs = db.query(DQCleansingLog).filter(DQCleansingLog.batch_id == run.id).all()
    print(f"\n[DQCleansingLog] ({len(cell_logs)} cell remediation diffs recorded):")
    for cl in cell_logs:
        print(f"  Col: {cl.column_name:<12} | Rule: {cl.rule_id:<12} | Strategy: {cl.strategy:<16} | Before: {repr(cl.before_value):<20} -> After: {repr(cl.after_value)}")

    pipe_id = pipeline.id
    run_res_id = run.id
    db.close()
    return pipe_id, run_res_id

if __name__ == "__main__":
    run_demo_setup()
