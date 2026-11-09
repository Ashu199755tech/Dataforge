import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import polars as pl

from backend.app.core.database import SessionLocal
from backend.app.models.connection import Connection
from backend.app.models.data_quality import DataQualityResult, DataProfileResult, ReconciliationResult
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.engine import DataQualityEngine

router = APIRouter(prefix="/data-quality", tags=["data-quality"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _load_polars_df(db: Session, connection_id: Optional[str], table_name: Optional[str], file_path: Optional[str]) -> pl.DataFrame:
    if file_path:
        norm_path = os.path.abspath(file_path)
        if not os.path.exists(norm_path):
            raise HTTPException(status_code=404, detail=f"Dataset file '{norm_path}' not found")
        if norm_path.endswith(".parquet"):
            return pl.read_parquet(norm_path)
        elif norm_path.endswith(".json"):
            return pl.read_json(norm_path)
        else:
            return pl.read_csv(norm_path)

    if connection_id and table_name:
        conn_record = db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise HTTPException(status_code=404, detail=f"Connection ID '{connection_id}' not found")
        decrypted = decrypt_secret(conn_record.config_encrypted)
        connector = get_connector(conn_record.connector_type, decrypted)
        stream = connector.read_data_stream(table_name=table_name, batch_size=10000)
        rows = []
        for chunk in stream:
            rows.extend(chunk)
        if rows:
            return pl.DataFrame(rows)
        return pl.DataFrame()

    raise HTTPException(status_code=400, detail="Must provide file_path or connection_id + table_name")


class ValidateRequest(BaseModel):
    connection_id: Optional[str] = None
    table_name: Optional[str] = None
    file_path: Optional[str] = None
    rules: Optional[List[Dict[str, Any]]] = None
    rulebook: Optional[Dict[str, Any]] = None
    rulebook_file_path: Optional[str] = None
    min_score_threshold: float = 100.0
    reference_connection_id: Optional[str] = None
    reference_table_name: Optional[str] = None
    reference_file_path: Optional[str] = None


class ProfileRequest(BaseModel):
    connection_id: Optional[str] = None
    table_name: Optional[str] = None
    file_path: Optional[str] = None


class ReconcileRequest(BaseModel):
    source_connection_id: Optional[str] = None
    source_table_name: Optional[str] = None
    source_file_path: Optional[str] = None
    target_connection_id: Optional[str] = None
    target_table_name: Optional[str] = None
    target_file_path: Optional[str] = None
    key_columns: Optional[List[str]] = None
    numeric_sum_columns: Optional[List[str]] = None


class MaskRequest(BaseModel):
    connection_id: Optional[str] = None
    table_name: Optional[str] = None
    file_path: Optional[str] = None
    destination_file_path: Optional[str] = None
    masking_rules: List[Dict[str, Any]]


@router.get("/rules-catalog")
def get_rules_catalog():
    """
    Returns available Data Quality rule types, descriptions, and configuration schemas.
    """
    return [
        {
            "rule_type": "MandatoryFieldCheck",
            "name": "Mandatory Field Check",
            "description": "Verifies that designated columns are present in the dataset schema.",
            "parameters": [{"name": "columns", "type": "array", "required": True}]
        },
        {
            "rule_type": "NonBlankCheck",
            "name": "Non-Blank Check",
            "description": "Ensures that string columns contain non-empty, non-whitespace values.",
            "parameters": [{"name": "column", "type": "string", "required": True}]
        },
        {
            "rule_type": "NullValidation",
            "name": "Null Validation",
            "description": "Validates null percentage and count limits on designated column.",
            "parameters": [{"name": "column", "type": "string", "required": True}]
        },
        {
            "rule_type": "DuplicateCheck",
            "name": "Duplicate Check",
            "description": "Detects duplicate rows across specified composite or all columns.",
            "parameters": [{"name": "columns", "type": "array", "required": False}]
        },
        {
            "rule_type": "PrimaryKeyUniqueness",
            "name": "Primary Key Uniqueness",
            "description": "Asserts zero duplicates and zero nulls on primary key columns.",
            "parameters": [{"name": "columns", "type": "array", "required": True}]
        },
        {
            "rule_type": "ReferentialIntegrity",
            "name": "Referential Integrity",
            "description": "Validates foreign keys against parent table primary keys to eliminate orphan records.",
            "parameters": [
                {"name": "column", "type": "string", "required": True},
                {"name": "reference_column", "type": "string", "required": True}
            ]
        },
        {
            "rule_type": "RangeValidation",
            "name": "Range Validation",
            "description": "Asserts that numeric values fall within [min_value, max_value] bounds.",
            "parameters": [
                {"name": "column", "type": "string", "required": True},
                {"name": "min_value", "type": "number", "required": False},
                {"name": "max_value", "type": "number", "required": False}
            ]
        },
        {
            "rule_type": "DateValidation",
            "name": "Date Validation",
            "description": "Validates calendar date formatting and future/past date constraints.",
            "parameters": [
                {"name": "column", "type": "string", "required": True},
                {"name": "date_format", "type": "string", "default": "%Y-%m-%d"},
                {"name": "not_in_future", "type": "boolean", "default": False},
                {"name": "not_in_past", "type": "boolean", "default": False}
            ]
        },
        {
            "rule_type": "ControlledListValidation",
            "name": "Controlled List Validation",
            "description": "Asserts that column values belong to a predefined allowed list (enum).",
            "parameters": [
                {"name": "column", "type": "string", "required": True},
                {"name": "allowed_values", "type": "array", "required": True}
            ]
        },
        {
            "rule_type": "SchemaValidation",
            "name": "Schema Validation",
            "description": "Validates that columns conform strictly to expected data types and names.",
            "parameters": [{"name": "expected_schema", "type": "object", "required": True}]
        },
        {
            "rule_type": "SchemaDriftDetection",
            "name": "Schema Drift Detection",
            "description": "Detects structural drift (unexpected new columns or missing columns).",
            "parameters": [
                {"name": "baseline_columns", "type": "array", "required": True},
                {"name": "allow_drift", "type": "boolean", "default": False}
            ]
        },
        {
            "rule_type": "RowCountValidation",
            "name": "Row Count Validation",
            "description": "Asserts dataset total row count within specified boundaries.",
            "parameters": [
                {"name": "min_rows", "type": "int", "default": 1},
                {"name": "max_rows", "type": "int", "required": False}
            ]
        },
        {
            "rule_type": "PIIDetection",
            "name": "PII Detection",
            "description": "Identifies sensitive PII (Emails, Phones, SSNs, Credit Cards, IPs).",
            "parameters": [
                {"name": "column", "type": "string", "required": True},
                {"name": "pii_types", "type": "array", "default": ["email", "phone", "ssn", "credit_card"]}
            ]
        },
        {
            "rule_type": "CustomSqlCheck",
            "name": "Custom SQL Business Rule",
            "description": "Executes custom business SQL query, condition, or WHERE clause against the dataset to validate complex domain relationships.",
            "parameters": [
                {"name": "sql_condition", "type": "string", "required": False, "description": "Boolean expression valid rows must satisfy (e.g. 'discount <= total_amount')."},
                {"name": "sql_query", "type": "string", "required": False, "description": "Full SQL query returning violating records (e.g. 'SELECT * FROM dataset WHERE discount > total_amount')."},
                {"name": "where_clause", "type": "string", "required": False, "description": "WHERE clause filter matching violating records (e.g. 'discount > total_amount')."},
                {"name": "table_name", "type": "string", "required": False, "default": "dataset", "description": "Table alias for the dataset in SQLContext."}
            ]
        }
    ]


@router.post("/validate")
def validate_dataset(payload: ValidateRequest, db: Session = Depends(get_db)):
    """
    Executes Data Quality validation rules or an integrated rulebook on-demand against a dataset.
    """
    df = _load_polars_df(db, payload.connection_id, payload.table_name, payload.file_path)

    ref_df = None
    if payload.reference_file_path or (payload.reference_connection_id and payload.reference_table_name):
        try:
            ref_df = _load_polars_df(
                db,
                payload.reference_connection_id,
                payload.reference_table_name,
                payload.reference_file_path
            )
        except Exception:
            pass

    if payload.rulebook_file_path or payload.rulebook:
        target_rulebook = payload.rulebook or payload.rulebook_file_path
        return DataQualityEngine.evaluate_rulebook(
            df=df,
            rulebook=target_rulebook,
            ref_df=ref_df
        )

    return DataQualityEngine.evaluate_rules(
        df=df,
        rules=payload.rules or [],
        min_score_threshold=payload.min_score_threshold,
        ref_df=ref_df
    )


@router.post("/profile")
def profile_dataset(payload: ProfileRequest, db: Session = Depends(get_db)):
    """
    Computes statistical and schema profile on-demand.
    """
    df = _load_polars_df(db, payload.connection_id, payload.table_name, payload.file_path)
    return DataQualityEngine.profile_dataset(df)


@router.post("/reconcile")
def reconcile_datasets(payload: ReconcileRequest, db: Session = Depends(get_db)):
    """
    Executes source-to-target reconciliation on-demand.
    """
    s_df = _load_polars_df(db, payload.source_connection_id, payload.source_table_name, payload.source_file_path)
    t_df = _load_polars_df(db, payload.target_connection_id, payload.target_table_name, payload.target_file_path)

    return DataQualityEngine.reconcile(
        source_df=s_df,
        target_df=t_df,
        key_columns=payload.key_columns,
        numeric_sum_columns=payload.numeric_sum_columns
    )


@router.post("/mask")
def mask_dataset(payload: MaskRequest, db: Session = Depends(get_db)):
    """
    Applies data masking to sensitive columns and optionally persists to destination file.
    """
    df = _load_polars_df(db, payload.connection_id, payload.table_name, payload.file_path)
    masked_df = DataQualityEngine.apply_masking(df, payload.masking_rules)

    if payload.destination_file_path:
        norm_dest = os.path.abspath(payload.destination_file_path)
        os.makedirs(os.path.dirname(norm_dest), exist_ok=True)
        if norm_dest.endswith(".parquet"):
            masked_df.write_parquet(norm_dest)
        elif norm_dest.endswith(".json"):
            masked_df.write_json(norm_dest)
        else:
            masked_df.write_csv(norm_dest)

    return {
        "total_records": len(masked_df),
        "destination_file_path": payload.destination_file_path,
        "sample_masked": masked_df.head(10).to_dicts()
    }


@router.get("/history/{pipeline_run_id}")
def get_run_dq_history(pipeline_run_id: str, db: Session = Depends(get_db)):
    """
    Retrieves historical DQ rule evaluations, profile reports, and reconciliation results for a run.
    """
    rule_results = db.query(DataQualityResult).filter(DataQualityResult.pipeline_run_id == pipeline_run_id).all()
    profiles = db.query(DataProfileResult).filter(DataProfileResult.pipeline_run_id == pipeline_run_id).all()
    reconciliations = db.query(ReconciliationResult).filter(ReconciliationResult.pipeline_run_id == pipeline_run_id).all()

    return {
        "pipeline_run_id": pipeline_run_id,
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "rule_type": r.rule_type,
                "status": r.status,
                "total_records": r.total_records_evaluated,
                "failed_records": r.failed_records_count,
                "pass_percentage": r.pass_percentage,
                "sample_failed": r.sample_failed_records,
                "executed_at": r.executed_at.isoformat()
            }
            for r in rule_results
        ],
        "profiles": [
            {
                "dataset_name": p.dataset_name,
                "total_rows": p.total_rows,
                "total_columns": p.total_columns,
                "columns": p.column_profiles,
                "profiled_at": p.profiled_at.isoformat()
            }
            for p in profiles
        ],
        "reconciliations": [
            {
                "source_dataset": r.source_dataset,
                "target_dataset": r.target_dataset,
                "source_rows": r.source_rows,
                "target_rows": r.target_rows,
                "row_variance": r.row_variance,
                "status": r.status,
                "details": r.details,
                "reconciled_at": r.reconciled_at.isoformat()
            }
            for r in reconciliations
        ]
    }
