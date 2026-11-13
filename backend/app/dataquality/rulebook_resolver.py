import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Callable
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class RulebookResolver:
    """
    Enterprise Data Quality Rulebook Resolver.
    Resolves data quality rules and thresholds dynamically from:
      1. Local PC / Filesystem (JSON, YAML)
      2. Cloud Object Storage (AWS S3, Azure ADLS Gen2, Azure Blob, Google Cloud Storage)
      3. Cloud Data Warehouses & Relational Tables (Snowflake, BigQuery, Redshift, PostgreSQL, etc.)
      4. Direct Cloud URIs (s3://, abfss://, gs://)
      5. Inline rules configurations (fallback/hybrid)
    """

    @classmethod
    def resolve_rules(
        cls,
        config: Dict[str, Any],
        db: Optional[Session] = None,
        logger_fn: Optional[Callable[[str, str], None]] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Main entry point for rulebook resolution.
        Returns a tuple of (rules_list, min_score_threshold).
        """
        def log(level: str, msg: str):
            if logger_fn:
                logger_fn(level, msg)

        # Baseline defaults
        rules: List[Dict[str, Any]] = list(config.get("rules", []))
        min_score: float = float(config.get("min_score_threshold", 100.0))

        rulebook_source = (config.get("rulebook_source") or "").lower().strip()
        rulebook_conn_id = config.get("rulebook_connection_id")
        rulebook_path = config.get("rulebook_path") or config.get("rulebook_file_path") or config.get("rulebook_uri")
        rulebook_table = config.get("rulebook_table_name") or config.get("rulebook_table")
        rulebook_query = config.get("rulebook_query") or config.get("rulebook_sql")

        # -------------------------------------------------------------
        # 1. Check for Cloud Storage or Database Table via Connection ID
        # -------------------------------------------------------------
        if rulebook_conn_id and db:
            conn_record = db.query(Connection).filter(Connection.id == rulebook_conn_id).first()
            if not conn_record:
                log("WARNING", f"Rulebook connection ID '{rulebook_conn_id}' not found in registry")
            else:
                ctype = conn_record.connector_type.lower()
                is_storage = ctype in ("aws_s3", "s3", "azure_adls", "adls", "adls_gen2", "azure_blob", "blob", "gcp_storage", "gcs", "local_storage")
                is_database = ctype in ("snowflake", "sf", "bigquery", "bq", "redshift", "postgres", "postgresql", "mysql", "sqlite", "duckdb")

                if rulebook_source == "database_table" or is_database or rulebook_table or rulebook_query:
                    # Resolve from Database / Warehouse Table (e.g. Snowflake)
                    resolved_rules, resolved_score = cls._resolve_database_table(
                        conn_record=conn_record,
                        table_name=rulebook_table,
                        query=rulebook_query,
                        log=log
                    )
                    if resolved_rules:
                        rules = resolved_rules
                        if resolved_score is not None:
                            min_score = resolved_score
                        return rules, min_score

                elif rulebook_source == "cloud_storage" or is_storage:
                    # Resolve from Cloud Storage file (S3, ADLS, GCS)
                    container = config.get("rulebook_container") or config.get("rulebook_bucket")
                    file_key = config.get("rulebook_file_key") or rulebook_path
                    if not container and file_key and ("://" in file_key or "/" in file_key):
                        # Extract container & key from path or URI
                        uri_provider, uri_cont, uri_key = cls._parse_cloud_uri(file_key)
                        if uri_cont:
                            container = uri_cont
                            file_key = uri_key

                    resolved_rules, resolved_score = cls._resolve_cloud_storage(
                        conn_record=conn_record,
                        container=container,
                        object_key=file_key,
                        log=log
                    )
                    if resolved_rules:
                        rules = resolved_rules
                        if resolved_score is not None:
                            min_score = resolved_score
                        return rules, min_score

        # -------------------------------------------------------------
        # 2. Check for Cloud URI (s3://, abfss://, gs://) without explicit conn
        # -------------------------------------------------------------
        if rulebook_path and (rulebook_path.startswith("s3://") or rulebook_path.startswith("abfss://") or rulebook_path.startswith("gs://") or rulebook_path.startswith("wasbs://")):
            provider_type, container, object_key = cls._parse_cloud_uri(rulebook_path)
            if provider_type and container and object_key and db:
                # Find matching connection
                conn_record = db.query(Connection).filter(Connection.connector_type.ilike(f"%{provider_type}%")).first()
                if conn_record:
                    resolved_rules, resolved_score = cls._resolve_cloud_storage(
                        conn_record=conn_record,
                        container=container,
                        object_key=object_key,
                        log=log
                    )
                    if resolved_rules:
                        rules = resolved_rules
                        if resolved_score is not None:
                            min_score = resolved_score
                        return rules, min_score
                else:
                    log("WARNING", f"No active connection found for cloud URI scheme '{provider_type}' ({rulebook_path})")

        # -------------------------------------------------------------
        # 3. System PC / Local Filesystem Path
        # -------------------------------------------------------------
        if rulebook_path and not ("://" in rulebook_path):
            norm_rb = os.path.abspath(rulebook_path)
            if os.path.exists(norm_rb):
                resolved_rules, resolved_score = cls._resolve_local_file(norm_rb, log=log)
                if resolved_rules:
                    rules = resolved_rules
                    if resolved_score is not None:
                        min_score = resolved_score
                    return rules, min_score
            else:
                log("WARNING", f"Rulebook file '{norm_rb}' was specified but not found on local disk")

        return rules, min_score

    # ------------------------------------------------------------------
    # Resolvers for Specific Storage Mediums
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_local_file(
        cls,
        file_path: str,
        log: Callable[[str, str], None]
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """Reads and parses a rulebook from the local filesystem."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            log("INFO", f"Loaded rulebook from local system PC: '{file_path}'")
            return cls._parse_rulebook_content(content, filename=file_path)
        except Exception as e:
            log("ERROR", f"Failed reading local rulebook '{file_path}': {str(e)}")
            return [], None

    @classmethod
    def _resolve_cloud_storage(
        cls,
        conn_record: Connection,
        container: Optional[str],
        object_key: Optional[str],
        log: Callable[[str, str], None]
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """Fetches and parses a rulebook from S3, ADLS Gen2, GCS, or Azure Blob."""
        if not object_key:
            log("WARNING", f"Cloud storage rulebook specified via connection '{conn_record.name}' but object_key is missing")
            return [], None

        clean_container = container or ""
        clean_key = object_key.lstrip("/")

        try:
            decrypted = decrypt_secret(conn_record.config_encrypted)
            # Default container/bucket from connection config if omitted
            if not clean_container:
                clean_container = decrypted.get("bucket") or decrypted.get("bucket_name") or decrypted.get("container") or decrypted.get("container_name") or ""

            connector = get_connector(conn_record.connector_type, decrypted)
            raw_bytes = connector.read_file(clean_container, clean_key)
            content = raw_bytes.decode("utf-8")
            log("INFO", f"Loaded rulebook from cloud storage ({conn_record.connector_type}): '{clean_container}/{clean_key}'")
            return cls._parse_rulebook_content(content, filename=clean_key)
        except Exception as e:
            log("ERROR", f"Failed reading cloud storage rulebook '{clean_container}/{clean_key}': {str(e)}")
            return [], None

    @classmethod
    def _resolve_database_table(
        cls,
        conn_record: Connection,
        table_name: Optional[str],
        query: Optional[str],
        log: Callable[[str, str], None]
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """Queries a database/warehouse table (e.g. Snowflake) and translates rows to rules."""
        try:
            decrypted = decrypt_secret(conn_record.config_encrypted)
            connector = get_connector(conn_record.connector_type, decrypted)

            rows: List[Dict[str, Any]] = []
            if query:
                log("INFO", f"Querying database rulebook catalog via SQL: '{query}'")
                if hasattr(connector, "execute_query"):
                    rows = connector.execute_query(query)
                elif hasattr(connector, "_execute_sql"):
                    rows = connector._execute_sql(query)
            elif table_name:
                log("INFO", f"Fetching database rulebook table: '{table_name}' on connection '{conn_record.name}'")
                stream = connector.read_data_stream(table_name=table_name, batch_size=1000)
                for chunk in stream:
                    rows.extend(chunk)
            else:
                log("WARNING", "Neither rulebook_table_name nor rulebook_query provided for database rulebook resolution")
                return [], None

            return cls._parse_table_rows_to_rules(rows, log=log)
        except Exception as e:
            log("ERROR", f"Failed fetching database rulebook from connection '{conn_record.name}': {str(e)}")
            return [], None

    # ------------------------------------------------------------------
    # Parsers & Translators
    # ------------------------------------------------------------------

    @classmethod
    def _parse_rulebook_content(
        cls,
        content: str,
        filename: str = ""
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """Parses raw text content as JSON or YAML."""
        trimmed = content.strip()
        data: Any = None

        if trimmed.startswith("{") or trimmed.startswith("["):
            try:
                data = json.loads(trimmed)
            except Exception:
                pass

        if data is None:
            try:
                import yaml
                data = yaml.safe_load(trimmed)
            except Exception as ye:
                if filename.endswith(".json"):
                    data = json.loads(trimmed)
                else:
                    raise ValueError(f"Could not parse rulebook as YAML or JSON: {str(ye)}")

        if isinstance(data, list):
            return data, None
        elif isinstance(data, dict):
            rules = data.get("rules", [])
            score = float(data["min_score_threshold"]) if "min_score_threshold" in data else None
            return rules, score
        return [], None

    @classmethod
    def _parse_table_rows_to_rules(
        cls,
        rows: List[Dict[str, Any]],
        log: Callable[[str, str], None]
    ) -> Tuple[List[Dict[str, Any]], Optional[float]]:
        """
        Translates database rows (e.g. from a Snowflake table) into DataQualityEngine rules.
        Supports:
          Case A: Document-in-table (column like rulebook_content, rules_json, config)
          Case B: Row-per-rule catalog (columns: rule_name, rule_type, column_name, sql_condition, etc.)
        """
        if not rows:
            return [], None

        first_row_normalized = {k.lower(): v for k, v in rows[0].items()}

        # -------------------------------------------------------------
        # Case A: Document-in-table schema
        # -------------------------------------------------------------
        doc_cols = ("rulebook_content", "rules_json", "rules_yaml", "rulebook_json", "rules_config", "rule_spec")
        for col in doc_cols:
            if col in first_row_normalized and first_row_normalized[col]:
                val = first_row_normalized[col]
                if isinstance(val, (dict, list)):
                    if isinstance(val, list):
                        return val, None
                    return val.get("rules", []), float(val.get("min_score_threshold", 100.0))
                elif isinstance(val, str):
                    return cls._parse_rulebook_content(val)

        # -------------------------------------------------------------
        # Case B: Row-per-rule catalog schema
        # -------------------------------------------------------------
        rules: List[Dict[str, Any]] = []
        min_score: Optional[float] = None

        for idx, r in enumerate(rows):
            # Normalize keys to lowercase for case-insensitive access (Snowflake is uppercase)
            row = {k.lower(): v for k, v in r.items()}

            # Check if rule is active
            if "is_active" in row and row["is_active"] in (False, 0, "false", "f", "no", "0"):
                continue
            if "enabled" in row and row["enabled"] in (False, 0, "false", "f", "no", "0"):
                continue

            rule_name = str(row.get("rule_name") or row.get("name") or f"Rule_{idx + 1}").strip()
            rule_type = str(row.get("rule_type") or row.get("type") or "CustomSqlCheck").strip()

            rule: Dict[str, Any] = {
                "rule_name": rule_name,
                "rule_type": rule_type
            }

            # Map Columns / Column Name
            raw_cols = row.get("columns") or row.get("column_name") or row.get("column")
            if raw_cols:
                if isinstance(raw_cols, list):
                    rule["columns"] = raw_cols
                elif isinstance(raw_cols, str):
                    clean_str = raw_cols.strip()
                    if clean_str.startswith("[") and clean_str.endswith("]"):
                        try:
                            rule["columns"] = json.loads(clean_str)
                        except Exception:
                            rule["columns"] = [c.strip() for c in clean_str.strip("[]").split(",") if c.strip()]
                    elif "," in clean_str:
                        rule["columns"] = [c.strip() for c in clean_str.split(",") if c.strip()]
                    else:
                        rule["columns"] = [clean_str]
                        rule["column"] = clean_str

            # Map SQL Condition / Expression
            cond = row.get("sql_condition") or row.get("condition") or row.get("expression")
            if cond:
                rule["sql_condition"] = str(cond).strip()

            # Map Range limits
            if row.get("min_value") is not None and str(row.get("min_value")).strip() != "":
                rule["min_value"] = float(row["min_value"])
            if row.get("max_value") is not None and str(row.get("max_value")).strip() != "":
                rule["max_value"] = float(row["max_value"])

            # Map Controlled / Allowed values list
            raw_allowed = row.get("allowed_values") or row.get("values_list") or row.get("controlled_list")
            if raw_allowed:
                if isinstance(raw_allowed, list):
                    rule["allowed_values"] = raw_allowed
                elif isinstance(raw_allowed, str):
                    clean_val = raw_allowed.strip()
                    if clean_val.startswith("[") and clean_val.endswith("]"):
                        try:
                            rule["allowed_values"] = json.loads(clean_val)
                        except Exception:
                            rule["allowed_values"] = [v.strip() for v in clean_val.strip("[]").split(",") if v.strip()]
                    else:
                        rule["allowed_values"] = [v.strip() for v in clean_val.split(",") if v.strip()]

            # Map Pattern / Regex
            if row.get("pattern") or row.get("regex"):
                rule["pattern"] = str(row.get("pattern") or row.get("regex"))

            # Map Date Format
            if row.get("date_format"):
                rule["date_format"] = str(row["date_format"])

            # Map Referential Integrity fields
            if row.get("reference_table") or row.get("ref_table"):
                rule["reference_table"] = str(row.get("reference_table") or row.get("ref_table"))
            if row.get("reference_column") or row.get("ref_column"):
                rule["reference_column"] = str(row.get("reference_column") or row.get("ref_column"))

            # Map Threshold & Severity
            if row.get("threshold_percent") is not None and str(row.get("threshold_percent")).strip() != "":
                rule["threshold_percent"] = float(row["threshold_percent"])
            if row.get("severity"):
                rule["severity"] = str(row["severity"])

            # Check for global min_score_threshold override if provided on row
            if row.get("min_score_threshold") is not None and str(row.get("min_score_threshold")).strip() != "":
                min_score = float(row["min_score_threshold"])

            rules.append(rule)

        log("INFO", f"Translated {len(rules)} data quality rules from database table")
        return rules, min_score

    @classmethod
    def _parse_cloud_uri(cls, uri: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parses a cloud URI into (provider_type, container/bucket, object_key).
        Examples:
          s3://my-bucket/path/rules.yaml -> ("aws_s3", "my-bucket", "path/rules.yaml")
          gs://my-bucket/path/rules.json -> ("gcp_storage", "my-bucket", "path/rules.json")
          abfss://container@acct.dfs.core.windows.net/path/rules.yaml -> ("azure_adls", "container", "path/rules.yaml")
          wasbs://container@acct.blob.core.windows.net/path/rules.yaml -> ("azure_blob", "container", "path/rules.yaml")
        """
        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()

        if scheme in ("s3", "s3a"):
            return "aws_s3", parsed.netloc, parsed.path.lstrip("/")
        elif scheme in ("gs", "gcs"):
            return "gcp_storage", parsed.netloc, parsed.path.lstrip("/")
        elif scheme in ("abfs", "abfss"):
            # abfss://container@account.dfs.core.windows.net/path
            container = parsed.username or parsed.netloc.split("@")[0]
            return "azure_adls", container, parsed.path.lstrip("/")
        elif scheme in ("wasb", "wasbs"):
            container = parsed.username or parsed.netloc.split("@")[0]
            return "azure_blob", container, parsed.path.lstrip("/")

        return None, None, None
