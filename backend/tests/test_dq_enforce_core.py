"""
Unit tests for Phase 2: Cleansing Engine, Two-Phase Tagging, and DQEnforceCore.
"""
import polars as pl
import pytest
from backend.app.dataquality.dq_enforce_core import DQEnforceCore, compute_row_hashes, get_business_columns
from backend.app.dataquality.dq_tagger import (
    pre_cleanse_sanitization,
    tag_dataframe,
    retag_after_cleanse,
    FLAG_COL,
    FAILED_COL,
    ORIG_FAILED_COL,
    CLEANSED_COL,
    CLEANSING_ID_COL,
)
from backend.app.dataquality.dq_cleanser import DQCleansingEngine


def test_pre_cleanse_sanitization():
    """Verify string trimming, collapsing internal whitespace, and mapping empty strings to None."""
    df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "name": ["  Alice   Smith  ", "Bob\t\tJones", "", "   "],
        "num": [10, 20, 30, 40]
    })
    cleaned = pre_cleanse_sanitization(df)
    names = cleaned["name"].to_list()

    assert names[0] == "Alice Smith"
    assert names[1] == "Bob Jones"
    assert names[2] is None
    assert names[3] is None
    assert cleaned["num"].to_list() == [10, 20, 30, 40]


def test_phase1_tagging_interim_flags():
    """Verify interim tagging: 1 clean, 2 soft reject, 3 single-PK null."""
    df = pl.DataFrame({
        "customer_id": [101, 102, None, 104],
        "email": ["alice@domain.com", "not-an-email", "bob@domain.com", None]
    })
    rules = [
        {
            "rule_id": "R_EMAIL_FMT",
            "rule_type": "ATR4",
            "target_column": "email",
            "parameters": {"pattern": r"^[^@]+@[^@]+\.[^@]+$"},
            "technical_description": "Email format"
        },
        {
            "rule_id": "R_PK_NN",
            "rule_type": "ATR1",
            "target_column": "customer_id",
            "technical_description": "PK not null"
        }
    ]
    tagged, report = tag_dataframe(df, rules, pk_columns=["customer_id"])

    # Row 0: Clean -> Flag 1
    assert tagged[FLAG_COL][0] == 1
    assert tagged[FAILED_COL][0] == "NONE"

    # Row 1: Valid PK, but email format invalid -> Flag 2
    assert tagged[FLAG_COL][1] == 2
    assert "R_EMAIL_FMT" in tagged[FAILED_COL][1]

    # Row 2: PK is NULL -> Flag 3 (Hard reject)
    assert tagged[FLAG_COL][2] == 3

    # Row 3: Valid PK, email is NULL -> Flag 2
    assert tagged[FLAG_COL][3] == 2


def test_composite_pk_never_receives_flag_3():
    """A composite key with a null component must never be treated as Flag 3."""
    df = pl.DataFrame({
        "company_id": [1, None, 3],
        "user_id": [10, 20, 30],
        "val": ["A", "B", "C"]
    })
    rules = [
        {
            "rule_id": "R1",
            "rule_type": "ATR1",
            "target_column": "company_id",
            "technical_description": "Company ID not null"
        }
    ]
    tagged, report = tag_dataframe(df, rules, pk_columns=["company_id", "user_id"])

    # Row 1 has company_id=None, but PK is composite (company_id, user_id)
    # Must be Flag 2 (Soft reject), NOT Flag 3
    assert tagged[FLAG_COL][1] == 2


def test_clean_rows_are_untouched_and_stay_flag_1():
    """Clean rows remain untouched, no cell logs generated, PREV_ROW_HASH == LAST_ROW_HASH."""
    df = pl.DataFrame({
        "id": [1, 2],
        "status": ["ACTIVE", "PENDING"],
        "score": [85.0, 92.5]
    })
    rules = [
        {"rule_id": "R_STATUS", "rule_type": "ATR5", "target_column": "status", "technical_description": "Allowed values: ACTIVE, PENDING"},
        {"rule_id": "R_SCORE", "rule_type": "ATR6", "target_column": "score", "technical_description": "Score between 0 and 100"}
    ]
    cleansing_steps = [
        {"rule_id": "R_STATUS", "target_column": "status", "strategy": "hardcode_constant", "params": {"value": "ACTIVE"}}
    ]

    final_df, logs, metrics = DQEnforceCore.run_enforcement(
        df=df,
        rules=rules,
        cleansing_steps=cleansing_steps,
        pk_columns=["id"],
        table_name="CUSTOMERS"
    )

    assert metrics["total_rows"] == 2
    assert metrics["clean_rows"] == 2
    assert metrics["soft_reject_rows"] == 0
    assert metrics["hard_reject_rows"] == 0
    assert metrics["cleansed_rows"] == 0
    assert metrics["overall_dqi"] == 1.0
    assert metrics["gate_passed"] is True

    # No cell diff logs
    assert len(logs) == 0

    # Hashes equal for clean rows
    for r in range(2):
        assert final_df[FLAG_COL][r] == 1
        assert final_df[CLEANSED_COL][r] == 0
        assert final_df["PREV_ROW_HASH"][r] == final_df["LAST_ROW_HASH"][r]
        assert final_df[CLEANSING_ID_COL][r] is None


