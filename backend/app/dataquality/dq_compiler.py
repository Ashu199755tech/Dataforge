"""
dq_compiler.py — Rulebook Metadata & Predicate Compiler (Core Engine).

Converts Rule Catalogue metadata (DQ_RULE_CATALOGUE / DIM_DQ_RULE) into
executable Boolean violation expressions (evaluating to TRUE when a record fails).

Rule Types Supported:
  - ATR1: Not Null (col IS NULL)
  - ATR2: Non-Blank (col IS NULL OR trim(col) = '')
  - ATR3: Placeholders / Sentinels ('N/A', 'UNKNOWN', '9999-99-99', etc.)
  - ATR4: Pattern / Regex (Arabic/English purity, alphanumeric, special characters)
  - ATR5: Domain set validation (col NOT IN ('Y', 'N', ...))
  - ATR6: Numeric range (col < min OR col > max)
  - ATR7: Date / Temporal boundary (date > CURRENT_DATE or before floor)
  - ATR8: Length check (length(col) NOT BETWEEN min AND max)
  - DS1:  Uniqueness check (Window count > 1 on key columns)
  - CSQL: Referential integrity (Broadcast left-anti-join on reference tables) or SQL predicate
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import polars as pl

# Arabic unicode character range for language purity checks
_ARABIC = r"\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF"

# Standard sentinels / dummy placeholder values
DEFAULT_PLACEHOLDERS = [
    "--", "---", "TBD", "TBC", "N/A", "NA", "N.A", "NONE", "NIL", "UNKNOWN",
    "NULL", "TEST", "-", ".", "..", "...", "X", "XX", "XXX", "XXXX",
    "0", "00", "000", "0000", "9999", "99999", "PENDING", "TEMP", "9999-99-99", "1900-01-01"
]


@dataclass
class DQRuleCatalogueItem:
    """
    Schema representation for DQ_RULE_CATALOGUE / DIM_DQ_RULE.
    """
    rule_id: str
    rule_type: str  # ATR1..ATR8, DS1, CSQL or descriptive name
    target_column: Optional[str] = None
    rule_expression_logic: Optional[str] = None
    technical_description: Optional[str] = None
    severity: str = "Error"  # Error, Warning
    dataset_id: Optional[str] = None
    key_columns: Optional[List[str]] = None
    placeholder_values: Optional[List[str]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DQRuleCatalogueItem:
        """Instantiates a rule catalogue item from a dictionary, case-insensitively."""
        norm = {k.lower(): v for k, v in data.items()}

        rule_id = str(norm.get("rule_id") or norm.get("id") or "").strip()
        rule_type = str(norm.get("rule_type") or norm.get("rule_type_id") or norm.get("type") or "").strip()
        target_col = norm.get("target_column") or norm.get("attribute_id") or norm.get("column") or norm.get("column_name")
        expr_logic = norm.get("rule_expression_logic") or norm.get("sql_condition") or norm.get("expression")
        tech_desc = norm.get("technical_description") or norm.get("description")
        severity = str(norm.get("severity") or "Error").strip()
        dataset_id = norm.get("dataset_id") or norm.get("table_name")

        # Parse key_columns (for DS1 uniqueness)
        raw_keys = norm.get("key_columns")
        key_cols: Optional[List[str]] = None
        if raw_keys:
            if isinstance(raw_keys, list):
                key_cols = [str(k).strip() for k in raw_keys if str(k).strip()]
            elif isinstance(raw_keys, str):
                key_cols = [k.strip() for k in raw_keys.split(",") if k.strip()]

        # Parse placeholder values (for ATR3)
        raw_ph = norm.get("placeholder_values") or norm.get("placeholders")
        placeholders: Optional[List[str]] = None
        if raw_ph:
            if isinstance(raw_ph, list):
                placeholders = [str(p).strip() for p in raw_ph if str(p).strip()]
            elif isinstance(raw_ph, str):
                placeholders = [p.strip() for p in raw_ph.split(",") if p.strip()]

        params = norm.get("parameters") or norm.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        is_active = norm.get("is_active", True)
        if isinstance(is_active, str):
            is_active = is_active.lower() not in ("false", "0", "n", "no", "f")

        return cls(
            rule_id=rule_id,
            rule_type=rule_type,
            target_column=str(target_col).strip() if target_col else None,
            rule_expression_logic=str(expr_logic).strip() if expr_logic else None,
            technical_description=str(tech_desc).strip() if tech_desc else None,
            severity=severity,
            dataset_id=str(dataset_id).strip() if dataset_id else None,
            key_columns=key_cols,
            placeholder_values=placeholders,
            parameters=params,
            is_active=bool(is_active)
        )


def normalise_rule_type_id(rule_type: str) -> str:
    """Normalises human rule type or code to standard rule type ID (ATR1..ATR8, DS1, CSQL)."""
    t = rule_type.upper().strip()
    if t in ("ATR1", "ATR2", "ATR3", "ATR4", "ATR5", "ATR6", "ATR7", "ATR8", "DS1", "CSQL"):
        return t

    tl = rule_type.lower()
    if "not null" in tl or "mandatory" in tl:
        return "ATR1"
    if "non-blank" in tl or "non blank" in tl or "empty string" in tl:
        return "ATR2"
    if "placeholder" in tl or "sentinel" in tl:
        return "ATR3"
    if "pattern" in tl or "regex" in tl or "purity" in tl or "alphanumeric" in tl:
        return "ATR4"
    if "domain" in tl or "controlled list" in tl or "allowed values" in tl or "permissible" in tl:
        return "ATR5"
    if "range" in tl or "numeric" in tl or "greater than" in tl or "less than" in tl or "positive" in tl:
        return "ATR6"
    if "date" in tl or "temporal" in tl or "future" in tl:
        return "ATR7"
    if "length" in tl:
        return "ATR8"
    if "unique" in tl or "duplicate" in tl or "primary key" in tl:
        return "DS1"
    if "referential" in tl or "foreign key" in tl or "orphan" in tl or "custom sql" in tl:
        return "CSQL"

    return t


def derive_params(rule: Union[DQRuleCatalogueItem, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Derives rule parameters from rule metadata and technical description,
    mirroring the reference enforcement engine parameter derivation.
    """
    if isinstance(rule, DQRuleCatalogueItem):
        rtid = normalise_rule_type_id(rule.rule_type)
        t = (rule.rule_type or "").lower()
        desc = rule.technical_description or ""
        target_col = rule.target_column or ""
        p: Dict[str, Any] = dict(rule.parameters)
        if rule.placeholder_values:
            p["placeholders"] = rule.placeholder_values
        if rule.key_columns:
            p["key_columns"] = rule.key_columns
    else:
        norm = {k.lower(): v for k, v in rule.items()}
        rtid = normalise_rule_type_id(str(norm.get("rule_type") or norm.get("rule_type_id") or ""))
        t = str(norm.get("rule_type") or "").lower()
        desc = str(norm.get("technical_description") or norm.get("description") or "")
        target_col = str(norm.get("target_column") or norm.get("attribute_id") or "")
        p = dict(norm.get("parameters") or norm.get("params") or {})
        if norm.get("placeholder_values"):
            p["placeholders"] = norm["placeholder_values"]
        if norm.get("key_columns"):
            p["key_columns"] = norm["key_columns"]

    dl = desc.lower()

    # ATR3: Placeholders
    if rtid == "ATR3":
        if "placeholders" not in p:
            p["placeholders"] = DEFAULT_PLACEHOLDERS

    # ATR4: Pattern / Regex
    elif rtid == "ATR4":
        if "pattern" not in p:
            if re.search(r"\b(arabic\s+(?:language\s+)?purity|no\s+(?:latin|english))\b", dl) or target_col.upper().endswith("_AR"):
                p.update(pattern=r"[A-Za-z]", negate=True)
            elif re.search(r"\b(english\s+(?:language\s+)?purity|no\s+arabic)\b", dl) or target_col.upper().endswith("_EN"):
                p.update(pattern=r"[" + _ARABIC + r"]", negate=True)
            elif "symbol-only" in t or "symbol only" in t or "valid characters" in t:
                p.update(pattern=r"[A-Za-z" + _ARABIC + r"]", negate=False)
            elif "special character" in t or "no special" in t or "special characters" in dl:
                p.update(pattern=r"[^0-9A-Za-z " + _ARABIC + r"]", negate=True)
            elif "alphanumeric" in t or "alphanumeric" in dl:
                p.update(pattern=r"^[A-Za-z0-9]+$", negate=False)

    # ATR5: Domain set validation
    elif rtid == "ATR5":
        if "domain" not in p and "allowed_values" not in p:
            if "boolean" in dl or re.search(r"\b(?:y\s*/\s*n|y or n|n or y|yes or no)\b", dl):
                p["domain"] = ["Y", "N"]
            else:
                m = (re.search(r"(?:permissible|allowed|valid|accepted|possible)?\s*values?\s*:\s*(.+)$", desc, re.IGNORECASE)
                     or re.search(r"\bone of\b\s*:?\s*(.+)$", desc, re.IGNORECASE))
                if m:
                    vals = re.split(r"\s*(?:,| or | and |/)\s*", m.group(1))
                    vals = [v.strip().strip(".'\"") for v in vals if v.strip()]
                    vals = [v for v in vals if v and len(v) <= 40]
                    if 1 < len(vals) <= 50:
                        p["domain"] = vals

    # ATR6: Numeric range
    elif rtid == "ATR6":
        if "range_min" not in p and "range_max" not in p:
            m = re.search(r"(?:range\s*(?:from|of|:)?\s*|between\s+)(-?\d+(?:\.\d+)?)\s*(?:to|and|-|\u2013|\u2014)\s*(-?\d+(?:\.\d+)?)", dl)
            if m:
                p.update(range_min=float(m.group(1)), range_max=float(m.group(2)))
            if "positive" in t or "positive" in dl:
                p.setdefault("range_min", 0.0)
            if "greater than zero" in dl or "greater than 0" in dl:
                p["range_min"] = 0.0
                p["exclusive_min"] = True

    # ATR7: Date / Temporal boundary
    elif rtid == "ATR7":
        if "date_max" not in p and "date_min" not in p:
            if ("not in future" in t or "no future" in t or "not greater than the current" in dl
                    or "current business date" in dl or "not be in the future" in dl):
                p["date_max"] = "current"
            m = re.search(r"earlier than\s+(?:date\s+)?'?(\d{4}-\d{2}-\d{2})'?", dl)
            if m:
                p["date_min"] = m.group(1)
            m2 = re.search(r"(?:on or after|not earlier than|not before)\s+(\d{1,2})[- ]([A-Za-z]{3})[- ](\d{4})", desc, re.IGNORECASE)
            if m2:
                mon = {
                    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
                }.get(m2.group(2).lower())
                if mon:
                    p["date_min"] = f"{m2.group(3)}-{mon}-{int(m2.group(1)):02d}"

    # ATR8: Length check
    elif rtid == "ATR8":
        if "length_min" not in p and "length_max" not in p:
            m_exact = re.search(r"(?:length of|exactly|fixed length(?:\s*of)?|length\s*=\s*)\s*(\d+)", dl)
            m_max = re.search(r"(?:not exceed|max(?:imum)?(?:\s+of)?|up to|<=?)\s*(\d+)", dl)
            if m_exact:
                n = int(m_exact.group(1))
                p.update(length_min=n, length_max=n)
            elif m_max:
                p.update(length_min=0, length_max=int(m_max.group(1)))

    return p


