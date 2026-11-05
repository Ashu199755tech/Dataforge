from backend.app.execution.dag_engine import PipelineDAG


def test_adf_four_dependency_conditions():
    activities = [
        {"id": "A", "name": "Activity A", "depends_on": []},
        {"id": "B_on_success", "name": "Runs on Success", "depends_on": [{"activity_id": "A", "condition": "Succeeded"}]},
        {"id": "C_on_failure", "name": "Runs on Failure", "depends_on": [{"activity_id": "A", "condition": "Failed"}]},
        {"id": "D_on_completion", "name": "Runs on Completion", "depends_on": [{"activity_id": "A", "condition": "Completed"}]},
        {"id": "E_on_skip", "name": "Runs on Skip", "depends_on": [{"activity_id": "B_on_success", "condition": "Skipped"}]}
    ]
    dag = PipelineDAG(activities)

    # SCENARIO 1: Parent A Succeeds
    comp_success = {"A": "Succeeded"}
    assert dag.is_activity_ready("B_on_success", comp_success) is True
    assert dag.is_activity_ready("C_on_failure", comp_success) is False
    assert dag.is_activity_ready("D_on_completion", comp_success) is True

    # When A succeeds, C_on_failure is dead
    assert dag.is_activity_dead("C_on_failure", comp_success) is True
    assert dag.is_activity_dead("B_on_success", comp_success) is False

    # SCENARIO 2: Parent A Fails
    comp_failed = {"A": "Failed"}
    assert dag.is_activity_ready("B_on_success", comp_failed) is False
    assert dag.is_activity_ready("C_on_failure", comp_failed) is True
    assert dag.is_activity_ready("D_on_completion", comp_failed) is True

    # When A fails, B_on_success is dead -> will become Skipped
    assert dag.is_activity_dead("B_on_success", comp_failed) is True

    # SCENARIO 3: B_on_success is Skipped -> E_on_skip should be Ready!
    comp_skip = {"A": "Failed", "B_on_success": "Skipped"}
    assert dag.is_activity_ready("E_on_skip", comp_skip) is True
