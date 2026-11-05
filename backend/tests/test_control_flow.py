import os
import tempfile
from backend.app.core.database import SessionLocal
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.set_variable import SetVariableActivity
from backend.app.activities.wait import WaitActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.connectors.local_file import LocalFileConnector


def test_set_variable_activity():
    db = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_set_var",
            activity_name="Set Counter",
            activity_type="SetVariable",
            config={"variable_name": "counter", "value": 100},
            pipeline_parameters={},
            pipeline_variables={}
        )
        act = SetVariableActivity(ctx, db)
        res = act.execute()
        assert res.status == "Succeeded"
        assert res.output_variables["counter"] == 100
    finally:
        db.close()


def test_wait_activity():
    db = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_wait",
            activity_name="Short Pause",
            activity_type="Wait",
            config={"wait_time_in_seconds": 0.05},
            pipeline_parameters={},
            pipeline_variables={}
        )
        act = WaitActivity(ctx, db)
        res = act.execute()
        assert res.status == "Succeeded"
    finally:
        db.close()


def test_if_condition_activity():
    db = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_test",
            activity_id="act_if",
            activity_name="Check Environment",
            activity_type="IfCondition",
            config={"expression": "@equals(@parameters('env'), 'production')"},
            pipeline_parameters={"env": "production"},
            pipeline_variables={}
        )
        act = IfConditionActivity(ctx, db)
        res = act.execute()
        assert res.status == "Succeeded"
        assert res.output_variables["outcome"] is True
        assert res.output_variables["branch_taken"] == "True"
    finally:
        db.close()


def test_local_file_connector():
    with tempfile.TemporaryDirectory() as tmp_dir:
        conn = LocalFileConnector({"base_path": tmp_dir})
        assert conn.test_connection().success is True

        # Write CSV batch
        records = [
            {"id": 1, "product": "Widget", "price": 19.99},
            {"id": 2, "product": "Gadget", "price": 49.99}
        ]
        written = conn.write_data_batch("inventory.csv", records, write_mode="overwrite")
        assert written == 2

        # Stream CSV
        stream = conn.read_data_stream("inventory.csv", batch_size=1)
        chunks = list(stream)
        assert len(chunks) == 2
        assert chunks[0][0]["product"] == "Widget"