def parse_csql_refs(sql: str) -> Optional[Dict[str, str]]:
    """
    Extracts (fk, ref_schema, ref_table, ref_key) from referential integrity SQL
    (both NOT EXISTS and LEFT JOIN ... IS NULL forms).
    """
    if not sql:
        return None

    # NOT EXISTS form
    m = re.search(
        r"NOT EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+(?:([A-Za-z0-9_]+)\.)?([A-Za-z0-9_]+)\s+\w+\s+"
        r"WHERE\s+\w+\.([A-Za-z0-9_]+)\s*=\s*\w+\.([A-Za-z0-9_]+)",
        sql, re.IGNORECASE
    )
    if m:
        return {
            "ref_schema": m.group(1) or "",
            "ref_table": m.group(2),
            "ref_key": m.group(3),
            "fk": m.group(4)
        }

    # LEFT JOIN form
    j = re.search(
        r"LEFT\s+(?:OUTER\s+)?JOIN\s+(?:([A-Za-z0-9_]+)\.)?([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s+ON\s+"
        r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)",
        sql, re.IGNORECASE
    )
    if j and re.search(rf"\b{re.escape(j.group(3))}\.[A-Za-z0-9_]+\s+IS\s+NULL", sql, re.IGNORECASE):
        ref_schema, ref_table, ref_alias = j.group(1) or "", j.group(2), j.group(3)
        a1, c1, a2, c2 = j.group(4), j.group(5), j.group(6), j.group(7)
        if a1.upper() == ref_alias.upper():
            ref_key, fk = c1, c2
        else:
            ref_key, fk = c2, c1
        return {
            "ref_schema": ref_schema,
            "ref_table": ref_table,
            "ref_key": ref_key,
            "fk": fk
        }

    return None


