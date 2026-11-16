"""
test_dq_compiler.py — Offline Unit Tests for Phase 1: Rulebook Metadata & Predicate Compiler.

Verifies:
  1. DQRuleCatalogueItem schema parsing and database model.
  2. Predicate compiler for each rule type:
     - ATR1: Not Null (col IS NULL)
     - ATR2: Non-Blank (col IS NULL OR trim(col) = '')
     - ATR3: Placeholders / Sentinels ('N/A', 'UNKNOWN', '9999-99-99')
     - ATR4: Pattern / Regex (Alphanumeric, Arabic/English purity, custom regex)
     - ATR5: Domain set validation (col NOT IN ('Y', 'N', ...))
     - ATR6: Numeric range (col < min OR col > max, positive / > 0)
     - ATR7: Date / Temporal boundary (date > CURRENT_DATE or before floor)
     - ATR8: Length check (length(col) NOT BETWEEN min AND max)
     - DS1:  Uniqueness check (Window count > 1 on key columns)
     - CSQL: Referential integrity (anti-join against reference table) & custom SQL conditions
  3. Bulk evaluation and multi-rule evaluation mapping.
"""
from datetime import date, datetime, timedelta, timezone
import polars as pl
import pytest

from backend.app.dataquality.dq_compiler import (
    DQPredicateCompiler,
    DQRuleCatalogueItem,
    derive_params,
    normalise_rule_type_id,
    parse_csql_refs,
    DEFAULT_PLACEHOLDERS
)
from backend.app.models.data_quality import DQRuleCatalogue, DimDQRule


def _violating_ids(df: pl.DataFrame, rule: dict, ref_frames=None) -> set:
    """Helper that compiles a rule, runs it on df, and returns IDs of violating rows."""
    item = DQRuleCatalogueItem.from_dict(rule)
    expr = DQPredicateCompiler.compile_violation(item, df.columns, ref_frames)
    if expr is None:
        return None
    viol_series = df.select(expr.alias("viol"))["viol"]
    return set(df.filter(viol_series)["id"].to_list())


# ==============================================================================
# 1. Rulebook Metadata Schema & Normalisation Tests
# ==============================================================================

def test_dq_rule_catalogue_schema_and_normalisation():
    """Verify DQRuleCatalogueItem parses uppercase catalogue fields and handles case-insensitivity."""
    raw = {
        "RULE_ID": "R_CUST_001",
        "RULE_TYPE": "ATR1",
        "TARGET_COLUMN": "customer_id",
        "RULE_EXPRESSION_LOGIC": "customer_id IS NOT NULL",
        "TECHNICAL_DESCRIPTION": "Ensures customer_id is mandatory and never null",
        "SEVERITY": "Error",
        "KEY_COLUMNS": "customer_id, branch_id",
        "PLACEHOLDER_VALUES": "N/A, TBD, UNKNOWN",
        "IS_ACTIVE": "Y"
    }

    item = DQRuleCatalogueItem.from_dict(raw)
    assert item.rule_id == "R_CUST_001"
    assert item.rule_type == "ATR1"
    assert item.target_column == "customer_id"
    assert item.rule_expression_logic == "customer_id IS NOT NULL"
    assert item.severity == "Error"
    assert item.key_columns == ["customer_id", "branch_id"]
    assert item.placeholder_values == ["N/A", "TBD", "UNKNOWN"]
    assert item.is_active is True

    # Verify SQLAlchemy model aliases
    db_model = DQRuleCatalogue(
        rule_id="R_CUST_002",
        rule_type="ATR2",
        target_column="email",
        severity="Warning"
    )
    assert db_model.rule_id == "R_CUST_002"
    assert DimDQRule is DQRuleCatalogue


