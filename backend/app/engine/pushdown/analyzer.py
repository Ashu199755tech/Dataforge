from typing import Dict, Any, List, Optional, Set
from backend.app.connectors.base import BaseConnector
from backend.app.engine.pushdown.models import (
    SQLDialect,
    PushdownEligibility
)


class SQLPushdownAnalyzer:
    """
    Evaluates whether a Data Flow transformation graph can be pushed down
    directly into a relational database engine.
    """

    SUPPORTED_OPERATORS: Set[str] = {
        "source",
        "sink",
        "filter",
        "select",
        "derivedcolumn",
        "derived_column",
        "aggregate",
        "join",
        "union",
        "sort",
        "window",
        "surrogatekey",
        "surrogate_key",
        "cast"
    }

    @classmethod
    def detect_dialect_from_connector(cls, connector: Optional[BaseConnector]) -> SQLDialect:
        """Infers the target SQL dialect from a connector instance or config."""
        if connector is None:
            return SQLDialect.ANSI

        conn_name = connector.__class__.__name__.lower()
        cfg_type = (connector.config.get("connector_type") or connector.config.get("type") or "").lower()

        combined = f"{conn_name}_{cfg_type}"
        if "postgres" in combined or "redshift" in combined:
            return SQLDialect.POSTGRESQL
        elif "mysql" in combined:
            return SQLDialect.MYSQL
        elif "sqlite" in combined:
            return SQLDialect.SQLITE
        elif "duckdb" in combined:
            return SQLDialect.DUCKDB
        elif "snowflake" in combined:
            return SQLDialect.SNOWFLAKE
        return SQLDialect.ANSI

    @classmethod
    def analyze_graph(
        cls,
        graph_json: Dict[str, Any],
        source_connector: Optional[BaseConnector] = None,
        target_connector: Optional[BaseConnector] = None
    ) -> PushdownEligibility:
        """
        Analyzes all nodes in a Data Flow graph to check for pushdown eligibility.
        """
        nodes = graph_json.get("nodes", [])
        dialect = cls.detect_dialect_from_connector(target_connector or source_connector)

        if not nodes:
            return PushdownEligibility(
                can_pushdown=False,
                dialect=dialect,
                reason="Graph is empty."
            )

        eligible_nodes: List[str] = []
        ineligible_nodes: List[str] = []

        for node in nodes:
            node_id = node.get("id")
            data = node.get("data", {})
            op_type = (
                data.get("operatorType") or data.get("operator") or node.get("type") or ""
            ).strip().lower()

            if op_type in cls.SUPPORTED_OPERATORS:
                eligible_nodes.append(node_id)
            else:
                ineligible_nodes.append(node_id)

        if ineligible_nodes:
            return PushdownEligibility(
                can_pushdown=False,
                dialect=dialect,
                eligible_nodes=eligible_nodes,
                ineligible_nodes=ineligible_nodes,
                reason=f"Graph contains operators that cannot be pushed down to SQL: {', '.join(ineligible_nodes)}"
            )

        # Check connector consistency if both are provided
        if source_connector and target_connector:
            src_conn_id = source_connector.config.get("connection_id") or source_connector.config.get("database_path") or source_connector.config.get("database")
            tgt_conn_id = target_connector.config.get("connection_id") or target_connector.config.get("database_path") or target_connector.config.get("database")
            if src_conn_id and tgt_conn_id and src_conn_id != tgt_conn_id:
                return PushdownEligibility(
                    can_pushdown=False,
                    dialect=dialect,
                    eligible_nodes=eligible_nodes,
                    reason="Source and destination databases reside in different database instances. Cross-database pushdown requires Copy/Spark engine."
                )

        return PushdownEligibility(
            can_pushdown=True,
            dialect=dialect,
            eligible_nodes=eligible_nodes,
            ineligible_nodes=[],
            reason="All transformation operators are eligible for in-database SQL pushdown."
        )