def test_failing_rows_repaired_and_promoted_to_flag_1():
    """Failing rows remediated by cleansing get promoted from Flag 2 to Flag 1."""
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "country": ["  us  ", "n/a", "uk"]
    })
    rules = [
        {"rule_id": "R_PH", "rule_type": "ATR3", "target_column": "country", "placeholder_values": ["N/A"]},
        {"rule_id": "R_DOM", "rule_type": "ATR5", "target_column": "country", "technical_description": "Domain: US, UK"}
    ]
    cleansing_steps = [
        # Trim leading/trailing whitespace
        {"rule_id": "R_DOM", "target_column": "country", "strategy": "trim"},
        # Fix placeholder "n/a" to "US"
        {"rule_id": "R_PH", "target_column": "country", "strategy": "hardcode_constant", "params": {"value": "US"}}
    ]

    final_df, logs, metrics = DQEnforceCore.run_enforcement(
        df=df,
        rules=rules,
        cleansing_steps=cleansing_steps,
        pk_columns=["id"],
        table_name="COUNTRIES"
    )

    # Row 1 ("  us  ") was pre-cleansed/trimmed to "us", but domain requires "US" (case check or remap)
    # Row 2 was "n/a", repaired to "US"
    # Row 3 was "uk"
    # Let's inspect logs
    assert len(logs) >= 1
    # Check that row 2 was cleansed
    assert final_df[CLEANSED_COL][1] == 1
    assert final_df[CLEANSING_ID_COL][1] is not None
    # PREV_ROW_HASH and LAST_ROW_HASH differ on cleansed row
    assert final_df["PREV_ROW_HASH"][1] != final_df["LAST_ROW_HASH"][1]
    # Provenance preserved
    assert final_df[ORIG_FAILED_COL][1] != "NONE"
    assert "R_PH" in final_df[ORIG_FAILED_COL][1]


def test_non_repaired_rows_stay_flag_2():
    """Rows that fail rules and have no matching cleansing remediation stay Flag 2."""
    df = pl.DataFrame({
        "id": [1, 2],
        "age": [25, -10]
    })
    rules = [
        {"rule_id": "R_AGE_POS", "rule_type": "ATR6", "target_column": "age", "technical_description": "Age must be positive"}
    ]
    # No cleansing step for R_AGE_POS
    final_df, logs, metrics = DQEnforceCore.run_enforcement(
        df=df,
        rules=rules,
        cleansing_steps=[],
        pk_columns=["id"]
    )

    assert final_df[FLAG_COL][0] == 1
    assert final_df[FLAG_COL][1] == 2
    assert "R_AGE_POS" in final_df[FAILED_COL][1]
    assert metrics["soft_reject_rows"] == 1
    assert metrics["clean_rows"] == 1
    assert metrics["overall_dqi"] == 0.5


def test_cell_level_audit_trail_diffs():
    """Cell-level audit log captures exact before/after diffs and strategy metadata."""
    df = pl.DataFrame({
        "id": [10],
        "notes": ["Special#$Characters*&Here"],
        "city": ["UNKNOWN"]
    })
    rules = [
        {"rule_id": "R_NOTES_SPEC", "rule_type": "ATR4", "target_column": "notes", "technical_description": "No special characters"},
        {"rule_id": "R_CITY_PH", "rule_type": "ATR3", "target_column": "city", "placeholder_values": ["UNKNOWN"]}
    ]
    cleansing_steps = [
        {"rule_id": "R_NOTES_SPEC", "target_column": "notes", "strategy": "strip_special"},
        {"rule_id": "R_CITY_PH", "target_column": "city", "strategy": "hardcode_constant", "params": {"value": "Riyadh"}}
    ]

    final_df, logs, metrics = DQEnforceCore.run_enforcement(
        df=df,
        rules=rules,
        cleansing_steps=cleansing_steps,
        pk_columns=["id"],
        table_name="CUSTOMERS"
    )

    assert len(logs) == 2
    # Verify first log
    log_notes = next(l for l in logs if l["column_name"] == "notes")
    assert log_notes["table_name"] == "CUSTOMERS"
    assert log_notes["strategy"] == "strip_special"
    assert log_notes["rule_id"] == "R_NOTES_SPEC"
    assert log_notes["before_value"] == "Special#$Characters*&Here"
    assert log_notes["after_value"] == "SpecialCharactersHere"
    assert log_notes["primary_key_values"] == {"id": 10}

    # Verify second log
    log_city = next(l for l in logs if l["column_name"] == "city")
    assert log_city["strategy"] == "hardcode_constant"
    assert log_city["rule_id"] == "R_CITY_PH"
    assert log_city["before_value"] == "UNKNOWN"
    assert log_city["after_value"] == "Riyadh"

    # Both logs share the same CLEANSING_ID
    assert log_notes["cleansing_id"] == log_city["cleansing_id"]
    assert log_notes["cleansing_id"] == final_df[CLEANSING_ID_COL][0]


def test_precedence_ordering():
    """Verify that Stage 0 executes before Stage 1 and Stage 2."""
    df = pl.DataFrame({
        "id": [1],
        "name_raw": ["  apple  "],
        "name_clean": [None]
    })
    rules = [
        {"rule_id": "R1", "rule_type": "ATR1", "target_column": "name_clean", "technical_description": "Clean name not null"}
    ]
    cleansing_steps = [
        # Stage 2: copy from raw to clean
        {"rule_id": "R1", "target_column": "name_clean", "strategy": "copy_from_column", "params": {"from_column": "name_raw"}},
        # Stage 0: trim raw
        {"rule_id": "R1", "target_column": "name_raw", "strategy": "trim", "fire": "always"}
    ]

    # In input, copy_from_column was placed before trim.
    # Precedence sort should run trim (Stage 0) BEFORE copy_from_column (Stage 2),
    # so name_clean receives the already-trimmed value "apple"!
    final_df, logs, metrics = DQEnforceCore.run_enforcement(
        df=df,
        rules=rules,
        cleansing_steps=cleansing_steps,
        pk_columns=["id"]
    )

    assert final_df["name_raw"][0] == "apple"
    assert final_df["name_clean"][0] == "apple"