def test_normalise_rule_type_id():
    """Verify human rule types map accurately to standard ATR1..8, DS1, CSQL."""
    assert normalise_rule_type_id("Not Null") == "ATR1"
    assert normalise_rule_type_id("MandatoryFieldCheck") == "ATR1"
    assert normalise_rule_type_id("Non-Blank Check") == "ATR2"
    assert normalise_rule_type_id("Placeholder Check") == "ATR3"
    assert normalise_rule_type_id("Alphanumeric Pattern Check") == "ATR4"
    assert normalise_rule_type_id("Domain Validation") == "ATR5"
    assert normalise_rule_type_id("Numeric Range Check") == "ATR6"
    assert normalise_rule_type_id("Temporal / Date Check") == "ATR7"
    assert normalise_rule_type_id("Length Check") == "ATR8"
    assert normalise_rule_type_id("Primary Key Uniqueness") == "DS1"
    assert normalise_rule_type_id("Referential Integrity Check") == "CSQL"


# ==============================================================================
# 2. Predicate Compiler Rule Types (ATR1 - ATR8, DS1, CSQL)
# ==============================================================================

def test_atr1_not_null():
    """ATR1 Not Null: row is a violation when column value is NULL."""
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "v": ["valid", None, "another_valid"]
    })
    rule = {"rule_id": "R1", "rule_type": "ATR1", "target_column": "v"}
    assert _violating_ids(df, rule) == {2}


def test_atr2_non_blank():
    """ATR2 Non-Blank: row is a violation when NULL, empty string, or whitespace-only."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "v": ["real_text", None, "   ", "", "  spaced  "]
    })
    rule = {"rule_id": "R2", "rule_type": "ATR2", "target_column": "v"}
    # 2 is Null, 3 is whitespace, 4 is empty string -> all violations
    assert _violating_ids(df, rule) == {2, 3, 4}


def test_atr3_placeholders_and_sentinels():
    """ATR3 Placeholders: row is a violation when NULL or matches sentinel token."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7],
        "v": ["Acme Corp", "N/A", "tbd", None, "UNKNOWN", "9999-99-99", "Real Name"]
    })
    rule = {"rule_id": "R3", "rule_type": "ATR3", "target_column": "v"}
    assert _violating_ids(df, rule) == {2, 3, 4, 5, 6}

    # Custom placeholder overrides
    rule_custom = {
        "rule_id": "R3_custom",
        "rule_type": "ATR3",
        "target_column": "v",
        "placeholder_values": ["N/A", "TBD"]
    }
    # 2 (N/A), 3 (tbd), 4 (None) violate
    assert _violating_ids(df, rule_custom) == {2, 3, 4}


def test_atr4_pattern_alphanumeric():
    """ATR4 Alphanumeric: violation when non-alphanumeric or NULL."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "v": ["ABC123", "has space", "ok!", None]
    })
    rule = {
        "rule_id": "R4_alpha",
        "rule_type": "ATR4",
        "target_column": "v",
        "technical_description": "Must be alphanumeric string"
    }
    assert _violating_ids(df, rule) == {2, 3, 4}


def test_atr4_pattern_arabic_purity():
    """ATR4 Arabic Purity: violation when text contains Latin characters."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "DESC_AR": ["\u0645\u0631\u062d\u0628\u0627", "hello", "\u0639\u0631\u0628\u064aA", None]
    })
    rule = {
        "rule_id": "R4_ar",
        "rule_type": "ATR4",
        "target_column": "DESC_AR",
        "technical_description": "Arabic language purity (no latin)"
    }
    assert _violating_ids(df, rule) == {2, 3, 4}


