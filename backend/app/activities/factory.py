from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext
from backend.app.activities.registry import activity_registry, ActivityMetadata
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.sql_script import SqlScriptActivity
from backend.app.activities.dq_check import DataQualityCheckActivity
from backend.app.activities.lookup import LookupActivity
from backend.app.activities.set_variable import SetVariableActivity
from backend.app.activities.wait import WaitActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.activities.rest_api import RestApiActivity


def _register_builtin_activities():
    """Initializes and registers all core built-in activity executors into the global ActivityRegistry."""
    # 1. Copy Data
    activity_registry.register(
        ActivityMetadata(
            activity_type="CopyData",
            display_name="Copy Data",
            category="Move & Transform",
            description="High-throughput chunked data ingestion, column mapping, upsert/merge, and incremental watermark loading.",
            version="1.0.0",
            icon="ArrowRightLeft",
            config_schema={
                "type": "object",
                "required": ["source", "destination"],
                "properties": {
                    "source": {"type": "object"},
                    "destination": {"type": "object"},
                    "column_mappings": {"type": "array"},
                    "write_behavior": {"type": "string", "enum": ["append", "overwrite", "upsert"]}
                }
            },
            outputs=[
                {"name": "rows_read", "type": "int"},
                {"name": "rows_written", "type": "int"},
                {"name": "bytes_processed", "type": "int"}
            ],
            supports_retry=True,
            tags=["ETL", "ELT", "Ingestion", "CDC"]
        ),
        CopyDataActivity,
        aliases=["copy_data", "copy"]
    )

    # 2. Lookup
    activity_registry.register(
        ActivityMetadata(
            activity_type="Lookup",
            display_name="Lookup",
            category="Move & Transform",
            description="Reads a dataset or first row from a data source and stores result in variable output.",
            version="1.0.0",
            icon="Search",
            config_schema={
                "type": "object",
                "required": ["connection_id"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "query": {"type": "string"},
                    "first_row_only": {"type": "boolean", "default": True}
                }
            },
            outputs=[
                {"name": "first_row", "type": "object"},
                {"name": "count", "type": "int"}
            ],
            supports_retry=True,
            tags=["Lookup", "Metadata", "Variables"]
        ),
        LookupActivity,
        aliases=["lookupactivity"]
    )

    # 3. Data Quality Check
    activity_registry.register(
        ActivityMetadata(
            activity_type="DataQualityCheck",
            display_name="Data Quality",
            category="Move & Transform",
            description="Enforces data integrity, null constraints, row count minimums, and SLA thresholds.",
            version="1.0.0",
            icon="ShieldCheck",
            config_schema={
                "type": "object",
                "required": ["connection_id", "table_name"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "rules": {"type": "array"}
                }
            },
            outputs=[
                {"name": "rules_passed", "type": "int"},
                {"name": "rules_failed", "type": "int"}
            ],
            supports_retry=False,
            tags=["DataQuality", "Governance", "SLA"]
        ),
        DataQualityCheckActivity,
        aliases=["dq_check", "data_quality"]
    )

    # 4. If Condition
    activity_registry.register(
        ActivityMetadata(
            activity_type="IfCondition",
            display_name="If Condition",
            category="Control Flow",
            description="Evaluates a conditional expression to direct downstream execution branches.",
            version="1.0.0",
            icon="GitFork",
            config_schema={
                "type": "object",
                "required": ["expression"],
                "properties": {
                    "expression": {"type": "string"}
                }
            },
            outputs=[
                {"name": "evaluated_result", "type": "boolean"}
            ],
            supports_retry=False,
            tags=["Branching", "ControlFlow", "Logic"]
        ),
        IfConditionActivity,
        aliases=["if_condition", "if"]
    )

    # 5. Set Variable
    activity_registry.register(
        ActivityMetadata(
            activity_type="SetVariable",
            display_name="Set Variable",
            category="Control Flow",
            description="Assigns values to pipeline variables dynamically during execution.",
            version="1.0.0",
            icon="Variable",
            config_schema={
                "type": "object",
                "required": ["variable_name", "value"],
                "properties": {
                    "variable_name": {"type": "string"},
                    "value": {"type": "any"}
                }
            },
            outputs=[
                {"name": "variable_name", "type": "string"},
                {"name": "value", "type": "any"}
            ],
            supports_retry=False,
            tags=["Variables", "ControlFlow", "State"]
        ),
        SetVariableActivity,
        aliases=["set_variable"]
    )

    # 6. Wait
    activity_registry.register(
        ActivityMetadata(
            activity_type="Wait",
            display_name="Wait",
            category="Control Flow",
            description="Pauses pipeline execution for a specified duration.",
            version="1.0.0",
            icon="Clock",
            config_schema={
                "type": "object",
                "required": ["wait_time_in_seconds"],
                "properties": {
                    "wait_time_in_seconds": {"type": "integer", "minimum": 1}
                }
            },
            outputs=[],
            supports_retry=False,
            tags=["Delay", "Timer", "ControlFlow"]
        ),
        WaitActivity,
        aliases=["waitactivity"]
    )

    # 7. SQL Script
    activity_registry.register(
        ActivityMetadata(
            activity_type="SqlScript",
            display_name="SQL Script",
            category="Compute & External",
            description="Executes arbitrary SQL queries or DDL/DML statements on a database connection.",
            version="1.0.0",
            icon="FileCode",
            config_schema={
                "type": "object",
                "required": ["connection_id", "sql"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "sql": {"type": "string"}
                }
            },
            outputs=[
                {"name": "rows_affected", "type": "int"}
            ],
            supports_retry=True,
            tags=["SQL", "Compute", "Database"]
        ),
        SqlScriptActivity,
        aliases=["sql_script", "sql"]
    )

    # 8. REST API Call
    activity_registry.register(
        ActivityMetadata(
            activity_type="RestApi",
            display_name="REST API Call",
            category="Compute & External",
            description="Invokes external HTTP/REST endpoints with request body, headers, and authentication.",
            version="1.0.0",
            icon="Globe",
            config_schema={
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"}
                }
            },
            outputs=[
                {"name": "status_code", "type": "int"},
                {"name": "response_body", "type": "any"}
            ],
            supports_retry=True,
            tags=["HTTP", "REST", "Webhook", "API"]
        ),
        RestApiActivity,
        aliases=["rest_api", "web", "http"]
    )


# Perform registration upon module import
_register_builtin_activities()


def get_activity_instance(context: ActivityExecutionContext, db: Session) -> BaseActivity:
    """
    Instantiates an activity executor using the centralized activity registry.
    Preserves 100% backward compatibility with existing engine execution.
    """
    return activity_registry.create_instance(context, db)
