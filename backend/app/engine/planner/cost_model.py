from typing import Dict, Any, List, Optional, Tuple
from backend.app.connectors.base import BaseConnector
from backend.app.engine.planner.models import (
    ExecutionEngineType,
    WorkloadProfile,
    EngineSuitabilityScore
)


class TransformationComplexityScorer:
    """
    Evaluates transformation graphs and calculates a normalized complexity score (0 to 10).
    Identifies high-cost operators like multi-way joins, window functions, and heavy aggregations.
    """

    OPERATOR_WEIGHTS: Dict[str, int] = {
        "source": 0,
        "sink": 0,
        "select": 1,
        "filter": 1,
        "cast": 1,
        "sort": 2,
        "union": 2,
        "derivedcolumn": 2,
        "derived_column": 2,
        "lookup": 2,
        "aggregate": 3,
        "join": 3,
        "surrogatekey": 3,
        "surrogate_key": 3,
        "window": 4,
        "flatten": 4,
        "unnest": 4,
        "python_script": 5,
        "custom_udf": 5
    }

    @classmethod
    def score_graph(cls, graph_json: Dict[str, Any]) -> Tuple[int, Dict[str, bool]]:
        """
        Computes total complexity score and extracts key transformation features.
        Returns (complexity_score, feature_flags).
        """
        nodes = graph_json.get("nodes", [])
        if not nodes:
            return 0, {
                "has_joins": False,
                "has_aggregations": False,
                "has_window_functions": False,
                "has_custom_udf": False
            }

        total_weight = 0
        has_joins = False
        has_aggregations = False
        has_window_functions = False
        has_custom_udf = False

        for n in nodes:
            data = n.get("data", {})
            op = (
                data.get("operatorType") or data.get("operator") or n.get("type") or ""
            ).strip().lower()

            weight = cls.OPERATOR_WEIGHTS.get(op, 2)
            total_weight += weight

            if op == "join":
                has_joins = True
            elif op == "aggregate":
                has_aggregations = True
            elif op == "window":
                has_window_functions = True
            elif op in ("python_script", "custom_udf"):
                has_custom_udf = True

        # Normalize total weight to 0-10 scale
        # 0: pure movement; 1-3: light; 4-6: moderate; 7-10: complex
        normalized = min(10, max(0, total_weight // 2))

        return normalized, {
            "has_joins": has_joins,
            "has_aggregations": has_aggregations,
            "has_window_functions": has_window_functions,
            "has_custom_udf": has_custom_udf
        }


class DataVolumeEstimator:
    """
    Estimates dataset payload size in bytes and row counts from connector metadata.
    """

    @classmethod
    def estimate_volume(
        cls,
        connector: Optional[BaseConnector],
        object_name: Optional[str] = None,
        schema_name: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Returns (estimated_bytes, estimated_rows).
        """
        if connector is None or not object_name:
            return None, None

        # Check storage connectors
        if hasattr(connector, "get_object_metadata"):
            try:
                # E.g. StorageItem
                container = connector.config.get("bucket") or connector.config.get("container") or "default"
                meta = connector.get_object_metadata(container, object_name)
                sz = getattr(meta, "size_in_bytes", None) or getattr(meta, "size", None)
                if sz:
                    # Estimate ~128 bytes per row average
                    return sz, max(1, sz // 128)
            except Exception:
                pass

        # Check relational connectors
        if hasattr(connector, "get_metadata"):
            try:
                meta = connector.get_metadata(object_name, schema_name)
                sz = meta.get("sizeInBytes")
                rows = meta.get("rowCount")
                return sz, rows
            except Exception:
                pass

        return None, None


class EngineCostCalculator:
    """
    Evaluates engine suitability scores based on workload profiles.
    Evaluates COPY, SPARK, and SQL_PUSHDOWN on a 0-100 scale.
    """

    @classmethod
    def score_all(cls, profile: WorkloadProfile) -> Dict[ExecutionEngineType, EngineSuitabilityScore]:
        return {
            ExecutionEngineType.COPY: cls.score_copy(profile),
            ExecutionEngineType.SQL_PUSHDOWN: cls.score_sql_pushdown(profile),
            ExecutionEngineType.SPARK: cls.score_spark(profile)
        }

    @classmethod
    def score_copy(cls, profile: WorkloadProfile) -> EngineSuitabilityScore:
        score = 70.0
        factors = {}
        reasons = []

        # Complexity penalty / bonus
        if profile.transformation_complexity_score == 0:
            score += 25.0
            factors["pure_data_movement"] = 25.0
            reasons.append("Zero transformation complexity favors high-speed streaming Copy Engine")
        elif profile.transformation_complexity_score <= 2:
            score += 10.0
            factors["light_transformation"] = 10.0
            reasons.append("Simple projections and filters can stream through Arrow transformers")
        elif profile.transformation_complexity_score >= 5:
            score -= 40.0
            factors["high_complexity_penalty"] = -40.0
            reasons.append("Copy Engine does not execute distributed multi-way joins or windowing")

        # Same database instance pushdown penalty
        if profile.is_same_database_instance and profile.database_supports_pushdown:
            score -= 35.0
            factors["unnecessary_extraction_penalty"] = -35.0
            reasons.append("Data already resides in target database; extracting adds redundant network I/O")

        # Memory boundedness
        score += 10.0
        factors["bounded_memory"] = 10.0
        reasons.append("Guarantees bounded RAM <= 64 MB with backpressure")

        # Volume factors
        if profile.estimated_bytes is not None:
            if profile.estimated_bytes < 1024 * 1024 * 1024:  # < 1 GB
                score += 15.0
                factors["small_to_medium_volume"] = 15.0
                reasons.append("Sub-gigabyte volume avoids distributed cluster startup overhead")
            elif profile.estimated_bytes > 50 * 1024 * 1024 * 1024:  # > 50 GB
                if profile.transformation_complexity_score > 2:
                    score -= 20.0
                    factors["large_volume_with_transforms"] = -20.0
                    reasons.append("Multi-gigabyte transformation sets benefit from distributed Spark")

        return EngineSuitabilityScore(
            engine=ExecutionEngineType.COPY,
            score=max(0.0, min(100.0, score)),
            factors=factors,
            reasons=reasons
        )

    @classmethod
    def score_sql_pushdown(cls, profile: WorkloadProfile) -> EngineSuitabilityScore:
        score = 15.0
        factors = {}
        reasons = []

        # Same database instance affinity
        if profile.is_same_database_instance and profile.database_supports_pushdown:
            score += 55.0
            factors["same_database_affinity"] = 55.0
            reasons.append("Source and destination reside in same database; zero network egress ELT")

            if profile.has_aggregations or profile.has_joins:
                score += 15.0
                factors["native_optimizer_advantage"] = 15.0
                reasons.append("Relational database query planner optimizes joins and index lookups")

            if not profile.has_custom_udf:
                score += 10.0
                factors["ansi_sql_compatible"] = 10.0
                reasons.append("All operators map cleanly to standard multi-CTE SQL")
        else:
            if not profile.is_same_database_instance:
                score -= 30.0
                factors["cross_database_penalty"] = -30.0
                reasons.append("Cross-database or cloud storage endpoints cannot execute in-database SQL")

        if profile.has_custom_udf:
            score -= 50.0
            factors["custom_udf_penalty"] = -50.0
            reasons.append("Custom Python scripts and external APIs cannot be pushed down to SQL")

        return EngineSuitabilityScore(
            engine=ExecutionEngineType.SQL_PUSHDOWN,
            score=max(0.0, min(100.0, score)),
            factors=factors,
            reasons=reasons
        )

    @classmethod
    def score_spark(cls, profile: WorkloadProfile) -> EngineSuitabilityScore:
        # Runtime availability: strict gate
        if not profile.spark_available:
            return EngineSuitabilityScore(
                engine=ExecutionEngineType.SPARK,
                score=0.0,
                factors={"spark_unavailable": -100.0},
                reasons=["Apache Spark / PySpark environment is not installed on this host"]
            )

        score = 35.0
        factors = {"spark_ready": 15.0}
        reasons = ["Apache Spark / PySpark environment is ready"]

        # Transformation complexity affinity
        if profile.transformation_complexity_score >= 6:
            score += 30.0
            factors["high_complexity_bonus"] = 30.0
            reasons.append("Complex multi-stage joins, windowing, and aggregations excel on Spark Catalyst")
        elif profile.transformation_complexity_score >= 3:
            score += 15.0
            factors["moderate_complexity_bonus"] = 15.0

        # Data volume scaling
        if profile.estimated_bytes is not None:
            if profile.estimated_bytes >= 10 * 1024 * 1024 * 1024:  # >= 10 GB
                score += 25.0
                factors["large_scale_volume"] = 25.0
                reasons.append("Multi-gigabyte scale requires distributed Spark worker executors")
            elif profile.estimated_bytes < 50 * 1024 * 1024:  # < 50 MB
                score -= 25.0
                factors["tiny_volume_overhead_penalty"] = -25.0
                reasons.append("Tiny datasets suffer from Spark JVM / session initialization overhead")

        return EngineSuitabilityScore(
            engine=ExecutionEngineType.SPARK,
            score=max(0.0, min(100.0, score)),
            factors=factors,
            reasons=reasons
        )
