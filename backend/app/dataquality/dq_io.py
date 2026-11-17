"""
dq_io.py — High-Performance Dataset and Rulebook I/O Resolver for Data Quality Activities.

Handles:
    - Resolving ADF-style Dataset references (referenceName / dataset_id / inline)
    - Streaming reading of Parquet, CSV, JSON, and Database connectors into Polars
    - Vectorized writing to Sinks (Single-Sink and Dual-Sink routing)
    - Write strategies: 'insert' (append), 'full' (overwrite), 'merge' (upsert on keys)
    - Rule Catalogue & Cleansing Map resolution from DB, cloud storage, or local files
"""
from __future__ import annotations

import io
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
import polars as pl

from backend.app.models.dataset import Dataset
from backend.app.models.connection import Connection
from backend.app.models.data_quality import DQRuleCatalogue
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.rulebook_resolver import RulebookResolver

logger = logging.getLogger("dataforge.dataquality.io")


def resolve_dataset_config(
    dataset_ref: Any,
    db: Optional[Session] = None,
    default_cfg: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolves dataset location and format settings from ADF-style reference or dict.
    Example dataset_ref:
        {"referenceName": "Bronze_Customers"} or "Bronze_Customers" or {"file_path": "/tmp/customers.csv"}
    """
    resolved: Dict[str, Any] = dict(default_cfg or {})

    if isinstance(dataset_ref, dict):
        ref_name = dataset_ref.get("referenceName") or dataset_ref.get("name") or dataset_ref.get("dataset_id") or dataset_ref.get("id")
        resolved.update(dataset_ref)
    else:
        ref_name = str(dataset_ref) if dataset_ref else None

    if ref_name and db:
        ds = db.query(Dataset).filter((Dataset.name == ref_name) | (Dataset.id == ref_name)).first()
        if ds:
            loc = ds.location_config or {}
            resolved["dataset_id"] = ds.id
            resolved["dataset_name"] = ds.name
            resolved["connection_id"] = ds.connection_id
            resolved["table_name"] = loc.get("table") or loc.get("table_name")
            resolved["schema_name"] = loc.get("schema") or loc.get("schema_name")
            resolved["query"] = loc.get("query")
            resolved["container"] = loc.get("container") or loc.get("bucket")
            resolved["bucket"] = loc.get("bucket") or loc.get("container")
            resolved["file_path"] = loc.get("path") or loc.get("file_name") or loc.get("file_path")
            resolved["format"] = (ds.format_settings or {}).get("format") or loc.get("format") or "csv"
            resolved.update(ds.format_settings or {})

    return resolved


def load_dataset_as_polars(
    cfg: Dict[str, Any],
    db: Optional[Session] = None
) -> pl.DataFrame:
    """
    Loads dataset from resolved config (in-memory, local file, ADLS/S3 cloud storage, or database connector) into Polars.
    """
    # 1. In-memory DataFrame or records passed directly
    if "dataframe" in cfg and isinstance(cfg["dataframe"], pl.DataFrame):
        return cfg["dataframe"]
    if "records" in cfg and isinstance(cfg["records"], list):
        return pl.DataFrame(cfg["records"])
    if "data" in cfg and isinstance(cfg["data"], list):
        return pl.DataFrame(cfg["data"])

    file_path = cfg.get("file_path") or cfg.get("path")
    connection_id = cfg.get("connection_id")
    table_name = cfg.get("table_name") or cfg.get("table")
    container = cfg.get("container") or cfg.get("filesystem") or cfg.get("bucket")

    # 2. Cloud Storage or Database Connector via Connection ID
    if connection_id and db:
        conn_record = db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection ID '{connection_id}' not found")

        decrypted = decrypt_secret(conn_record.config_encrypted)
        ctype = conn_record.connector_type.lower()
        is_cloud_storage = ctype in (
            "azure_adls", "adls", "adls_gen2", "azure_blob", "blob",
            "aws_s3", "s3", "gcp_storage", "gcs"
        )

        if is_cloud_storage:
            connector = get_connector(conn_record.connector_type, decrypted)
            target_container = container or decrypted.get("filesystem") or decrypted.get("container_name") or decrypted.get("bucket") or ""
            target_key = file_path or table_name or ""
            if "://" in target_key:
                _, uri_cont, uri_key = RulebookResolver._parse_cloud_uri(target_key)
                if uri_cont:
                    target_container = uri_cont
                if uri_key:
                    target_key = uri_key
            target_key = target_key.lstrip("/")

            raw_bytes = connector.read_file(target_container, target_key)
            byte_stream = io.BytesIO(raw_bytes)
            fmt = (cfg.get("format") or "").lower()
            if target_key.endswith(".parquet") or fmt == "parquet":
                return pl.read_parquet(byte_stream)
            elif target_key.endswith(".json") or fmt == "json":
                return pl.read_json(byte_stream)
            elif target_key.endswith(".avro") or fmt == "avro":
                return pl.read_avro(byte_stream)
            else:
                return pl.read_csv(byte_stream)

        elif table_name:
            connector = get_connector(conn_record.connector_type, decrypted)
            stream = connector.read_data_stream(table_name=table_name, batch_size=10000)
            rows: List[Dict[str, Any]] = []
            for chunk in stream:
                rows.extend(chunk)
            return pl.DataFrame(rows) if rows else pl.DataFrame()

    # 3. Direct Cloud URI (abfss://, s3://, gs://) without explicit connection_id
    if file_path and (file_path.startswith("abfss://") or file_path.startswith("wasbs://") or file_path.startswith("s3://") or file_path.startswith("gs://")):
        provider, uri_cont, uri_key = RulebookResolver._parse_cloud_uri(file_path)
        if provider and uri_cont and uri_key and db:
            conn_record = db.query(Connection).filter(Connection.connector_type.ilike(f"%{provider}%")).first()
            if conn_record:
                decrypted = decrypt_secret(conn_record.config_encrypted)
                connector = get_connector(conn_record.connector_type, decrypted)
                raw_bytes = connector.read_file(uri_cont, uri_key)
                byte_stream = io.BytesIO(raw_bytes)
                fmt = (cfg.get("format") or "").lower()
                if uri_key.endswith(".parquet") or fmt == "parquet":
                    return pl.read_parquet(byte_stream)
                elif uri_key.endswith(".json") or fmt == "json":
                    return pl.read_json(byte_stream)
                elif uri_key.endswith(".avro") or fmt == "avro":
                    return pl.read_avro(byte_stream)
                else:
                    return pl.read_csv(byte_stream)

    # 4. Local File storage (local or mounted volume)
    if file_path and not ("://" in file_path):
        norm_path = os.path.abspath(file_path)
        if not os.path.exists(norm_path):
            raise FileNotFoundError(f"Source dataset file '{norm_path}' not found")

        fmt = (cfg.get("format") or "").lower()
        if norm_path.endswith(".parquet") or fmt == "parquet":
            return pl.read_parquet(norm_path)
        elif norm_path.endswith(".json") or fmt == "json":
            return pl.read_json(norm_path)
        elif norm_path.endswith(".avro") or fmt == "avro":
            return pl.read_avro(norm_path)
        else:
            return pl.read_csv(norm_path)

    return pl.DataFrame()


def write_polars_dataset(
    df: pl.DataFrame,
    cfg: Dict[str, Any],
    write_strategy: str = "merge",
    pk_columns: Optional[List[str]] = None,
    db: Optional[Session] = None
) -> int:
    """
    Persists Polars DataFrame using configured write strategy:
      - 'insert': appends rows
      - 'full': overwrites target
      - 'merge': upserts on primary/business keys
    Returns rows written count.
    """
    if df.is_empty():
        return 0

    pk_cols = pk_columns or []
    strat = write_strategy.lower()
    file_path = cfg.get("file_path") or cfg.get("path")
    connection_id = cfg.get("connection_id")
    table_name = cfg.get("table_name") or cfg.get("table")

    # 1. File persistence
    if file_path:
        norm_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(norm_path), exist_ok=True)
        fmt = (cfg.get("format") or "").lower()
        is_parquet = norm_path.endswith(".parquet") or fmt == "parquet"
        is_json = norm_path.endswith(".json") or fmt == "json"

        target_df = df
        if os.path.exists(norm_path) and strat in ("insert", "merge"):
            try:
                if is_parquet:
                    existing = pl.read_parquet(norm_path)
                elif is_json:
                    existing = pl.read_json(norm_path)
                else:
                    existing = pl.read_csv(norm_path)

                # Cast common columns in df to match existing dtypes if needed
                for c in existing.columns:
                    if c in df.columns and existing[c].dtype != df[c].dtype:
                        try:
                            df = df.with_columns(pl.col(c).cast(existing[c].dtype))
                        except Exception:
                            pass

                if strat == "insert":
                    target_df = pl.concat([existing, df], how="diagonal")
                elif strat == "merge" and pk_cols:
                    # Filter existing to exclude keys in new df
                    clean_pks = [k for k in pk_cols if k in existing.columns and k in df.columns]
                    if clean_pks:
                        # Join anti on PK
                        keys_in_new = df.select(clean_pks).unique()
                        retained = existing.join(keys_in_new, on=clean_pks, how="anti")
                        target_df = pl.concat([retained, df], how="diagonal")
                    else:
                        target_df = pl.concat([existing, df], how="diagonal")
            except Exception as e:
                logger.warning(f"Could not merge with existing file {norm_path}: {e}. Overwriting.")
                target_df = df

        if is_parquet:
            target_df.write_parquet(norm_path)
        elif is_json:
            target_df.write_json(norm_path)
        else:
            target_df.write_csv(norm_path)

        return len(df)

    # 2. Cloud Storage Connector (ADLS Gen2 / Blob / S3 / GCS)
    if connection_id and db:
        conn_record = db.query(Connection).filter(Connection.id == connection_id).first()
        if conn_record:
            ctype = conn_record.connector_type.lower()
            if ctype in ("azure_adls", "adls", "adls_gen2", "azure_blob", "blob", "aws_s3", "s3", "gcp_storage", "gcs"):
                decrypted = decrypt_secret(conn_record.config_encrypted)
                connector = get_connector(conn_record.connector_type, decrypted)
                target_container = cfg.get("container") or cfg.get("filesystem") or cfg.get("bucket") or decrypted.get("filesystem") or decrypted.get("container_name") or ""
                target_key = cfg.get("file_path") or cfg.get("path") or cfg.get("table_name") or "dataset.parquet"
                if "://" in target_key:
                    _, uri_cont, uri_key = RulebookResolver._parse_cloud_uri(target_key)
                    if uri_cont:
                        target_container = uri_cont
                    if uri_key:
                        target_key = uri_key
                target_key = target_key.lstrip("/")

                buf = io.BytesIO()
                fmt = (cfg.get("format") or "").lower()
                if target_key.endswith(".json") or fmt == "json":
                    df.write_json(buf)
                elif target_key.endswith(".csv") or fmt == "csv":
                    df.write_csv(buf)
                else:
                    df.write_parquet(buf)

                connector.write_file(target_container, target_key, buf.getvalue())
                return len(df)

    # 3. Database Connector
    if connection_id and table_name and db:
        conn_record = db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection ID '{connection_id}' not found")
        decrypted = decrypt_secret(conn_record.config_encrypted)
        connector = get_connector(conn_record.connector_type, decrypted)

        write_mode = "overwrite" if strat == "full" else ("upsert" if strat == "merge" else "append")
        connector.write_data(
            data=df.to_dicts(),
            table_name=table_name,
            write_mode=write_mode,
            key_columns=pk_cols
        )
        return len(df)

    # In-memory storage into config for pipeline tests
    cfg["output_dataframe"] = df
    return len(df)


def resolve_rule_catalogue(
    rule_ref: Any,
    db: Optional[Session] = None,
    dataset_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Resolves rule catalogue items from:
      1. DB table `dq_rule_catalogue` (DQRuleCatalogue model)
      2. RulebookResolver (cloud storage, snowflake tables, local file)
      3. Direct list of rules
    """
    if isinstance(rule_ref, list):
        return rule_ref

    ref_name = None
    if isinstance(rule_ref, dict):
        ref_name = rule_ref.get("referenceName") or rule_ref.get("name")
        if "rules" in rule_ref and isinstance(rule_ref["rules"], list):
            return rule_ref["rules"]
    elif isinstance(rule_ref, str):
        ref_name = rule_ref

    # 1. Query Database table dq_rule_catalogue
    if db:
        try:
            q = db.query(DQRuleCatalogue).filter(DQRuleCatalogue.is_active == True)
            if ref_name and ref_name not in ("DQ_RULE_CATALOGUE", "DIM_DQ_RULE", "default"):
                q = q.filter(DQRuleCatalogue.dataset_id == ref_name)
            elif dataset_name:
                q = q.filter((DQRuleCatalogue.dataset_id == dataset_name) | (DQRuleCatalogue.dataset_id.is_(None)))

            db_rules = q.all()
            if db_rules:
                return [
                    {
                        "rule_id": r.rule_id,
                        "rule_type": r.rule_type,
                        "target_column": r.target_column,
                        "rule_expression_logic": r.rule_expression_logic,
                        "technical_description": r.technical_description,
                        "severity": r.severity,
                        "key_columns": r.key_columns,
                        "placeholder_values": r.placeholder_values or [],
                        "parameters": r.parameters or {}
                    }
                    for r in db_rules
                ]
        except Exception as e:
            logger.debug(f"Could not query dq_rule_catalogue: {e}")

    # 2. RulebookResolver
    if isinstance(rule_ref, dict):
        try:
            resolved, _ = RulebookResolver.resolve_rules(rule_ref, db=db)
            if resolved:
                return resolved
        except Exception:
            pass

    return []


def resolve_cleansing_map(
    map_ref: Any,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Resolves cleansing steps from file, dict, or referenceName.
    """
    if isinstance(map_ref, list):
        return map_ref

    if isinstance(map_ref, dict):
        if "steps" in map_ref and isinstance(map_ref["steps"], list):
            return map_ref["steps"]
        ref_path = map_ref.get("path") or map_ref.get("file_path")
        if ref_path and os.path.exists(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("steps") or (data if isinstance(data, list) else [])

    if isinstance(map_ref, str) and os.path.exists(map_ref):
        with open(map_ref, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("steps") or (data if isinstance(data, list) else [])

    return []
