import pytest
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError


def test_valid_dag_topological_sort():
    activities = [
        {"id": "act_extract", "name": "Extract", "depends_on": []},
        {"id": "act_transform", "name": "Transform", "depends_on": [{"activity_id": "act_extract", "condition": "Succeeded"}]},
        {"id": "act_load", "name": "Load", "depends_on": [{"activity_id": "act_transform", "condition": "Succeeded"}]}
    ]
    dag = PipelineDAG(activities)
    assert dag.get_root_activities() == ["act_extract"]
    assert dag.is_activity_ready("act_extract", {}) is True
    assert dag.is_activity_ready("act_transform", {}) is False
    assert dag.is_activity_ready("act_transform", {"act_extract": "Succeeded"}) is True
    assert dag.is_activity_ready("act_load", {"act_extract": "Succeeded", "act_transform": "Succeeded"}) is True


def test_cycle_detection():
    cyclic_activities = [
        {"id": "A", "depends_on": [{"activity_id": "B"}]},
        {"id": "B", "depends_on": [{"activity_id": "C"}]},
        {"id": "C", "depends_on": [{"activity_id": "A"}]}
    ]
    with pytest.raises(DAGValidationError):
        PipelineDAG(cyclic_activities)


def test_dependency_conditions():
    activities = [
        {"id": "A", "depends_on": []},
        {"id": "B_success_handler", "depends_on": [{"activity_id": "A", "condition": "Succeeded"}]},
        {"id": "C_error_handler", "depends_on": [{"activity_id": "A", "condition": "Failed"}]}
    ]
    dag = PipelineDAG(activities)
    # When A fails
    assert dag.is_activity_ready("B_success_handler", {"A": "Failed"}) is False
    assert dag.is_activity_ready("C_error_handler", {"A": "Failed"}) is True
