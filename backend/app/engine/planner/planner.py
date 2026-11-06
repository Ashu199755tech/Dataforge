import time
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.app.connectors.base import BaseConnector
from backend.app.engine.spark.session import SparkSessionManager
from backend.app.engine.pushdown.analyzer import SQLPushdownAnalyzer
from backend.app.engine.planner.models import (
    ExecutionEngineType,
    PlannerStrategy,
    WorkloadProfile,
    PlanDecision,
    EngineSuitabilityScore
)
from backend.app.engine.planner.cost_model import (
    TransformationComplexityScorer,
    DataVolumeEstimator,
    EngineCostCalculator
)


class IntelligentExecutionPlanner:
    """
    DataForge Intelligent Execution Planner.
    Evaluates data volume, transformation complexity, connector capabilities,
    network bandwidth, and runtime availability to automatically select the optimal
    engine (COPY, SPARK, or SQL_PUSHDOWN), while respecting explicit developer overrides.
    """

    @classmethod
    def plan(
        cls,
        profile: WorkloadProfile,
        strategy: PlannerStrategy = PlannerStrategy.AUTO
    ) -> PlanDecision:
        """
        Evaluates a workload profile and returns the optimal engine execution decision.
        """
        start_time = time.time()

        # 1. Handle Developer Overrides
        if strategy == PlannerStrategy.FORCE_COPY:
            return PlanDecision(
                selected_engine=ExecutionEngineType.COPY,
                strategy_applied=strategy,
                confidence_score=1.0,
                scores={ExecutionEngineType.COPY.value: 100.0},
                explanation="Execution forced to COPY engine by explicit user override.",
                primary_reason="User Override",
                fallback_engine=None,
                profile_summary=profile.model_dump()
            )
        elif strategy == PlannerStrategy.FORCE_SPARK:
            return PlanDecision(
                selected_engine=ExecutionEngineType.SPARK,
                strategy_applied=strategy,
                confidence_score=1.0,
                scores={ExecutionEngineType.SPARK.value: 100.0},
                explanation="Execution forced to SPARK engine by explicit user override.",
                primary_reason="User Override",
                fallback_engine=ExecutionEngineType.COPY,
                profile_summary=profile.model_dump()
            )
        elif strategy == PlannerStrategy.FORCE_SQL_PUSHDOWN:
            return PlanDecision(
                selected_engine=ExecutionEngineType.SQL_PUSHDOWN,
                strategy_applied=strategy,
                confidence_score=1.0,
                scores={ExecutionEngineType.SQL_PUSHDOWN.value: 100.0},
                explanation="Execution forced to SQL_PUSHDOWN engine by explicit user override.",
                primary_reason="User Override",
                fallback_engine=ExecutionEngineType.COPY,
                profile_summary=profile.model_dump()
            )

        # 2. Automated Multi-Factor Cost Scoring
        scores = EngineCostCalculator.score_all(profile)
        sorted_engines = sorted(scores.items(), key=lambda item: item[1].score, reverse=True)

        winner_engine, winner_score_obj = sorted_engines[0]
        runner_up_engine, runner_up_score_obj = sorted_engines[1]

        # Calculate confidence: delta between 1st and 2nd relative to 100
        delta = max(0.0, winner_score_obj.score - runner_up_score_obj.score)
        confidence = round(min(1.0, max(0.5, 0.5 + (delta / 100.0))), 2)

        # Build detailed explanation
        reasons_text = "; ".join(winner_score_obj.reasons) if winner_score_obj.reasons else "Highest overall score."
        explanation = (
            f"Selected {winner_engine.value} with score {winner_score_obj.score:.1f}/100 "
            f"(Runner-up: {runner_up_engine.value} at {runner_up_score_obj.score:.1f}/100). "
            f"Rationale: {reasons_text}"
        )

        primary_reason = winner_score_obj.reasons[0] if winner_score_obj.reasons else "Score Optimization"

        # Determine sensible fallback
        fallback = runner_up_engine
        if winner_engine == ExecutionEngineType.SPARK and not profile.spark_available:
            # If Spark won but is unavailable, fallback immediately to runner up
            fallback = ExecutionEngineType.COPY

        return PlanDecision(
            selected_engine=winner_engine,
            strategy_applied=strategy,
            confidence_score=confidence,
            scores={k.value: round(v.score, 1) for k, v in scores.items()},
            explanation=explanation,
            primary_reason=primary_reason,
            fallback_engine=fallback,
            profile_summary=profile.model_dump()
        )

    @classmethod
    def plan_dataflow(
        cls,
        graph_json: Dict[str, Any],
        source_connector: Optional[BaseConnector] = None,
        target_connector: Optional[BaseConnector] = None,
        strategy: PlannerStrategy = PlannerStrategy.AUTO,
        estimated_bytes: Optional[int] = None,
        estimated_rows: Optional[int] = None
    ) -> PlanDecision:
        """
        Extracts workload features from a Visual Data Flow graph and generates an execution plan.
        """
        complexity_score, features = TransformationComplexityScorer.score_graph(graph_json)

        # Check PySpark environment
        spark_ready = SparkSessionManager.is_spark_available()

        # Check pushdown eligibility
        pushdown_check = SQLPushdownAnalyzer.analyze_graph(
            graph_json=graph_json,
            source_connector=source_connector,
            target_connector=target_connector
        )

        # Database affinity checks
        is_same_db = False
        if source_connector and target_connector:
            src_conn = source_connector.config.get("connection_id") or source_connector.config.get("database_path") or source_connector.config.get("database")
            tgt_conn = target_connector.config.get("connection_id") or target_connector.config.get("database_path") or target_connector.config.get("database")
            if src_conn and tgt_conn and src_conn == tgt_conn:
                is_same_db = True

        src_type = source_connector.__class__.__name__ if source_connector else None
        tgt_type = target_connector.__class__.__name__ if target_connector else None

        profile = WorkloadProfile(
            estimated_bytes=estimated_bytes,
            estimated_rows=estimated_rows,
            transformation_complexity_score=complexity_score,
            has_joins=features["has_joins"],
            has_aggregations=features["has_aggregations"],
            has_window_functions=features["has_window_functions"],
            has_custom_udf=features["has_custom_udf"],
            is_same_database_instance=is_same_db,
            is_source_database=bool(source_connector and "storage" not in str(type(source_connector)).lower()),
            is_target_database=bool(target_connector and "storage" not in str(type(target_connector)).lower()),
            source_connector_type=src_type,
            target_connector_type=tgt_type,
            spark_available=spark_ready,
            database_supports_pushdown=pushdown_check.can_pushdown
        )

        return cls.plan(profile=profile, strategy=strategy)

    @classmethod
    def plan_copy_activity(
        cls,
        activity_config: Dict[str, Any],
        source_connector: Optional[BaseConnector] = None,
        target_connector: Optional[BaseConnector] = None,
        strategy: PlannerStrategy = PlannerStrategy.AUTO,
        estimated_bytes: Optional[int] = None
    ) -> PlanDecision:
        """
        Generates an execution plan for a Copy Data activity.
        """
        spark_ready = SparkSessionManager.is_spark_available()

        is_same_db = False
        if source_connector and target_connector:
            src_conn = source_connector.config.get("connection_id") or source_connector.config.get("database_path") or source_connector.config.get("database")
            tgt_conn = target_connector.config.get("connection_id") or target_connector.config.get("database_path") or target_connector.config.get("database")
            if src_conn and tgt_conn and src_conn == tgt_conn:
                is_same_db = True

        # Copy data activities have low complexity (mappings and filters only)
        mappings = activity_config.get("column_mappings") or []
        has_filter = bool(activity_config.get("source", {}).get("filter_expr"))
        complexity = 1 if (mappings or has_filter) else 0

        profile = WorkloadProfile(
            estimated_bytes=estimated_bytes,
            transformation_complexity_score=complexity,
            is_same_database_instance=is_same_db,
            is_source_database=bool(source_connector and "storage" not in str(type(source_connector)).lower()),
            is_target_database=bool(target_connector and "storage" not in str(type(target_connector)).lower()),
            spark_available=spark_ready,
            database_supports_pushdown=is_same_db
        )

        return cls.plan(profile=profile, strategy=strategy)
