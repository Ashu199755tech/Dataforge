import pytest
import time
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.models.workspace import Workspace, Project
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.for_each import ForEachActivity
from backend.app.activities.execute_pipeline import ExecutePipelineActivity
from backend.app.activities.switch_condition import SwitchActivity
from backend.app.activities.filter_activity import FilterActivity
from backend.app.activities.fail_activity import FailActivity
from backend.app.activities.append_variable import AppendVariableActivity
from backend.app.activities.until import UntilActivity
from backend.app.execution.expressions import ExpressionEvaluator


@pytest.fixture(scope="module")
def setup_control_flow_project():
    db: Session = SessionLocal()
    try:
        ws = db.query(Workspace).first()
        ws_id = ws.id if ws else "ws_test"

        proj = db.query(Project).filter(Project.name == "Test_Control_Flow_Project").first()
        if not proj:
            proj = Project(
                workspace_id=ws_id,
                name="Test_Control_Flow_Project",
                description="Testing Hierarchical Control Flow"
            )
            db.add(proj)
            db.commit()
            db.refresh(proj)

        yield {"project_id": proj.id}
    finally:
        db.close()


def test_scenario_1_lookup_if_condition_flow():
    """
    Acceptance Scenario 1:
    Lookup -> If Condition -> Branch evaluation
    """
    db: Session = SessionLocal()
    try:
        from backend.app.activities.if_condition import IfConditionActivity

        # Simulate Lookup output: {"total_orders": 150}
        activity_outputs = {
            "lookup_orders": {
                "first_row": {"total_orders": 150}
            }
        }

        # Evaluator checks if orders > 100
        evaluator = ExpressionEvaluator(activity_outputs=activity_outputs)
        resolved_expr = evaluator.evaluate("@greater(activity('lookup_orders').output.first_row.total_orders, 100)")
        assert resolved_expr is True

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_scen1",
            activity_id="act_if",
            activity_name="Check High Volume",
            activity_type="IfCondition",
            config={"expression": "@greater(activity('lookup_orders').output.first_row.total_orders, 100)"}
        )
        # Manually evaluate config as runner does
        ctx.config = evaluator.evaluate(ctx.config)

        act = IfConditionActivity(ctx, db)
        res = act.execute()
        assert res.status == "Succeeded"
        assert res.output_variables["evaluated_result"] is True
    finally:
        db.close()


def test_scenario_2_and_4_for_each_sequential_and_parallel():
    """
    Acceptance Scenario 2 & 4:
    GetMetadata -> ForEach (sequential and parallel processing with @item() resolution)
    """
    db: Session = SessionLocal()
    try:
        test_files = ["sales_2024_01.csv", "sales_2024_02.csv", "sales_2024_03.csv", "sales_2024_04.csv"]

        # 1. Test Sequential ForEach
        seq_ctx = ActivityExecutionContext(
            pipeline_run_id="run_seq_foreach",
            activity_id="act_foreach_seq",
            activity_name="Process Files Sequentially",
            activity_type="ForEach",
            config={
                "items": test_files,
                "is_sequential": True,
                "batch_count": 1,
                "activities": [
                    {
                        "id": "sub_wait",
                        "name": "Wait For File",
                        "type": "Wait",
                        "config": {"wait_time_in_seconds": 0}
                    }
                ]
            }
        )
        seq_act = ForEachActivity(seq_ctx, db)
        seq_res = seq_act.execute()

        assert seq_res.status == "Succeeded"
        assert seq_res.output_variables["item_count"] == 4
        assert seq_res.output_variables["succeeded_count"] == 4
        assert seq_res.output_variables["failed_count"] == 0

        # 2. Test Parallel ForEach with ThreadPool concurrency
        start_clock = time.time()
        par_ctx = ActivityExecutionContext(
            pipeline_run_id="run_par_foreach",
            activity_id="act_foreach_par",
            activity_name="Process Files In Parallel",
            activity_type="ForEach",
            config={
                "items": test_files,
                "is_sequential": False,
                "batch_count": 4,
                "activities": [
                    {
                        "id": "sub_wait_par",
                        "name": "Simulate Parallel Task",
                        "type": "Wait",
                        "config": {"wait_time_in_seconds": 0}
                    }
                ]
            }
        )
        par_act = ForEachActivity(par_ctx, db)
        par_res = par_act.execute()

        assert par_res.status == "Succeeded"
        assert par_res.output_variables["item_count"] == 4
        assert par_res.output_variables["succeeded_count"] == 4
        assert par_res.output_variables["failed_count"] == 0
    finally:
        db.close()