class DQPredicateCompiler:
    """
    Core Predicate Compiler.
    Transforms rule metadata into Polars Boolean violation expressions.
    Expression evaluates to TRUE for rows that BREAK the rule.
    """

    @classmethod
    def compile_violation(
        cls,
        rule_item: Union[DQRuleCatalogueItem, Dict[str, Any]],
        df_columns: List[str],
        ref_frames: Optional[Dict[str, pl.DataFrame]] = None
    ) -> Optional[pl.Expr]:
        """
        Compiles a single rule into a Polars violation expression.
        Returns None if the rule cannot be compiled (e.g. target column missing from df).
        """
        ref_frames = ref_frames or {}

        if not isinstance(rule_item, DQRuleCatalogueItem):
            rule_item = DQRuleCatalogueItem.from_dict(rule_item)

        rtid = normalise_rule_type_id(rule_item.rule_type)
        col = rule_item.target_column
        p = derive_params(rule_item)

        # -------------------------------------------------------------
        # DS1: Uniqueness check (Window count > 1)
        # -------------------------------------------------------------
        if rtid == "DS1":
            keys = rule_item.key_columns or p.get("key_columns")
            if not keys:
                if col and col in df_columns:
                    keys = [col]
            if not keys:
                return None
            clean_keys = [k.strip() for k in keys if k.strip() in df_columns]
            if not clean_keys:
                return None

            all_non_null = pl.all_horizontal([pl.col(k).is_not_null() for k in clean_keys])
            is_dup = pl.len().over(clean_keys) > 1
            return all_non_null & is_dup

        # -------------------------------------------------------------
        # CSQL: Referential Integrity (Anti-Join) or SQL expression
        # -------------------------------------------------------------
        if rtid == "CSQL":
            csql_info = parse_csql_refs(rule_item.rule_expression_logic or "")
            fk = (csql_info.get("fk") if csql_info else None) or col or p.get("foreign_key")
            ref_table = (csql_info.get("ref_table") if csql_info else None) or p.get("reference_table")
            ref_key = (csql_info.get("ref_key") if csql_info else None) or p.get("reference_key") or p.get("reference_column")

            if fk and ref_table and ref_key and fk in df_columns:
                # Find matching reference dataframe
                ref_df = None
                for cand in (ref_table, ref_table.upper(), ref_table.lower()):
                    if cand in ref_frames:
                        ref_df = ref_frames[cand]
                        break
                if ref_df is not None and ref_key in ref_df.columns:
                    valid_keys = ref_df[ref_key].drop_nulls().unique().to_list()
                    return pl.col(fk).is_not_null() & (~pl.col(fk).is_in(valid_keys))

            # Custom SQL expression logic (e.g. "retail_price >= cost * 1.2")
            if rule_item.rule_expression_logic:
                sql_cond = rule_item.rule_expression_logic.strip()
                # If SQL logic is single-table condition, return custom expression marker
                # Handled via pl.sql_expr in evaluate_rules or custom predicate
                return None

            return None

        # Remaining attribute checks require target_column in df_columns
        if not col or col not in df_columns:
            return None

        c = pl.col(col)
        s = c.cast(pl.Utf8)

        # -------------------------------------------------------------
        # ATR1: Not Null (col IS NULL)
        # -------------------------------------------------------------
        if rtid == "ATR1":
            return c.is_null()

        # -------------------------------------------------------------
        # ATR2: Non-Blank (col IS NULL OR trim(col) == '')
        # -------------------------------------------------------------
        if rtid == "ATR2":
            return c.is_null() | (s.str.strip_chars() == "")

        # -------------------------------------------------------------
        # ATR3: Placeholders / Sentinels
        # -------------------------------------------------------------
        if rtid == "ATR3":
            raw_ph = p.get("placeholders") or DEFAULT_PLACEHOLDERS
            ph_list = [str(x).strip().upper() for x in raw_ph if str(x).strip()]
            norm_s = s.str.strip_chars().str.to_uppercase()
            return c.is_null() | norm_s.is_in(ph_list)

        # -------------------------------------------------------------
        # ATR4: Pattern / Regex Check
        # -------------------------------------------------------------
        if rtid == "ATR4":
            pat = p.get("pattern")
            if not pat:
                return None
            negate = bool(p.get("negate", False))
            match_expr = s.str.contains(pat)
            if negate:
                # Violation when null OR matches prohibited pattern (e.g. latin in Arabic)
                return c.is_null() | match_expr
            else:
                # Violation when null OR does NOT match required pattern
                return c.is_null() | (~match_expr)

        # -------------------------------------------------------------
        # ATR5: Domain Set Validation (Controlled List)
        # Non-null scoped: only non-null values outside domain violate
        # -------------------------------------------------------------
        if rtid == "ATR5":
            dom = p.get("domain") or p.get("allowed_values") or p.get("domain_values")
            if not dom:
                return None
            allowed = [str(d).strip().upper() for d in dom if str(d).strip()]
            norm_s = s.str.strip_chars().str.to_uppercase()
            return c.is_not_null() & (~norm_s.is_in(allowed))

        # -------------------------------------------------------------
        # ATR6: Numeric Range Validation
        # Non-null scoped: non-numeric or out-of-range violate
        # -------------------------------------------------------------
        if rtid == "ATR6":
            r_min = p.get("range_min") if p.get("range_min") is not None else p.get("min_value")
            r_max = p.get("range_max") if p.get("range_max") is not None else p.get("max_value")
            if r_min is None and r_max is None:
                return None

            num = c.cast(pl.Float64, strict=False)
            cond = num.is_null()

            if r_min is not None:
                r_min_flt = float(r_min)
                if p.get("exclusive_min"):
                    cond = cond | (num <= pl.lit(r_min_flt))
                else:
                    cond = cond | (num < pl.lit(r_min_flt))

            if r_max is not None:
                r_max_flt = float(r_max)
                if p.get("exclusive_max"):
                    cond = cond | (num >= pl.lit(r_max_flt))
                else:
                    cond = cond | (num > pl.lit(r_max_flt))

            return c.is_not_null() & cond

        # -------------------------------------------------------------
        # ATR7: Date / Temporal Boundary
        # Non-null scoped: future date or date earlier than floor violate
        # -------------------------------------------------------------
        if rtid == "ATR7":
            d_min = p.get("date_min")
            d_max = p.get("date_max")
            if not d_min and not d_max:
                return None

            # Attempt date parsing
            dt_col = s.str.to_date(strict=False)
            cond = dt_col.is_null()

            if d_max == "current" or d_max == "CURRENT_DATE":
                curr_d = datetime.now(timezone.utc).date()
                cond = cond | (dt_col > pl.lit(curr_d))
            elif isinstance(d_max, str) and d_max:
                try:
                    parsed_max = date.fromisoformat(d_max)
                    cond = cond | (dt_col > pl.lit(parsed_max))
                except Exception:
                    pass

            if isinstance(d_min, str) and d_min:
                try:
                    parsed_min = date.fromisoformat(d_min)
                    cond = cond | (dt_col < pl.lit(parsed_min))
                except Exception:
                    pass

            return c.is_not_null() & cond

        # -------------------------------------------------------------
        # ATR8: Length Check
        # Non-null scoped: string length outside bounds violates
        # -------------------------------------------------------------
        if rtid == "ATR8":
            l_min = p.get("length_min")
            l_max = p.get("length_max")
            if l_min is None and l_max is None:
                return None

            ln = s.str.len_chars()
            cond = pl.lit(False)

            if l_min is not None:
                cond = cond | (ln < pl.lit(int(l_min)))
            if l_max is not None:
                cond = cond | (ln > pl.lit(int(l_max)))

            return c.is_not_null() & cond

        return None

    @classmethod
    def compile_all(
        cls,
        rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
        df_columns: List[str],
        ref_frames: Optional[Dict[str, pl.DataFrame]] = None
    ) -> Dict[str, pl.Expr]:
        """
        Compiles all applicable rules into a mapping of {rule_id: violation_expr}.
        """
        compiled: Dict[str, pl.Expr] = {}
        for r in rules:
            item = r if isinstance(r, DQRuleCatalogueItem) else DQRuleCatalogueItem.from_dict(r)
            if not item.is_active:
                continue
            expr = cls.compile_violation(item, df_columns, ref_frames)
            if expr is not None:
                compiled[item.rule_id] = expr
        return compiled

    @classmethod
    def evaluate_violations(
        cls,
        df: pl.DataFrame,
        rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
        ref_frames: Optional[Dict[str, pl.DataFrame]] = None
    ) -> Dict[str, List[int]]:
        """
        Evaluates compiled rules against a DataFrame and returns:
          {rule_id: [violating_row_indices]}
        Handles expression evaluation and CSQL SQL queries.
        """
        ref_frames = ref_frames or {}
        compiled = cls.compile_all(rules, df.columns, ref_frames)
        violations_map: Dict[str, List[int]] = {}

        if not compiled and not any(normalise_rule_type_id(str(r.get("rule_type") if isinstance(r, dict) else r.rule_type)) == "CSQL" for r in rules):
            return violations_map

        # Evaluate compiled expressions in parallel
        if compiled:
            # Select all violation columns
            eval_cols = [expr.alias(f"__viol_{rid}") for rid, expr in compiled.items()]
            res_df = df.select(eval_cols)
            for rid in compiled.keys():
                col_name = f"__viol_{rid}"
                series = res_df[col_name]
                viol_indices = [idx for idx, is_viol in enumerate(series.to_list()) if is_viol is True]
                violations_map[rid] = viol_indices

        # Handle CSQL custom SQL conditions if not handled via anti-join
        for r in rules:
            item = r if isinstance(r, DQRuleCatalogueItem) else DQRuleCatalogueItem.from_dict(r)
            if not item.is_active or item.rule_id in violations_map:
                continue
            rtid = normalise_rule_type_id(item.rule_type)
            if rtid == "CSQL" and item.rule_expression_logic:
                sql_cond = item.rule_expression_logic.strip()
                if not sql_cond.upper().startswith("SELECT") and "FROM" not in sql_cond.upper():
                    # It is a Boolean expression like "retail >= cost * 1.1"
                    try:
                        sql_ctx = pl.SQLContext(df=df)
                        query = f"SELECT NOT ({sql_cond}) AS __viol FROM df"
                        viol_series = sql_ctx.execute(query).collect()["__viol"]
                        violations_map[item.rule_id] = [idx for idx, v in enumerate(viol_series.to_list()) if v is True]
                    except Exception:
                        pass

        return violations_map