def test_atr4_pattern_english_purity():
    """ATR4 English Purity: violation when text contains Arabic characters."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "DESC_EN": ["Valid English Text", "English with \u0645\u0631\u062d\u0628\u0627", "All Good", None]
    })
    rule = {
        "rule_id": "R4_en",
        "rule_type": "ATR4",
        "target_column": "DESC_EN",
        "technical_description": "English language purity (no arabic characters)"
    }
    assert _violating_ids(df, rule) == {2, 4}


def test_atr5_domain_validation():
    """ATR5 Domain: violation when non-null value is not in permitted set (Null is not a domain violation)."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "status": ["Y", "N", "INVALID", None, "maybe"]
    })
    rule = {
        "rule_id": "R5",
        "rule_type": "ATR5",
        "target_column": "status",
        "technical_description": "Flag must be boolean Y or N"
    }
    # 3 (INVALID) and 5 (maybe) violate. 4 (None) is not a domain violation.
    assert _violating_ids(df, rule) == {3, 5}


def test_atr6_numeric_range_positive_and_bounded():
    """ATR6 Numeric Range: violation when non-numeric, or outside [min, max]."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4, 5, 6],
        "amount": ["5.5", "0.0", "-3.2", "not_a_num", None, "100.0"]
    })

    # Positive (> 0): 0.0, -3.2, and not_a_num violate
    rule_pos = {
        "rule_id": "R6_pos",
        "rule_type": "ATR6",
        "target_column": "amount",
        "technical_description": "must be a positive amount greater than zero"
    }
    assert _violating_ids(df, rule_pos) == {2, 3, 4}

    # Bounded range [10, 50]
    rule_bound = {
        "rule_id": "R6_bound",
        "rule_type": "ATR6",
        "target_column": "amount",
        "technical_description": "range from 10 to 50"
    }
    # 1 (5.5 < 10), 2 (0 < 10), 3 (-3.2 < 10), 4 (not_a_num), 6 (100 > 50) violate
    assert _violating_ids(df, rule_bound) == {1, 2, 3, 4, 6}


def test_atr7_date_temporal_boundary():
    """ATR7 Date: violation when future date or before floor date."""
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "event_date": [yesterday, tomorrow, "1960-01-01", None]
    })

    # Not in future check
    rule_future = {
        "rule_id": "R7_fut",
        "rule_type": "ATR7",
        "target_column": "event_date",
        "technical_description": "date must not be in the future"
    }
    assert _violating_ids(df, rule_future) == {2}

    # Date floor check (on or after 01-Jan-1970)
    rule_floor = {
        "rule_id": "R7_floor",
        "rule_type": "ATR7",
        "target_column": "event_date",
        "technical_description": "Ensures date is on or after 01-Jan-1970"
    }
    # 3 (1960-01-01) violates
    assert _violating_ids(df, rule_floor) == {3}


def test_atr8_length_check():
    """ATR8 Length: violation when string length does not meet boundary."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "national_id": ["123456789012", "123", None, "1234567890123"]
    })
    rule = {
        "rule_id": "R8",
        "rule_type": "ATR8",
        "target_column": "national_id",
        "technical_description": "must have a length of 12 characters"
    }
    # 2 (length 3) and 4 (length 13) violate. 3 (None) is not an ATR8 violation.
    assert _violating_ids(df, rule) == {2, 4}


def test_ds1_uniqueness_check():
    """DS1 Uniqueness: violation when non-null key is duplicated in the dataset."""
    # 1. Single-column uniqueness
    df_single = pl.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "sku": ["SKU_A", "SKU_B", "SKU_A", None, "SKU_C"]
    })
    rule_single = {
        "rule_id": "DS1_single",
        "rule_type": "DS1",
        "target_column": "sku",
        "key_columns": ["sku"]
    }
    # Row 1 and 3 share "SKU_A" -> both violate uniqueness. None is not duplicated.
    assert _violating_ids(df_single, rule_single) == {1, 3}

    # 2. Composite key uniqueness
    df_comp = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "k1": ["A", "A", "A", "B"],
        "k2": [10, 20, 10, 10]
    })
    rule_comp = {
        "rule_id": "DS1_comp",
        "rule_type": "DS1",
        "key_columns": ["k1", "k2"]
    }
    # Row 1 and 3 share ('A', 10) -> violate
    assert _violating_ids(df_comp, rule_comp) == {1, 3}


