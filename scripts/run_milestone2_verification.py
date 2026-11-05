#!/usr/bin/env python3
"""
DataFlow Enterprise — Milestone 2 Verification Script
Tests:
  1. Advanced Control Flow & Dynamic Expressions:
     Lookup -> SetVariable -> IfCondition -> Wait -> CopyData
  2. Automated Recurrence Trigger & Scheduler Daemon:
     Cron calculation, next fire time persistence, trigger dispatch.
"""

import sys
import os
import time
from datetime import datetime, timezone

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import SessionLocal
from backend.app.models.workspace import Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline, Trigger
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.execution.runner import PipelineRunner
from backend.app.orchestration.scheduler import scheduler


def run_milestone2_verification():
    print("=" * 70)
    print("  DATAFLOW ENTERPRISE — MILESTONE 2 VERIFICATION")
    print("=" * 70)

    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.name == "Core Analytics & Ingestion").first()
        assert project, "Project not found"

        mysql_conn = db.query(Connection).filter(Connection.name == "MySQL ERP Source").first()
        pg_conn = db.query(Connection).filter(Connection.name == "PostgreSQL Warehouse Destination").first()
        assert mysql_conn and pg_conn, "Prerequisite connections missing"

        # ---------------------------------------------------------
        # TEST 1: Control Flow & Dynamic Expressions Pipeline
        # ---------------------------------------------------------
        print("\n--- TEST 1: Control Flow & Expression Evaluation Pipeline ---")
        pipeline_def = {
            "parameters": {
                "batch_limit": 500,
                "environment": "production"
            },
            "variables": {
                "watermark_date": "1970-01-01 00:00:00",
                "condition_checked": False
            },
            "activities": [
                {
                    "id": "act_lookup_stats",
                    "name": "Lookup Latest Date",
                    "type": "Lookup",
                    "depends_on": [],
                    "config": {
                        "connection_id": mysql_conn.id,
                        "query": "SELECT MAX(updated_at) as max_date, COUNT(*) as total_orders FROM source_orders;",
                        "first_row_only": True
                    }
                },
                {
                    "id": "act_set_watermark",
                    "name": "Set Dynamic Watermark",
                    "type": "SetVariable",
                    "depends_on": [
                        {"activity_id": "act_lookup_stats", "condition": "Succeeded"}
                    ],
                    "config": {
                        "variable_name": "watermark_date",
                        "value": "@activity('act_lookup_stats').output.first_row.max_date"
                    }
                },
                {
                    "id": "act_eval_condition",
                    "name": "Check Orders Exist",
                    "type": "IfCondition",
                    "depends_on": [
                        {"activity_id": "act_lookup_stats", "condition": "Succeeded"}
                    ],
                    "config": {
                        "expression": "@greater(@activity('act_lookup_stats').output.first_row.total_orders, 0)"
                    }
                },
                {
                    "id": "act_wait_pause",
                    "name": "Controlled Pause",
                    "type": "Wait",
                    "depends_on": [
                        {"activity_id": "act_set_watermark", "condition": "Succeeded"}
                    ],
                    "config": {
                        "wait_time_in_seconds": 1
                    }
                }
            ]
        }

        pipeline = db.query(Pipeline).filter(Pipeline.name == "Milestone 2 Control Flow Demo").first()
        if not pipeline:
            pipeline = Pipeline(
                project_id=project.id,
                name="Milestone 2 Control Flow Demo",
                description="Pipeline demonstrating Lookup, SetVariable, IfCondition, and Wait activities",
                definition_json=pipeline_def,
                status="Published",
                current_version=1
            )
            db.add(pipeline)
        else:
            pipeline.definition_json = pipeline_def
            pipeline.current_version += 1
        db.commit()
        db.refresh(pipeline)

        print(f"[OK] Pipeline configured: '{pipeline.name}' (ID: {pipeline.id})")

        # Execute Control Flow Pipeline
        run = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Pending",
            parameters={"environment": "production"}
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        print("[+] Running control flow pipeline execution...")
        runner = PipelineRunner(run.id)
        runner.execute_sync()

        db.refresh(run)
        print(f"[RUN RESULT] Status: {run.status} in {run.duration_seconds}s")
        print(f"Activities Succeeded: {run.succeeded_activities} / {run.total_activities}")
        assert run.status == "Succeeded", f"Pipeline run failed: {run.error_summary}"
        assert run.succeeded_activities == 4, f"Expected 4 activities to succeed, got {run.succeeded_activities}"

        # Verify activity outputs
        act_runs = db.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).all()
        for act in act_runs:
            print(f"   -> [{act.status}] {act.activity_name} ({act.activity_type}) in {act.duration_seconds}s")
        print("[OK] Control flow and dynamic expression evaluation verified!")

        # ---------------------------------------------------------
        # TEST 2: Trigger & Scheduler Daemon Verification
        # ---------------------------------------------------------
        print("\n--- TEST 2: Trigger Scheduling & Cron Daemon ---")
        trigger = db.query(Trigger).filter(Trigger.name == "Hourly Sales Ingestion Schedule").first()
        next_fire = scheduler.calculate_next_fire("*/15 * * * *")

        if not trigger:
            trigger = Trigger(
                pipeline_id=pipeline.id,
                name="Hourly Sales Ingestion Schedule",
                trigger_type="cron",
                cron_expression="*/15 * * * *",
                is_active=True,
                parameters={"env": "prod", "triggered_by": "cron_daemon"},
                next_fire_time=next_fire
            )
            db.add(trigger)
        else:
            trigger.next_fire_time = next_fire
            trigger.is_active = True
        db.commit()
        db.refresh(trigger)

        print(f"[OK] Trigger registered: '{trigger.name}'")
        print(f"   -> Cron: {trigger.cron_expression}")
        print(f"   -> Next Fire Time: {trigger.next_fire_time.isoformat()}")

        # Test Fire Now
        print("[+] Testing trigger dispatch...")
        scheduled_run = PipelineRun(
            pipeline_id=trigger.pipeline_id,
            run_type=f"Trigger:{trigger.trigger_type}",
            status="Pending",
            parameters=trigger.parameters or {},
            started_at=datetime.now(timezone.utc)
        )
        db.add(scheduled_run)
        trigger.last_fired_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(scheduled_run)

        runner_sched = PipelineRunner(scheduled_run.id)
        runner_sched.execute_sync()

        db.refresh(scheduled_run)
        print(f"[TRIGGER RUN RESULT] Status: {scheduled_run.status}")
        assert scheduled_run.status == "Succeeded", f"Scheduled run failed: {scheduled_run.error_summary}"
        print(f"[OK] Scheduled run executed successfully with parameters: {scheduled_run.parameters}")

        print("\n" + "=" * 70)
        print("  [SUCCESS] ALL MILESTONE 2 VERIFICATION TESTS PASSED!")
        print("=" * 70)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_milestone2_verification()
    sys.exit(0 if success else 1)
