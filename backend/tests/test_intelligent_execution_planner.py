import time
from typing import Dict, Any

from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.engine.planner.models import (
    ExecutionEngineType,
    PlannerStrategy,
    WorkloadProfile
)
from backend.app.engine.planner.cost_model import (
    TransformationComplexityScorer,
    EngineCostCalculator
)
from backend.app.engine.planner.planner import IntelligentExecutionPlanner


def test_planner_developer_overrides():
    profile = WorkloadProfile(
        estimated_bytes=100 * 1024 * 1024,
        transformation_complexity_score=8,
        is_same_database_instance=True,
        spark_available=True
    )

    # Force COPY
    dec_copy = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.FORCE_COPY)
    assert dec_copy.selected_engine == ExecutionEngineType.COPY
    assert dec_copy.strategy_applied == PlannerStrategy.FORCE_COPY
    assert dec_copy.confidence_score == 1.0

    # Force SPARK
    dec_spark = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.FORCE_SPARK)
    assert dec_spark.selected_engine == ExecutionEngineType.SPARK
    assert dec_spark.strategy_applied == PlannerStrategy.FORCE_SPARK

    # Force SQL_PUSHDOWN
    dec_push = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.FORCE_SQL_PUSHDOWN)
    assert dec_push.selected_engine == ExecutionEngineType.SQL_PUSHDOWN
    assert dec_push.strategy_applied == PlannerStrategy.FORCE_SQL_PUSHDOWN


def test_planner_selects_copy_for_pure_data_movement():
    # Pure data movement across cloud/local storage without transforms
    profile = WorkloadProfile(
        estimated_bytes=500 * 1024 * 1024,  # 500 MB
        transformation_complexity_score=0,
        is_same_database_instance=False,
        is_cloud_storage=True,
        spark_available=False
    )

    decision = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.AUTO)
    assert decision.selected_engine == ExecutionEngineType.COPY
    assert decision.scores[ExecutionEngineType.COPY.value] > decision.scores[ExecutionEngineType.SPARK.value]
    assert decision.scores[ExecutionEngineType.COPY.value] > decision.scores[ExecutionEngineType.SQL_PUSHDOWN.value]
    assert "pure_data_movement" in decision.explanation or "Copy" in decision.explanation


def test_planner_selects_sql_pushdown_for_in_database_transforms():
    # Transformations where source and sink reside in the same database instance
    profile = WorkloadProfile(
        estimated_bytes=50 * 1024 * 1024,
        transformation_complexity_score=4,
        has_aggregations=True,
        has_joins=True,
        is_same_database_instance=True,
        database_supports_pushdown=True,
        spark_available=False
    )

    decision = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.AUTO)
    assert decision.selected_engine == ExecutionEngineType.SQL_PUSHDOWN
    assert decision.scores[ExecutionEngineType.SQL_PUSHDOWN.value] > decision.scores[ExecutionEngineType.COPY.value]
    assert "zero network egress" in decision.explanation.lower() or "same database" in decision.explanation.lower()


def test_planner_selects_spark_for_large_complex_transforms():
    # Multi-gigabyte distributed transformation graph
    profile = WorkloadProfile(
        estimated_bytes=25 * 1024 * 1024 * 1024,  # 25 GB
        transformation_complexity_score=7,
        has_joins=True,
        has_window_functions=True,
        has_aggregations=True,
        is_same_database_instance=False,
        spark_available=True
    )

    decision = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.AUTO)
    assert decision.selected_engine == ExecutionEngineType.SPARK
    assert decision.confidence_score >= 0.70
    assert "Catalyst" in decision.explanation or "distributed" in decision.explanation.lower()


def test_planner_falls_back_when_spark_unavailable():
    # Complex transformation graph but PySpark is not available on host
    profile = WorkloadProfile(
        estimated_bytes=25 * 1024 * 1024 * 1024,
        transformation_complexity_score=7,
        has_joins=True,
        has_window_functions=True,
        is_same_database_instance=False,
        spark_available=False
    )

    decision = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.AUTO)
    # Spark should receive a heavy penalty; Copy or fallback chosen
    assert decision.selected_engine != ExecutionEngineType.SPARK
    assert decision.scores[ExecutionEngineType.SPARK.value] < decision.scores[ExecutionEngineType.COPY.value]


def test_transformation_complexity_scorer():
    simple_graph = {
        "nodes": [
            {"id": "s", "type": "source"},
            {"id": "f", "type": "filter"},
            {"id": "o", "type": "sink"}
        ]
    }
    score_simple, feat_simple = TransformationComplexityScorer.score_graph(simple_graph)
    assert score_simple <= 1
    assert feat_simple["has_joins"] is False

    complex_graph = {
        "nodes": [
            {"id": "s1", "type": "source"},
            {"id": "s2", "type": "source"},
            {"id": "j", "type": "join"},
            {"id": "agg", "type": "aggregate"},
            {"id": "w", "type": "window"},
            {"id": "o", "type": "sink"}
        ]
    }
    score_complex, feat_complex = TransformationComplexityScorer.score_graph(complex_graph)
    assert score_complex >= 5
    assert feat_complex["has_joins"] is True
    assert feat_complex["has_aggregations"] is True
    assert feat_complex["has_window_functions"] is True


def test_plan_dataflow_integration():
    db_path = "/tmp/test_planner_db.sqlite"
    conn = SQLiteConnector({"database_path": db_path})

    graph = {
        "nodes": [
            {"id": "src", "type": "source", "data": {"operatorType": "source", "config": {"table_name": "users"}}},
            {"id": "filter", "type": "filter", "data": {"operatorType": "filter", "config": {"condition": "age > 18"}}},
            {"id": "agg", "type": "aggregate", "data": {"operatorType": "aggregate", "config": {"group_by": ["country"]}}},
            {"id": "sink", "type": "sink", "data": {"operatorType": "sink", "config": {"table_name": "user_summary"}}}
        ],
        "edges": [
            {"source": "src", "target": "filter"},
            {"source": "filter", "target": "agg"},
            {"source": "agg", "target": "sink"}
        ]
    }

    # Same database connector for source and target
    decision = IntelligentExecutionPlanner.plan_dataflow(
        graph_json=graph,
        source_connector=conn,
        target_connector=conn,
        strategy=PlannerStrategy.AUTO
    )

    assert decision.selected_engine == ExecutionEngineType.SQL_PUSHDOWN
    assert decision.strategy_applied == PlannerStrategy.AUTO


def test_planner_latency_benchmark():
    """
    Empirical benchmark testing decision planning latency.
    Runs 1,000 full planning evaluations to ensure sub-millisecond execution.
    """
    profile = WorkloadProfile(
        estimated_bytes=5 * 1024 * 1024 * 1024,
        transformation_complexity_score=4,
        has_joins=True,
        has_aggregations=True,
        is_same_database_instance=False,
        spark_available=True
    )

    iterations = 1000
    start_time = time.time()
    for _ in range(iterations):
        dec = IntelligentExecutionPlanner.plan(profile, strategy=PlannerStrategy.AUTO)
    total_time = time.time() - start_time

    avg_latency_ms = (total_time / iterations) * 1000

    print(f"\n[BENCHMARK] Planner 1,000 Evaluations Time: {total_time:.4f}s")
    print(f"[BENCHMARK] Average Decision Planning Latency: {avg_latency_ms:.4f} ms per plan")
    print(f"[BENCHMARK] Winner Selected: {dec.selected_engine.value} (Confidence: {dec.confidence_score})")

    # Strict constraint: planner overhead must be < 1.0 ms
    assert avg_latency_ms < 1.0