def test_scenario_3_parent_executes_child_pipeline(setup_control_flow_project):
    """
    Acceptance Scenario 3:
    Parent Pipeline -> Execute Child Pipeline with parameter forwarding
    """
    db: Session = SessionLocal()
    try:
        proj_id = setup_control_flow_project["project_id"]

        # Create child pipeline definition
        child_pipeline = db.query(Pipeline).filter(Pipeline.name == "Child_Worker_Pipeline").first()
        if not child_pipeline:
            child_pipeline = Pipeline(
                project_id=proj_id,
                name="Child_Worker_Pipeline",
                description="Worker pipeline executed by parent orchestrator",
                definition_json={
                    "parameters": {"batch_id": "DEFAULT"},
                    "activities": [
                        {
                            "id": "child_wait",
                            "name": "Child Wait Task",
                            "type": "Wait",
                            "config": {"wait_time_in_seconds": 0}
                        }
                    ]
                }
            )
            db.add(child_pipeline)
            db.commit()
            db.refresh(child_pipeline)

        # Parent activity invokes child pipeline
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_parent_orchestrator",
            activity_id="act_call_child",
            activity_name="Invoke Worker Pipeline",
            activity_type="ExecutePipeline",
            config={
                "pipeline_id": child_pipeline.id,
                "parameters": {"batch_id": "BATCH_2026_NOVEMBER"},
                "wait_on_completion": True
            }
        )
        act = ExecutePipelineActivity(ctx, db)
        res = act.execute()

        assert res.status == "Succeeded"
        assert res.output_variables["child_status"] == "Succeeded"
        assert res.output_variables["child_pipeline_name"] == "Child_Worker_Pipeline"

        # Verify child run was persisted and completed in database
        child_run_id = res.output_variables["child_run_id"]
        child_run_record = db.query(PipelineRun).filter(PipelineRun.id == child_run_id).first()
        assert child_run_record is not None
        assert child_run_record.status == "Succeeded"
        assert child_run_record.parameters.get("batch_id") == "BATCH_2026_NOVEMBER"
    finally:
        db.close()


def test_switch_activity():
    """Verifies SwitchActivity routes execution to matching case branch."""
    db: Session = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_switch",
            activity_id="act_switch",
            activity_name="Route by Environment",
            activity_type="Switch",
            config={
                "expression": "PRODUCTION",
                "cases": [
                    {
                        "value": "DEVELOPMENT",
                        "activities": [{"id": "dev_act", "name": "Dev Task", "type": "Wait", "config": {"wait_time_in_seconds": 0}}]
                    },
                    {
                        "value": "PRODUCTION",
                        "activities": [{"id": "prod_act", "name": "Prod Task", "type": "Wait", "config": {"wait_time_in_seconds": 0}}]
                    }
                ],
                "default_activities": []
            }
        )
        act = SwitchActivity(ctx, db)
        res = act.execute()
        assert res.status == "Succeeded"
        assert res.output_variables["matched_case"] == "PRODUCTION"
        assert res.output_variables["evaluated_value"] == "PRODUCTION"
    finally:
        db.close()


def test_filter_activity():
    """Verifies FilterActivity filters array items based on dynamic conditions."""
    db: Session = SessionLocal()
    try:
        sample_transactions = [
            {"tx_id": 101, "amount": 50},
            {"tx_id": 102, "amount": 250},
            {"tx_id": 103, "amount": 10},
            {"tx_id": 104, "amount": 900}
        ]

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_filter",
            activity_id="act_filter",
            activity_name="Filter High Value Transactions",
            activity_type="Filter",
            config={
                "items": sample_transactions,
                "condition": "@greater(@item().amount, 100)"
            }
        )
        act = FilterActivity(ctx, db)
        res = act.execute()

        assert res.status == "Succeeded"
        assert res.output_variables["count"] == 2
        filtered_ids = [tx["tx_id"] for tx in res.output_variables["value"]]
        assert filtered_ids == [102, 104]
    finally:
        db.close()


def test_fail_activity():
    """Verifies FailActivity triggers deliberate, graceful activity failure."""
    db: Session = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_fail",
            activity_id="act_fail",
            activity_name="Trigger SLA Failure",
            activity_type="Fail",
            config={
                "error_code": "SLA_BREACH",
                "message": "Critical daily latency threshold exceeded"
            }
        )
        act = FailActivity(ctx, db)
        res = act.execute()

        assert res.status == "Failed"
        assert "[SLA_BREACH] Critical daily latency threshold exceeded" in res.error_message
        assert res.output_variables["error_code"] == "SLA_BREACH"
    finally:
        db.close()


def test_append_variable_activity():
    """Verifies AppendVariableActivity appends items to array variables."""
    db: Session = SessionLocal()
    try:
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_append",
            activity_id="act_append",
            activity_name="Accumulate Processed File",
            activity_type="AppendVariable",
            config={
                "variable_name": "processed_files",
                "value": "file_alpha.csv"
            },
            pipeline_variables={"processed_files": ["seed_file.csv"]}
        )
        act = AppendVariableActivity(ctx, db)
        res = act.execute()

        assert res.status == "Succeeded"
        assert res.output_variables["processed_files"] == ["seed_file.csv", "file_alpha.csv"]
        assert len(ctx.pipeline_variables["processed_files"]) == 2
    finally:
        db.close()
