from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext
from backend.app.activities.registry import activity_registry, ActivityMetadata
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.sql_script import SqlScriptActivity
from backend.app.activities.data_quality import DataQualityActivity
from backend.app.activities.data_profiling import DataProfilingActivity
from backend.app.activities.reconciliation import ReconciliationActivity
from backend.app.activities.data_masking import DataMaskingActivity
from backend.app.activities.lookup import LookupActivity
from backend.app.activities.set_variable import SetVariableActivity
from backend.app.activities.wait import WaitActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.activities.rest_api import RestApiActivity
from backend.app.activities.get_metadata import GetMetadataActivity
from backend.app.activities.delete_data import DeleteDataActivity
from backend.app.activities.for_each import ForEachActivity
from backend.app.activities.execute_pipeline import ExecutePipelineActivity
from backend.app.activities.switch_condition import SwitchActivity
from backend.app.activities.filter_activity import FilterActivity
from backend.app.activities.fail_activity import FailActivity
from backend.app.activities.append_variable import AppendVariableActivity
from backend.app.activities.until import UntilActivity
from backend.app.activities.python_script import PythonScriptActivity
from backend.app.activities.stored_procedure import StoredProcedureActivity
from backend.app.activities.custom_activity import CustomActivity
from backend.app.activities.databricks import DatabricksNotebookActivity
from backend.app.activities.pyspark_job import PySparkJobActivity
from backend.app.activities.web import WebActivity
from backend.app.activities.webhook import WebhookActivity
from backend.app.activities.validation import ValidationActivity
from backend.app.activities.file_operation import FileOperationActivity
from backend.app.activities.archive import ArchiveActivity
from backend.app.activities.data_flow import ExecuteDataFlowActivity
from backend.app.activities.pipeline_return_value import PipelineReturnValueActivity
from backend.app.activities.dbt import DbtActivity
from backend.app.activities.cdc import CDCReplicationActivity
from backend.app.activities.reverse_etl import ReverseETLActivity


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
            category="Data Quality & Governance",
            description="Enforces data integrity, mandatory fields, null limits, uniqueness, ranges, dates, PII, and SLA score thresholds.",
            version="2.0.0",
            icon="ShieldCheck",
            config_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "file_path": {"type": "string"},
                    "rules": {"type": "array"},
                    "min_score_threshold": {"type": "number", "default": 100.0},
                    "quarantine_path": {"type": "string"},
                    "fail_pipeline_on_error": {"type": "boolean", "default": True}
                }
            },
            outputs=[
                {"name": "dq_score", "type": "number"},
                {"name": "overall_status", "type": "string"},
                {"name": "rules_passed", "type": "int"},
                {"name": "rules_failed", "type": "int"},
                {"name": "quarantine_count", "type": "int"},
                {"name": "rule_results", "type": "array"}
            ],
            supports_retry=False,
            tags=["DataQuality", "Governance", "SLA", "Validation", "PII"]
        ),
        DataQualityActivity,
        aliases=["dq_check", "data_quality", "DataQuality"]
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

    # 9. Get Metadata
    activity_registry.register(
        ActivityMetadata(
            activity_type="GetMetadata",
            display_name="Get Metadata",
            category="Move & Transform",
            description="Inspects datasets to discover existence, row counts, column counts, structure, and byte size.",
            version="1.0.0",
            icon="FileSearch",
            config_schema={
                "type": "object",
                "required": ["connection_id", "table_name"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "schema_name": {"type": "string"},
                    "field_list": {"type": "array"}
                }
            },
            outputs=[
                {"name": "exists", "type": "boolean"},
                {"name": "rowCount", "type": "int"},
                {"name": "columnCount", "type": "int"},
                {"name": "sizeInBytes", "type": "int"},
                {"name": "structure", "type": "array"}
            ],
            supports_retry=True,
            tags=["Metadata", "Discovery", "Move & Transform", "Schema"]
        ),
        GetMetadataActivity,
        aliases=["get_metadata", "getmetadata"]
    )

    # 10. Delete Data
    activity_registry.register(
        ActivityMetadata(
            activity_type="DeleteData",
            display_name="Delete Data",
            category="Move & Transform",
            description="Safely removes records conditionally or truncates tables to prepare staging environments.",
            version="1.0.0",
            icon="Trash2",
            config_schema={
                "type": "object",
                "required": ["connection_id", "table_name"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "schema_name": {"type": "string"},
                    "delete_mode": {"type": "string", "enum": ["conditional", "truncate"]},
                    "filter_expr": {"type": "string"}
                }
            },
            outputs=[
                {"name": "rows_deleted", "type": "int"}
            ],
            supports_retry=False,
            tags=["Cleanup", "Delete", "Staging", "Move & Transform"]
        ),
        DeleteDataActivity,
        aliases=["delete_data", "deletedata"]
    )

    # 11. ForEach
    activity_registry.register(
        ActivityMetadata(
            activity_type="ForEach",
            display_name="ForEach",
            category="Control Flow",
            description="Iterates through an array of items and executes sub-activities sequentially or in parallel.",
            version="1.0.0",
            icon="Repeat",
            config_schema={
                "type": "object",
                "required": ["items", "activities"],
                "properties": {
                    "items": {"type": "any"},
                    "is_sequential": {"type": "boolean", "default": False},
                    "batch_count": {"type": "integer", "default": 4},
                    "activities": {"type": "array"}
                }
            },
            outputs=[
                {"name": "item_count", "type": "int"},
                {"name": "succeeded_count", "type": "int"},
                {"name": "failed_count", "type": "int"}
            ],
            supports_retry=False,
            tags=["Iteration", "Parallel", "Loop", "Control Flow"]
        ),
        ForEachActivity,
        aliases=["for_each", "foreach"]
    )

    # 12. Execute Pipeline
    activity_registry.register(
        ActivityMetadata(
            activity_type="ExecutePipeline",
            display_name="Execute Pipeline",
            category="Control Flow",
            description="Invokes another pipeline with parameter mapping and waits for completion.",
            version="1.0.0",
            icon="Workflow",
            config_schema={
                "type": "object",
                "properties": {
                    "pipeline_id": {"type": "string"},
                    "pipeline_name": {"type": "string"},
                    "parameters": {"type": "object"},
                    "wait_on_completion": {"type": "boolean", "default": True}
                }
            },
            outputs=[
                {"name": "child_run_id", "type": "string"},
                {"name": "child_status", "type": "string"},
                {"name": "duration_seconds", "type": "int"}
            ],
            supports_retry=True,
            tags=["ChildPipeline", "Hierarchy", "SubPipeline", "Control Flow"]
        ),
        ExecutePipelineActivity,
        aliases=["execute_pipeline", "executepipeline"]
    )

    # 13. Switch
    activity_registry.register(
        ActivityMetadata(
            activity_type="Switch",
            display_name="Switch",
            category="Control Flow",
            description="Evaluates an expression and routes execution to matching case branches.",
            version="1.0.0",
            icon="Split",
            config_schema={
                "type": "object",
                "required": ["expression"],
                "properties": {
                    "expression": {"type": "string"},
                    "cases": {"type": "array"},
                    "default_activities": {"type": "array"}
                }
            },
            outputs=[
                {"name": "matched_case", "type": "string"},
                {"name": "evaluated_value", "type": "string"}
            ],
            supports_retry=False,
            tags=["Branching", "Condition", "Switch", "Control Flow"]
        ),
        SwitchActivity,
        aliases=["switch_condition", "switchactivity"]
    )

    # 14. Filter
    activity_registry.register(
        ActivityMetadata(
            activity_type="Filter",
            display_name="Filter",
            category="Control Flow",
            description="Filters an array of elements based on a dynamic boolean condition.",
            version="1.0.0",
            icon="Filter",
            config_schema={
                "type": "object",
                "required": ["items", "condition"],
                "properties": {
                    "items": {"type": "any"},
                    "condition": {"type": "string"}
                }
            },
            outputs=[
                {"name": "value", "type": "array"},
                {"name": "count", "type": "int"}
            ],
            supports_retry=False,
            tags=["Array", "Filter", "Transform", "Control Flow"]
        ),
        FilterActivity,
        aliases=["filter_activity", "filteractivity"]
    )

    # 15. Fail
    activity_registry.register(
        ActivityMetadata(
            activity_type="Fail",
            display_name="Fail",
            category="Control Flow",
            description="Deliberately triggers an activity failure with custom message and code.",
            version="1.0.0",
            icon="AlertOctagon",
            config_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "error_code": {"type": "string"}
                }
            },
            outputs=[
                {"name": "error_code", "type": "string"},
                {"name": "message", "type": "string"}
            ],
            supports_retry=False,
            tags=["Error", "Abort", "Guardrail", "Control Flow"]
        ),
        FailActivity,
        aliases=["fail_activity", "failactivity"]
    )

    # 16. Append Variable
    activity_registry.register(
        ActivityMetadata(
            activity_type="AppendVariable",
            display_name="Append Variable",
            category="Control Flow",
            description="Appends a dynamic value or object to an existing array pipeline variable.",
            version="1.0.0",
            icon="ListPlus",
            config_schema={
                "type": "object",
                "required": ["variable_name", "value"],
                "properties": {
                    "variable_name": {"type": "string"},
                    "value": {"type": "any"}
                }
            },
            outputs=[
                {"name": "appended_value", "type": "any"}
            ],
            supports_retry=False,
            tags=["Variables", "Array", "State", "Control Flow"]
        ),
        AppendVariableActivity,
        aliases=["append_variable", "appendvariable"]
    )

    # 17. Until
    activity_registry.register(
        ActivityMetadata(
            activity_type="Until",
            display_name="Until",
            category="Control Flow",
            description="Executes sub-activities repeatedly until a boolean condition evaluates to True.",
            version="1.0.0",
            icon="RotateCw",
            config_schema={
                "type": "object",
                "required": ["expression", "activities"],
                "properties": {
                    "expression": {"type": "string"},
                    "activities": {"type": "array"},
                    "max_iterations": {"type": "integer", "default": 10}
                }
            },
            outputs=[
                {"name": "iterations_completed", "type": "int"},
                {"name": "condition_met", "type": "boolean"}
            ],
            supports_retry=False,
            tags=["Loop", "Until", "Break", "Control Flow"]
        ),
        UntilActivity,
        aliases=["until_activity", "untilactivity"]
    )

    # 18. Python Script
    activity_registry.register(
        ActivityMetadata(
            activity_type="PythonScript",
            display_name="Python Script",
            category="Compute & External",
            description="Executes arbitrary Python code in an isolated worker process with strict timeouts and output capture.",
            version="1.0.0",
            icon="Terminal",
            config_schema={
                "type": "object",
                "required": ["script"],
                "properties": {
                    "script": {"type": "string"},
                    "parameters": {"type": "object"},
                    "timeout_seconds": {"type": "integer", "default": 60}
                }
            },
            outputs=[
                {"name": "output_variables", "type": "object"},
                {"name": "duration_seconds", "type": "number"}
            ],
            supports_retry=True,
            tags=["Python", "DataScience", "Worker", "Compute"]
        ),
        PythonScriptActivity,
        aliases=["python_script", "python"]
    )

    # 19. Stored Procedure
    activity_registry.register(
        ActivityMetadata(
            activity_type="StoredProcedure",
            display_name="Stored Procedure",
            category="Compute & External",
            description="Executes a database stored procedure or function with parameter bindings.",
            version="1.0.0",
            icon="DatabaseZap",
            config_schema={
                "type": "object",
                "required": ["connection_id", "stored_procedure_name"],
                "properties": {
                    "connection_id": {"type": "string"},
                    "stored_procedure_name": {"type": "string"},
                    "parameters": {"type": "object"},
                    "is_function": {"type": "boolean", "default": False}
                }
            },
            outputs=[
                {"name": "row_count", "type": "int"},
                {"name": "first_row", "type": "object"}
            ],
            supports_retry=True,
            tags=["StoredProcedure", "Database", "Compute", "SQL"]
        ),
        StoredProcedureActivity,
        aliases=["stored_procedure", "storedprocedure"]
    )

    # 20. Custom Activity
    activity_registry.register(
        ActivityMetadata(
            activity_type="CustomActivity",
            display_name="Custom Activity",
            category="Compute & External",
            description="Executes a CLI command, script binary, or batch process in an isolated environment.",
            version="1.0.0",
            icon="Cpu",
            config_schema={
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string"},
                    "arguments": {"type": "array"},
                    "timeout_seconds": {"type": "integer", "default": 120}
                }
            },
            outputs=[
                {"name": "exit_code", "type": "int"},
                {"name": "duration_seconds", "type": "number"}
            ],
            supports_retry=True,
            tags=["CLI", "Command", "Custom", "Compute"]
        ),
        CustomActivity,
        aliases=["custom_activity", "customactivity"]
    )

    # 21. Databricks Notebook
    activity_registry.register(
        ActivityMetadata(
            activity_type="DatabricksNotebook",
            display_name="Databricks Notebook",
            category="Compute & External",
            description="Submits and orchestrates remote Databricks notebooks via the official Jobs API 2.1.",
            version="1.0.0",
            icon="CloudLightning",
            config_schema={
                "type": "object",
                "required": ["notebook_path"],
                "properties": {
                    "host": {"type": "string"},
                    "token": {"type": "string"},
                    "notebook_path": {"type": "string"},
                    "base_parameters": {"type": "object"}
                }
            },
            outputs=[
                {"name": "run_id", "type": "string"},
                {"name": "result_state", "type": "string"}
            ],
            supports_retry=True,
            tags=["Databricks", "Notebook", "Spark", "Compute", "Cloud"]
        ),
        DatabricksNotebookActivity,
        aliases=["databricks_notebook", "databricks"]
    )

    # 22. PySpark Job
    activity_registry.register(
        ActivityMetadata(
            activity_type="PySparkJob",
            display_name="PySpark Job",
            category="Compute & External",
            description="Submits distributed Spark applications with master cluster parameters and memory configuration.",
            version="1.0.0",
            icon="Flame",
            config_schema={
                "type": "object",
                "required": ["script_path"],
                "properties": {
                    "script_path": {"type": "string"},
                    "master": {"type": "string", "default": "local[*]"},
                    "spark_args": {"type": "array"}
                }
            },
            outputs=[
                {"name": "exit_code", "type": "int"}
            ],
            supports_retry=True,
            tags=["PySpark", "Spark", "Distributed", "BigData", "Compute"]
        ),
        PySparkJobActivity,
        aliases=["pyspark_job", "pyspark", "spark_job"]
    )

    # 23. Web Activity
    activity_registry.register(
        ActivityMetadata(
            activity_type="WebActivity",
            display_name="Web Activity",
            category="File & API Integration",
            description="Executes custom HTTP/S requests with authentication, payload formatting, and response parsing.",
            version="1.0.0",
            icon="Globe",
            config_schema={
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                    "timeout_seconds": {"type": "integer", "default": 30}
                }
            },
            outputs=[
                {"name": "status_code", "type": "int"},
                {"name": "response", "type": "object"},
                {"name": "duration_seconds", "type": "number"}
            ],
            supports_retry=True,
            tags=["HTTP", "REST", "API", "Web"]
        ),
        WebActivity,
        aliases=["web_activity", "web", "http"]
    )

    # 24. Webhook Activity
    activity_registry.register(
        ActivityMetadata(
            activity_type="Webhook",
            display_name="Webhook",
            category="File & API Integration",
            description="Dispatches external notification with unique callback URL and awaits asynchronous callback completion.",
            version="1.0.0",
            icon="Send",
            config_schema={
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string"},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                    "timeout_seconds": {"type": "integer", "default": 300}
                }
            },
            outputs=[
                {"name": "callback_data", "type": "object"},
                {"name": "duration_seconds", "type": "number"}
            ],
            supports_retry=False,
            tags=["Webhook", "Callback", "Async", "Integration"]
        ),
        WebhookActivity,
        aliases=["webhook_activity", "webhook"]
    )

    # 25. Validation Activity
    activity_registry.register(
        ActivityMetadata(
            activity_type="Validation",
            display_name="Validation",
            category="Control Flow",
            description="Polls and verifies dataset or file availability and minimum size thresholds before proceeding.",
            version="1.0.0",
            icon="CheckCheck",
            config_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "dataset_name": {"type": "string"},
                    "file_path": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "default": 60},
                    "sleep_interval_seconds": {"type": "integer", "default": 5}
                }
            },
            outputs=[
                {"name": "exists", "type": "boolean"},
                {"name": "size_bytes", "type": "int"},
                {"name": "row_count", "type": "int"}
            ],
            supports_retry=False,
            tags=["Validation", "Sensing", "Gates", "Prerequisites"]
        ),
        ValidationActivity,
        aliases=["validation_activity", "validate", "check_exists"]
    )

    # 26. File Operation
    activity_registry.register(
        ActivityMetadata(
            activity_type="FileOperation",
            display_name="File Operation",
            category="File & Storage",
            description="Performs copy, move, delete, rename, or existence checks across file system paths.",
            version="1.0.0",
            icon="FolderCog",
            config_schema={
                "type": "object",
                "required": ["source_path"],
                "properties": {
                    "operation": {"type": "string", "enum": ["copy", "move", "delete", "rename", "file_exists"]},
                    "source_path": {"type": "string"},
                    "destination_path": {"type": "string"}
                }
            },
            outputs=[
                {"name": "affected_count", "type": "int"},
                {"name": "affected_files", "type": "array"}
            ],
            supports_retry=True,
            tags=["File", "Filesystem", "Storage", "Maintenance"]
        ),
        FileOperationActivity,
        aliases=["file_operation", "file_transfer", "file_exists"]
    )

    # 27. Archive Activity
    activity_registry.register(
        ActivityMetadata(
            activity_type="Archive",
            display_name="Archive & Compression",
            category="File & Storage",
            description="Compresses files into .zip/.tar.gz archives or extracts compressed packages to a folder.",
            version="1.0.0",
            icon="Archive",
            config_schema={
                "type": "object",
                "required": ["source_path", "destination_path"],
                "properties": {
                    "action": {"type": "string", "enum": ["compress", "extract"]},
                    "format": {"type": "string", "default": "zip"},
                    "source_path": {"type": "string"},
                    "destination_path": {"type": "string"}
                }
            },
            outputs=[
                {"name": "archive_size_bytes", "type": "int"},
                {"name": "extracted_count", "type": "int"}
            ],
            supports_retry=True,
            tags=["Archive", "Zip", "Tar", "Compression", "Storage"]
        ),
        ArchiveActivity,
        aliases=["archive_activity", "unzip", "extract", "compress"]
    )

    # 28. Execute Data Flow
    activity_registry.register(
        ActivityMetadata(
            activity_type="ExecuteDataFlow",
            display_name="Data Flow",
            category="Move & Transform",
            description="Executes a visual mapping transformation graph with vectorized Polars and Spark compilation.",
            version="1.0.0",
            icon="Workflow",
            config_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "dataflow_id": {"type": "string"},
                    "dataflow_name": {"type": "string"}
                }
            },
            outputs=[
                {"name": "total_rows_read", "type": "int"},
                {"name": "total_rows_written", "type": "int"},
                {"name": "duration_seconds", "type": "number"}
            ],
            supports_retry=True,
            tags=["DataFlow", "ETL", "Transformation", "Mapping", "Vectorized"]
        ),
        ExecuteDataFlowActivity,
        aliases=["execute_dataflow", "data_flow", "mapping_data_flow"]
    )

    # 29. Data Profiling
    activity_registry.register(
        ActivityMetadata(
            activity_type="DataProfiling",
            display_name="Data Profiling",
            category="Data Quality & Governance",
            description="Generates exhaustive column statistics, null distributions, distinct counts, and frequent value histograms.",
            version="1.0.0",
            icon="BarChart3",
            config_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "connection_id": {"type": "string"},
                    "table_name": {"type": "string"},
                    "file_path": {"type": "string"}
                }
            },
            outputs=[
                {"name": "total_rows", "type": "int"},
                {"name": "total_columns", "type": "int"},
                {"name": "columns", "type": "array"}
            ],
            supports_retry=True,
            tags=["Profiling", "Statistics", "DataQuality", "Metadata"]
        ),
        DataProfilingActivity,
        aliases=["data_profiling", "profile_dataset"]
    )

    # 30. Reconciliation
    activity_registry.register(
        ActivityMetadata(
            activity_type="Reconciliation",
            display_name="Reconciliation",
            category="Data Quality & Governance",
            description="Source-to-Target automated reconciliation validating row parity, key discrepancies, and numeric sum checksums.",
            version="1.0.0",
            icon="Scale",
            config_schema={
                "type": "object",
                "required": [],
                "properties": {
                    "source_connection_id": {"type": "string"},
                    "source_table_name": {"type": "string"},
                    "source_file_path": {"type": "string"},
                    "target_connection_id": {"type": "string"},
                    "target_table_name": {"type": "string"},
                    "target_file_path": {"type": "string"},
                    "key_columns": {"type": "array"},
                    "numeric_sum_columns": {"type": "array"},
                    "fail_on_discrepancy": {"type": "boolean", "default": True}
                }
            },
            outputs=[
                {"name": "source_records", "type": "int"},
                {"name": "target_records", "type": "int"},
                {"name": "row_variance", "type": "int"},
                {"name": "reconciliation_status", "type": "string"}
            ],
            supports_retry=True,
            tags=["Reconciliation", "Audit", "Parity", "DataQuality"]
        ),
        ReconciliationActivity,
        aliases=["reconciliation", "data_reconciliation", "compare_datasets"]
    )

    # 31. Data Masking
    activity_registry.register(
        ActivityMetadata(
            activity_type="DataMasking",
            display_name="Data Masking",
            category="Data Quality & Governance",
            description="Applies obfuscation, redaction, hashing, and partial masking to sensitive PII and confidential fields.",
            version="1.0.0",
            icon="ShieldAlert",
            config_schema={
                "type": "object",
                "required": ["masking_rules"],
                "properties": {
                    "source_connection_id": {"type": "string"},
                    "source_table_name": {"type": "string"},
                    "source_file_path": {"type": "string"},
                    "destination_file_path": {"type": "string"},
                    "masking_rules": {"type": "array"}
                }
            },
            outputs=[
                {"name": "masked_records_count", "type": "int"},
                {"name": "destination_file_path", "type": "string"}
            ],
            supports_retry=True,
            tags=["Security", "Masking", "PII", "Redaction", "Governance"]
        ),
        DataMaskingActivity,
        aliases=["data_masking", "mask_pii", "anonymize"]
    )

    # 32. Pipeline Return Value
    activity_registry.register(
        ActivityMetadata(
            activity_type="PipelineReturnValue",
            display_name="Pipeline Return Value",
            category="Control Flow",
            description="Returns structured values, flags, and compute metrics from a child pipeline back to parent callers.",
            version="1.0.0",
            icon="CornerDownLeft",
            config_schema={
                "type": "object",
                "required": ["value"],
                "properties": {
                    "value": {"type": "object"}
                }
            },
            outputs=[
                {"name": "pipelineReturnValue", "type": "object"}
            ],
            supports_retry=False,
            tags=["ControlFlow", "ReturnValue", "Output", "Subpipeline"]
        ),
        PipelineReturnValueActivity,
        aliases=["pipeline_return_value", "return_value", "set_return_value"]
    )

    # 33. dbt (Data Build Tool)
    activity_registry.register(
        ActivityMetadata(
            activity_type="Dbt",
            display_name="dbt Transformation",
            category="Compute & External",
            description="Orchestrates dbt Core CLI models or dbt Cloud jobs with model selection and parameterization.",
            version="1.0.0",
            icon="Boxes",
            config_schema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["core", "cloud"], "default": "core"},
                    "command": {"type": "string", "default": "run"},
                    "select": {"type": "string"},
                    "project_dir": {"type": "string"},
                    "target": {"type": "string"},
                    "account_id": {"type": "string"},
                    "job_id": {"type": "string"}
                }
            },
            outputs=[
                {"name": "status", "type": "string"},
                {"name": "models_run", "type": "int"},
                {"name": "models_passed", "type": "int"},
                {"name": "models_failed", "type": "int"},
                {"name": "duration_seconds", "type": "float"}
            ],
            supports_retry=True,
            tags=["dbt", "Transformation", "DataOps", "ELT", "Compute"]
        ),
        DbtActivity,
        aliases=["dbt", "dbt_activity", "dbt_run", "dbt_cloud", "DbtActivity"]
    )

    # 17. Incremental CDC Replication Stream
    activity_registry.register(
        ActivityMetadata(
            activity_type="CDCReplication",
            display_name="CDC Replication",
            category="Move & Transform",
            description="Continuous or micro-batched transaction log CDC replication (Debezium/WAL) with upsert, delete, and audit logging.",
            version="1.0.0",
            icon="Radio",
            config_schema={
                "type": "object",
                "required": ["source", "destination"],
                "properties": {
                    "source": {"type": "object"},
                    "destination": {"type": "object"},
                    "key_columns": {"type": "array"},
                    "soft_delete": {"type": "boolean"},
                    "audit_mode": {"type": "boolean"}
                }
            },
            outputs=[
                {"name": "events_processed", "type": "int"},
                {"name": "inserts", "type": "int"},
                {"name": "updates", "type": "int"},
                {"name": "deletes", "type": "int"},
                {"name": "highest_lsn", "type": "string"},
                {"name": "duration_seconds", "type": "float"}
            ],
            supports_retry=True,
            tags=["CDC", "Debezium", "WAL", "Streaming", "Replication"]
        ),
        CDCReplicationActivity,
        aliases=["cdc", "cdc_replication", "debezium", "CDCReplicationActivity"]
    )

    # 18. Reverse ETL Sync
    activity_registry.register(
        ActivityMetadata(
            activity_type="ReverseETL",
            display_name="Reverse ETL",
            category="Compute & External",
            description="Synchronizes analytical models from warehouses into operational tools: Salesforce, HubSpot, Slack, and Webhooks.",
            version="1.0.0",
            icon="Send",
            config_schema={
                "type": "object",
                "required": ["destination"],
                "properties": {
                    "source": {"type": "object"},
                    "destination": {"type": "object"},
                    "target_object": {"type": "string"},
                    "external_id_field": {"type": "string"},
                    "field_mappings": {"type": "array"},
                    "sync_mode": {"type": "string", "enum": ["upsert", "insert", "update"]}
                }
            },
            outputs=[
                {"name": "records_synced", "type": "int"},
                {"name": "records_failed", "type": "int"},
                {"name": "target_object", "type": "string"},
                {"name": "destination_type", "type": "string"},
                {"name": "duration_seconds", "type": "float"}
            ],
            supports_retry=True,
            tags=["ReverseETL", "Salesforce", "HubSpot", "Slack", "Webhook", "OperationalAnalytics"]
        ),
        ReverseETLActivity,
        aliases=["reverse_etl", "reverseetl", "ReverseETLActivity"]
    )



# Perform registration upon module import
_register_builtin_activities()


def get_activity_instance(context: ActivityExecutionContext, db: Session) -> BaseActivity:
    """
    Instantiates an activity executor using the centralized activity registry.
    Preserves 100% backward compatibility with existing engine execution.
    """
    return activity_registry.create_instance(context, db)