def test_csql_referential_integrity():
    """CSQL Referential Integrity: flags foreign keys not found in reference table."""
    df_orders = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "customer_id": [100, 200, 999, None]  # 999 does not exist in customers
    })
    df_customers = pl.DataFrame({
        "cust_id": [100, 200, 300]
    })
    ref_frames = {"dim_customers": df_customers}

    rule_fk = {
        "rule_id": "CSQL_fk",
        "rule_type": "CSQL",
        "target_column": "customer_id",
        "rule_expression_logic": "NOT EXISTS (SELECT 1 FROM schema.dim_customers c WHERE c.cust_id = m.customer_id)"
    }
    assert _violating_ids(df_orders, rule_fk, ref_frames=ref_frames) == {3}


def test_csql_custom_sql_expression():
    """CSQL Custom SQL: evaluates boolean expressions via evaluate_violations."""
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "cost": [10.0, 20.0, 50.0],
        "retail": [15.0, 18.0, 70.0]  # row 2 has 18 < 20 * 1.1 = 22
    })
    rule_sql = {
        "rule_id": "CSQL_expr",
        "rule_type": "CSQL",
        "rule_expression_logic": "retail >= cost * 1.1"
    }
    viol_map = DQPredicateCompiler.evaluate_violations(df, [rule_sql])
    # Index 1 corresponds to id 2
    assert viol_map["CSQL_expr"] == [1]


# ==============================================================================
# 3. Multi-Rule Compilation & Bulk Evaluation
# ==============================================================================

def test_multi_rule_evaluation():
    """Verify evaluate_violations compiles and executes multiple diverse rules in a single pass."""
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "email": ["user@corp.com", "", "invalid_email"],
        "age": [25, 17, 40]
    })

    rules = [
        {
            "rule_id": "R_NON_BLANK_EMAIL",
            "rule_type": "ATR2",
            "target_column": "email"
        },
        {
            "rule_id": "R_ADULT_AGE",
            "rule_type": "ATR6",
            "target_column": "age",
            "parameters": {"range_min": 18}
        }
    ]

    viol_map = DQPredicateCompiler.evaluate_violations(df, rules)
    # Email non-blank fails for row index 1 (id 2, "")
    assert viol_map["R_NON_BLANK_EMAIL"] == [1]
    # Age >= 18 fails for row index 1 (id 2, 17)
    assert viol_map["R_ADULT_AGE"] == [1]


def test_missing_column_returns_none():
    """Rules targeting columns not present in the dataframe must return None (skipped, not failed)."""
    df = pl.DataFrame({"id": [1, 2]})
    rule = {"rule_id": "R_MISSING", "rule_type": "ATR1", "target_column": "non_existent_col"}
    expr = DQPredicateCompiler.compile_violation(rule, df.columns)
    assert expr is None


def test_parse_csql_refs():
    """Verify parse_csql_refs accurately extracts foreign key and reference details from both SQL formats."""
    # 1. NOT EXISTS format
    sql1 = "NOT EXISTS (SELECT 1 FROM HR.DEPARTMENTS d WHERE d.DEPT_ID = m.EMP_DEPT_ID)"
    res1 = parse_csql_refs(sql1)
    assert res1["ref_schema"] == "HR"
    assert res1["ref_table"] == "DEPARTMENTS"
    assert res1["ref_key"] == "DEPT_ID"
    assert res1["fk"] == "EMP_DEPT_ID"

    # 2. LEFT JOIN ... IS NULL format
    sql2 = "SELECT c.* FROM SALES.ORDERS c LEFT OUTER JOIN SALES.CUSTOMERS p ON c.CUST_ID = p.CUSTOMER_ID WHERE p.CUSTOMER_ID IS NULL"
    res2 = parse_csql_refs(sql2)
    assert res2["ref_table"] == "CUSTOMERS"
    assert res2["ref_key"] == "CUSTOMER_ID"
    assert res2["fk"] == "CUST_ID"
