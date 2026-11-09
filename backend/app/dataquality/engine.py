import re
import math
import hashlib
import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import polars as pl


class DataQualityEngine:
    """
    Enterprise Vectorized Data Quality & Profiling Engine.
    Executes rules, profiling, reconciliation, PII detection, and masking using Polars.
    """

    # Common PII Regex Patterns
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    PHONE_REGEX = re.compile(r"^\+?1?\s*\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$")
    SSN_REGEX = re.compile(r"^(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}$")
    CREDIT_CARD_REGEX = re.compile(r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})$")
    IPV4_REGEX = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

    # Disallowed DDL/DML patterns to guarantee read-only query safety
    DISALLOWED_SQL_REGEX = re.compile(
        r"\b(DROP|DELETE|ALTER|TRUNCATE|INSERT|UPDATE|GRANT|REVOKE|EXEC|EXECUTE|ATTACH|DETACH)\b",
        re.IGNORECASE
    )

    @classmethod
    def evaluate_rules(
        cls,
        df: pl.DataFrame,
        rules: List[Dict[str, Any]],
        min_score_threshold: float = 100.0,
        ref_df: Optional[pl.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a suite of data quality rules against a Polars DataFrame.
        Returns a comprehensive report with rule scores, failed record samples,
        composite DQ score, and quarantine rows.
        """
        total_rows = len(df)
        rule_results = []
        all_failed_indices = set()
        critical_failed = False

        norm_map = {
            "mandatory": "MandatoryFieldCheck",
            "mandatoryfieldcheck": "MandatoryFieldCheck",
            "nonblank": "NonBlankCheck",
            "nonblankcheck": "NonBlankCheck",
            "null": "NullValidation",
            "nullcheck": "NullValidation",
            "nullvalidation": "NullValidation",
            "duplicate": "DuplicateCheck",
            "duplicatecheck": "DuplicateCheck",
            "primarykey": "PrimaryKeyUniqueness",
            "primarykeyuniqueness": "PrimaryKeyUniqueness",
            "referentialintegrity": "ReferentialIntegrity",
            "range": "RangeValidation",
            "rangevalidation": "RangeValidation",
            "date": "DateValidation",
            "datevalidation": "DateValidation",
            "controlledlist": "ControlledListValidation",
            "controlledlistvalidation": "ControlledListValidation",
            "schemavalidation": "SchemaValidation",
            "schemadrift": "SchemaDriftDetection",
            "schemadriftdetection": "SchemaDriftDetection",
            "rowcount": "RowCountValidation",
            "rowcountvalidation": "RowCountValidation",
            "pii": "PIIDetection",
            "piidetection": "PIIDetection",
            "customsql": "CustomSqlCheck",
            "customsqlcheck": "CustomSqlCheck",
            "sql": "CustomSqlCheck",
            "sqlcheck": "CustomSqlCheck",
            "sqlquery": "CustomSqlCheck",
            "sqlquerycheck": "CustomSqlCheck",
            "customquery": "CustomSqlCheck",
            "customsqlquery": "CustomSqlCheck",
            "sqlcondition": "CustomSqlCheck",
            "customsqlexpression": "CustomSqlCheck"
        }

        for r_idx, rule in enumerate(rules):
            raw_rule_type = rule.get("rule_type", "").strip()
            lookup_key = raw_rule_type.lower().replace("_", "").replace(" ", "")
            rule_type = norm_map.get(lookup_key, raw_rule_type)
            column = rule.get("column")
            severity = rule.get("severity", "Error")  # Error or Warning
            threshold_pct = float(rule.get("threshold_percent", 100.0))
            params = rule.get("parameters", {})

            failed_indices = set()
            error_message = None
            custom_sample_records = None

            # 1. Mandatory Field Check
            if rule_type == "MandatoryFieldCheck":
                req_columns = rule.get("columns", [column] if column else [])
                missing = [c for c in req_columns if c not in df.columns]
                if missing:
                    error_message = f"Missing mandatory columns: {missing}"
                    failed_indices = set(range(total_rows))

            # 2. Non-Blank Check
            elif rule_type == "NonBlankCheck":
                if column in df.columns:
                    col_series = df[column].cast(pl.String, strict=False)
                    for idx, val in enumerate(col_series.to_list()):
                        if val is None or str(val).strip() == "":
                            failed_indices.add(idx)

            # 3. Null Validation
            elif rule_type == "NullValidation":
                if column in df.columns:
                    col_series = df[column]
                    for idx, val in enumerate(col_series.to_list()):
                        if val is None:
                            failed_indices.add(idx)

            # 4. Duplicate Check
            elif rule_type == "DuplicateCheck":
                check_cols = rule.get("columns", [column] if column else df.columns)
                valid_cols = [c for c in check_cols if c in df.columns]
                if valid_cols:
                    dups_mask = df.select(valid_cols).is_duplicated()
                    for idx, is_dup in enumerate(dups_mask.to_list()):
                        if is_dup:
                            failed_indices.add(idx)

            # 5. Primary Key Uniqueness
            elif rule_type == "PrimaryKeyUniqueness":
                pk_cols = rule.get("columns", [column] if column else [])
                valid_pk = [c for c in pk_cols if c in df.columns]
                if valid_pk:
                    # PK cannot have nulls AND cannot have duplicates
                    dups_mask = df.select(valid_pk).is_duplicated()
                    null_mask = df.select([pl.col(c).is_null() for c in valid_pk]).select(pl.any_horizontal("*")).to_series()
                    for idx in range(total_rows):
                        if dups_mask[idx] or null_mask[idx]:
                            failed_indices.add(idx)

            # 6. Referential Integrity
            elif rule_type == "ReferentialIntegrity":
                fk_col = column
                ref_pk_col = rule.get("reference_column", fk_col)
                if fk_col in df.columns and ref_df is not None and ref_pk_col in ref_df.columns:
                    ref_keys = set(ref_df[ref_pk_col].drop_nulls().to_list())
                    fk_vals = df[fk_col].to_list()
                    for idx, val in enumerate(fk_vals):
                        if val is not None and val not in ref_keys:
                            failed_indices.add(idx)
                elif ref_df is None:
                    error_message = "Reference dataset missing for ReferentialIntegrity check"
                    failed_indices = set(range(total_rows))

            # 7. Range Validation
            elif rule_type == "RangeValidation":
                min_val = rule.get("min_value")
                max_val = rule.get("max_value")
                if column in df.columns:
                    col_vals = df[column].to_list()
                    for idx, val in enumerate(col_vals):
                        if val is not None:
                            try:
                                num = float(val)
                                if min_val is not None and num < float(min_val):
                                    failed_indices.add(idx)
                                elif max_val is not None and num > float(max_val):
                                    failed_indices.add(idx)
                            except (ValueError, TypeError):
                                failed_indices.add(idx)

            # 8. Date Validation
            elif rule_type == "DateValidation":
                fmt = rule.get("date_format", "%Y-%m-%d")
                not_future = rule.get("not_in_future", False)
                not_past = rule.get("not_in_past", False)
                now_date = datetime.datetime.now(datetime.timezone.utc).date()

                if column in df.columns:
                    col_vals = df[column].to_list()
                    for idx, val in enumerate(col_vals):
                        if val is not None and str(val).strip() != "":
                            try:
                                dt = datetime.datetime.strptime(str(val).strip()[:10], fmt[:8] if len(fmt) >= 8 else fmt).date()
                                if not_future and dt > now_date:
                                    failed_indices.add(idx)
                                if not_past and dt < now_date:
                                    failed_indices.add(idx)
                            except Exception:
                                failed_indices.add(idx)

            # 9. Controlled List Validation
            elif rule_type == "ControlledListValidation":
                allowed_vals = set(rule.get("allowed_values", []))
                if column in df.columns:
                    col_vals = df[column].to_list()
                    for idx, val in enumerate(col_vals):
                        if val is not None and val not in allowed_vals:
                            failed_indices.add(idx)

            # 10. Schema Validation
            elif rule_type == "SchemaValidation":
                expected_schema = rule.get("expected_schema", {})  # { col: type_name }
                for exp_col, exp_type in expected_schema.items():
                    if exp_col not in df.columns:
                        failed_indices = set(range(total_rows))
                        error_message = f"Schema mismatch: missing column '{exp_col}'"
                        break

            # 11. Schema Drift Detection
            elif rule_type == "SchemaDriftDetection":
                baseline_cols = set(rule.get("baseline_columns", []))
                allow_drift = rule.get("allow_drift", False)
                current_cols = set(df.columns)
                added = current_cols - baseline_cols
                missing = baseline_cols - current_cols
                if (added or missing) and not allow_drift:
                    failed_indices = set(range(total_rows))
                    error_message = f"Schema drift detected: added {list(added)}, missing {list(missing)}"

            # 12. Row Count Validation
            elif rule_type == "RowCountValidation":
                min_rows = rule.get("min_rows", 1)
                max_rows = rule.get("max_rows")
                if total_rows < min_rows or (max_rows is not None and total_rows > max_rows):
                    failed_indices = set(range(total_rows))
                    error_message = f"Row count {total_rows} out of bounds [{min_rows}, {max_rows}]"

            # 13. PII Detection Check
            elif rule_type == "PIIDetection":
                pii_types = rule.get("pii_types", ["email", "phone", "ssn", "credit_card"])
                if column in df.columns:
                    col_vals = df[column].to_list()
                    for idx, val in enumerate(col_vals):
                        if val is not None:
                            val_str = str(val).strip()
                            if ("email" in pii_types and cls.EMAIL_REGEX.match(val_str)) or \
                               ("phone" in pii_types and cls.PHONE_REGEX.match(val_str)) or \
                               ("ssn" in pii_types and cls.SSN_REGEX.match(val_str)) or \
                               ("credit_card" in pii_types and cls.CREDIT_CARD_REGEX.match(val_str)):
                                failed_indices.add(idx)

            # 14. Custom SQL Business Rule Check
            elif rule_type in ("CustomSqlCheck", "SqlQueryCheck", "CustomSqlExpression"):
                sql_query = rule.get("sql_query") or rule.get("query") or params.get("sql_query") or params.get("query")
                sql_condition = rule.get("sql_condition") or rule.get("condition") or params.get("sql_condition") or params.get("condition")
                where_clause = rule.get("where_clause") or params.get("where_clause") or rule.get("filter") or params.get("filter")

                if not (sql_query or sql_condition or where_clause):
                    error_message = "CustomSqlCheck requires 'sql_query', 'sql_condition', or 'where_clause'"
                    failed_indices = set(range(total_rows))
                else:
                    raw_sql = str(sql_query or sql_condition or where_clause)
                    if cls.DISALLOWED_SQL_REGEX.search(raw_sql):
                        error_message = "Disallowed SQL statement detected: only read-only SELECT queries and conditions are permitted in Data Quality rules"
                        failed_indices = set(range(total_rows))
                    else:
                        try:
                            df_idx = df.with_row_index("__df_row_idx__")
                            ctx = pl.SQLContext()
                            target_alias = rule.get("table_name") or params.get("table_name") or "dataset"
                            ctx.register(target_alias, df_idx)
                            ctx.register("dataset", df_idx)
                            ctx.register("df", df_idx)
                            ctx.register("source", df_idx)

                            if ref_df is not None:
                                ref_alias = rule.get("reference_table_name") or params.get("reference_table_name") or "reference"
                                ref_idx = ref_df.with_row_index("__ref_row_idx__")
                                ctx.register(ref_alias, ref_idx)
                                ctx.register("reference", ref_idx)
                                ctx.register("ref_df", ref_idx)
                                ctx.register("ref_dataset", ref_idx)

                            if sql_condition:
                                # Records where condition is NOT true violate the rule
                                cond_query = f"SELECT __df_row_idx__ FROM {target_alias} WHERE NOT ({sql_condition})"
                                q_res = ctx.execute(cond_query).collect()
                                failed_indices = set(q_res["__df_row_idx__"].to_list())
                            elif where_clause:
                                # Records matching where_clause are violating rows
                                wc_query = f"SELECT __df_row_idx__ FROM {target_alias} WHERE {where_clause}"
                                q_res = ctx.execute(wc_query).collect()
                                failed_indices = set(q_res["__df_row_idx__"].to_list())
                            elif sql_query:
                                trimmed_query = sql_query.strip()
                                if not (trimmed_query.upper().startswith("SELECT") or trimmed_query.upper().startswith("WITH")):
                                    error_message = "Custom SQL query must begin with SELECT or WITH"
                                    failed_indices = set(range(total_rows))
                                else:
                                    q_res = ctx.execute(trimmed_query).collect()
                                    if "__df_row_idx__" in q_res.columns:
                                        failed_indices = set(q_res["__df_row_idx__"].to_list())
                                    elif len(q_res) == 1 and len(q_res.columns) == 1:
                                        val = q_res[0, 0]
                                        if isinstance(val, bool):
                                            if not val:
                                                failed_indices = set(range(total_rows))
                                        elif isinstance(val, (int, float)):
                                            val_num = int(val)
                                            if val_num > 0:
                                                failed_indices = set(range(min(val_num, total_rows or 1)))
                                        else:
                                            if not val:
                                                failed_indices = set(range(total_rows))
                                    else:
                                        # Query returned violating rows
                                        num_failing = len(q_res)
                                        if num_failing > 0:
                                            # Match by key if possible
                                            matched_indices = set()
                                            if column and column in q_res.columns and column in df.columns:
                                                failing_keys = set(q_res[column].drop_nulls().to_list())
                                                for idx, row_val in enumerate(df[column].to_list()):
                                                    if row_val in failing_keys:
                                                        matched_indices.add(idx)
                                            if matched_indices:
                                                failed_indices = matched_indices
                                            else:
                                                failed_indices = set(range(min(num_failing, total_rows or 1)))
                                            custom_sample_records = q_res.drop("__df_row_idx__", strict=False).head(10).to_dicts()
                        except Exception as ex:
                            error_message = f"SQL execution error in CustomSqlCheck: {str(ex)}"
                            failed_indices = set(range(total_rows))

            else:
                error_message = f"Unsupported rule type: {rule_type}"

            # Compute metric scores for this rule
            fail_count = len(failed_indices)
            pass_pct = round(((total_rows - fail_count) / max(total_rows, 1)) * 100.0, 2)
            passed = pass_pct >= threshold_pct and not error_message

            if not passed and severity == "Error":
                critical_failed = True

            all_failed_indices.update(failed_indices)

            # Extract sample failed records
            sample_failed_records = []
            if failed_indices:
                if custom_sample_records:
                    sample_failed_records = custom_sample_records
                else:
                    sample_indices = sorted(list(failed_indices))[:10]
                    sample_failed_records = df[sample_indices].to_dicts()

            rule_results.append({
                "rule_name": rule.get("rule_name") or rule.get("name") or f"{rule_type} on {column or rule.get('sql_condition') or 'query'}",
                "rule_type": rule_type,
                "column": column or rule.get("sql_condition") or rule.get("where_clause") or "sql_expression",
                "severity": severity,
                "threshold_percent": threshold_pct,
                "total_records": total_rows,
                "failed_records_count": fail_count,
                "pass_percentage": pass_pct,
                "status": "Passed" if passed else ("Warning" if severity == "Warning" else "Failed"),
                "sample_failed_records": sample_failed_records,
                "error_message": error_message
            })

        # Calculate composite DQ Score
        if rule_results:
            composite_score = round(sum(r["pass_percentage"] for r in rule_results) / len(rule_results), 2)
        else:
            composite_score = 100.0

        overall_status = "Passed"
        if composite_score < min_score_threshold or critical_failed:
            overall_status = "Failed"
        elif any(r["status"] == "Warning" for r in rule_results):
            overall_status = "Warning"

        # Quarantine rows extraction
        quarantine_rows = []
        if all_failed_indices:
            quarantine_rows = df[sorted(list(all_failed_indices))].to_dicts()

        return {
            "total_records": total_rows,
            "rules_evaluated": len(rule_results),
            "rules_passed": sum(1 for r in rule_results if r["status"] == "Passed"),
            "rules_failed": sum(1 for r in rule_results if r["status"] == "Failed"),
            "rules_warning": sum(1 for r in rule_results if r["status"] == "Warning"),
            "composite_dq_score": composite_score,
            "min_score_threshold": min_score_threshold,
            "overall_status": overall_status,
            "rule_results": rule_results,
            "quarantine_count": len(all_failed_indices),
            "quarantine_records": quarantine_rows[:100]  # sample of quarantine
        }

    @classmethod
    def evaluate_rulebook(
        cls,
        df: pl.DataFrame,
        rulebook: Union[Dict[str, Any], str],
        ref_df: Optional[pl.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a manually written Data Quality rulebook (provided as a dictionary,
        JSON/YAML string, or file path to a .json / .yaml / .yml document).
        """
        import os
        import json

        rulebook_data = {}
        if isinstance(rulebook, str):
            trimmed = rulebook.strip()
            if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
                rulebook_data = json.loads(trimmed)
            elif os.path.exists(trimmed):
                norm_path = os.path.abspath(trimmed)
                with open(norm_path, "r", encoding="utf-8") as f:
                    if norm_path.endswith((".yaml", ".yml")):
                        try:
                            import yaml
                            rulebook_data = yaml.safe_load(f)
                        except ImportError:
                            raise RuntimeError("PyYAML is required to parse YAML rulebook files")
                    else:
                        rulebook_data = json.load(f)
            else:
                try:
                    import yaml
                    rulebook_data = yaml.safe_load(trimmed)
                except Exception:
                    raise ValueError(f"Rulebook path or content '{rulebook[:100]}' could not be resolved")
        elif isinstance(rulebook, dict):
            rulebook_data = rulebook
        elif isinstance(rulebook, list):
            rulebook_data = {"rules": rulebook}
        else:
            raise TypeError(f"Expected rulebook to be dict, JSON/YAML string, or file path, got {type(rulebook)}")

        if isinstance(rulebook_data, list):
            rules = rulebook_data
            min_score = 100.0
        else:
            rules = rulebook_data.get("rules", [])
            min_score = float(rulebook_data.get("min_score_threshold", 100.0))

        return cls.evaluate_rules(
            df=df,
            rules=rules,
            min_score_threshold=min_score,
            ref_df=ref_df
        )

    @classmethod
    def profile_dataset(cls, df: pl.DataFrame) -> Dict[str, Any]:
        """
        Generates exhaustive statistical and schema profiling for an entire DataFrame.
        Computes row counts, null counts, null percentages, distinct values,
        min, max, mean, stddev, median, and top values per column.
        """
        total_rows = len(df)
        total_cols = len(df.columns)
        columns_profile = []

        for col_name in df.columns:
            series = df[col_name]
            dtype_str = str(series.dtype)
            null_count = series.null_count()
            null_pct = round((null_count / max(total_rows, 1)) * 100.0, 2)
            distinct_count = series.n_unique()
            uniqueness_pct = round((distinct_count / max(total_rows, 1)) * 100.0, 2)

            col_meta = {
                "column_name": col_name,
                "data_type": dtype_str,
                "total_count": total_rows,
                "null_count": null_count,
                "null_percentage": null_pct,
                "distinct_count": distinct_count,
                "uniqueness_percentage": uniqueness_pct,
                "min": None,
                "max": None,
                "mean": None,
                "stddev": None,
                "median": None,
                "top_frequent_values": []
            }

            # Numeric metrics
            if series.dtype.is_numeric() and total_rows > null_count:
                clean_s = series.drop_nulls()
                if len(clean_s) > 0:
                    col_meta["min"] = clean_s.min()
                    col_meta["max"] = clean_s.max()
                    col_meta["mean"] = round(float(clean_s.mean()), 3) if clean_s.mean() is not None else None
                    col_meta["stddev"] = round(float(clean_s.std()), 3) if clean_s.std() is not None else None
                    col_meta["median"] = clean_s.median()
            elif series.dtype == pl.String and total_rows > null_count:
                clean_s = series.drop_nulls()
                if len(clean_s) > 0:
                    col_meta["min"] = clean_s.min()
                    col_meta["max"] = clean_s.max()

            # Top frequent values
            if total_rows > 0:
                val_counts = series.value_counts(sort=True).head(5).to_dicts()
                col_meta["top_frequent_values"] = [
                    {"value": str(vc[col_name]), "count": vc["count"]} for vc in val_counts
                ]

            columns_profile.append(col_meta)

        return {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "columns": columns_profile,
            "profiled_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    @classmethod
    def reconcile(
        cls,
        source_df: pl.DataFrame,
        target_df: pl.DataFrame,
        key_columns: Optional[List[str]] = None,
        numeric_sum_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes Source-to-Target Data Reconciliation:
        - Row count parity check
        - Key-based record existence and discrepancy detection
        - Column-level numeric sum/average reconciliation
        """
        source_rows = len(source_df)
        target_rows = len(target_df)
        row_variance = target_rows - source_rows
        row_parity = (source_rows == target_rows)

        column_comparisons = []
        if numeric_sum_columns:
            for col in numeric_sum_columns:
                if col in source_df.columns and col in target_df.columns:
                    s_sum = float(source_df[col].drop_nulls().sum() or 0.0)
                    t_sum = float(target_df[col].drop_nulls().sum() or 0.0)
                    variance = round(t_sum - s_sum, 4)
                    match = math.isclose(s_sum, t_sum, rel_tol=1e-5)
                    column_comparisons.append({
                        "column": col,
                        "source_sum": round(s_sum, 4),
                        "target_sum": round(t_sum, 4),
                        "variance": variance,
                        "matched": match
                    })

        # Key-level reconciliation
        missing_in_target = 0
        extra_in_target = 0
        if key_columns:
            valid_keys = [k for k in key_columns if k in source_df.columns and k in target_df.columns]
            if valid_keys:
                s_keys = set(tuple(r) for r in source_df.select(valid_keys).iter_rows())
                t_keys = set(tuple(r) for r in target_df.select(valid_keys).iter_rows())
                missing_in_target = len(s_keys - t_keys)
                extra_in_target = len(t_keys - s_keys)

        matched = row_parity and (missing_in_target == 0) and all(c["matched"] for c in column_comparisons)

        return {
            "source_records": source_rows,
            "target_records": target_rows,
            "row_variance": row_variance,
            "row_parity": row_parity,
            "missing_in_target": missing_in_target,
            "extra_in_target": extra_in_target,
            "column_metrics": column_comparisons,
            "reconciliation_status": "MATCHED" if matched else "DISCREPANCY_DETECTED"
        }

    @classmethod
    def apply_masking(
        cls,
        df: pl.DataFrame,
        masking_rules: List[Dict[str, Any]]
    ) -> pl.DataFrame:
        """
        Applies masking transformations to sensitive columns:
        - redact: [REDACTED]
        - hash: SHA-256 hash string
        - partial_mask: e.g. ****-****-****-1234
        - nullify: None
        """
        masked_df = df.clone()

        for rule in masking_rules:
            col = rule.get("column")
            strategy = rule.get("strategy", "redact")
            if col not in masked_df.columns:
                continue

            vals = masked_df[col].to_list()
            new_vals = []

            for val in vals:
                if val is None:
                    new_vals.append(None)
                    continue

                val_str = str(val)
                if strategy == "redact":
                    new_vals.append("[REDACTED]")
                elif strategy == "hash":
                    new_vals.append(hashlib.sha256(val_str.encode("utf-8")).hexdigest())
                elif strategy == "nullify":
                    new_vals.append(None)
                elif strategy == "partial_mask":
                    # Keep last 4 chars, mask preceding with '*'
                    if len(val_str) > 4:
                        prefix_len = len(val_str) - 4
                        new_vals.append("*" * prefix_len + val_str[-4:])
                    else:
                        new_vals.append("****")
                else:
                    new_vals.append(val)

            masked_df = masked_df.with_columns(pl.Series(col, new_vals))

        return masked_df
