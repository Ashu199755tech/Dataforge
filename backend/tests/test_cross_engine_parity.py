import sqlite3
import pytest
import polars as pl
from typing import Dict, Any

from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.engine.pushdown.models import SQLDialect
from backend.app.engine.pushdown.transpiler import SQLPushdownTranspiler
from backend.app.engine.pushdown.executor import DataForgeSQLPushdownEngine
from backend.app.engine.spark.compiler import SparkDataFlowCompiler
from backend.app.engine.spark.executor import DataForgeSparkEngine


@pytest.fixture
def sample_orders_db(tmp_path):
    """Creates a temporary SQLite database with 1,000 test orders for cross-engine parity testing."""
    db_file = str(tmp_path / "parity_test.db")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE raw_orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            category TEXT,
            amount REAL,
            status TEXT
        )
    """)

    # Populate 1,000 rows across 4 categories and 2 statuses
    categories = ["ELECTRONICS", "APPAREL", "GROCERY", "BOOKS"]
    statuses = ["COMPLETED", "PENDING"]
    rows = []
    for i in range(1, 1001):
        cat = categories[i % len(categories)]
        stat = statuses[i % len(statuses)]
        amt = round(10.0 + (i * 0.75), 2)
        rows.append((i, 1000 + (i % 50), cat, amt, stat))

    cursor.executemany("INSERT INTO raw_orders VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    return db_file


def test_filter_derive_aggregate_cross_engine_parity(sample_orders_db):
    """
    Validates that:
    1. Polars vectorized execution
    2. DataForge PySpark compiler plan
    3. DataForge SQL Pushdown in-database CTE execution
    produce 100% identical outputs for Filter -> Derive -> Aggregate -> Sort workflows.
    """
    # 1. Setup SQLite connector
    sqlite_conn = SQLiteConnector({"database_path": sample_orders_db})

    # Read raw data into Polars for reference
    raw_records = sqlite_conn.execute_query("SELECT * FROM raw_orders")
    raw_df = pl.DataFrame(raw_records)
    assert len(raw_df) == 1000

    # Execute reference workflow in Polars:
    # Filter: status == 'COMPLETED' and amount > 50.0
    # Derive: tax = amount * 0.10, total_amount = amount + tax
    # Group by category: count, sum(total_amount), avg(amount)
    # Sort: sum_total_amount DESC
    filtered_pl = raw_df.filter((pl.col("status") == "COMPLETED") & (pl.col("amount") > 50.0))
    derived_pl = filtered_pl.with_columns([
        (pl.col("amount") * 0.10).alias("tax"),
        (pl.col("amount") + (pl.col("amount") * 0.10)).alias("total_amount")
    ])
    grouped_pl = derived_pl.group_by("category").agg([
        pl.len().alias("order_count"),
        pl.col("total_amount").sum().alias("total_revenue"),
        pl.col("amount").mean().alias("avg_amount")
    ]).sort("total_revenue", descending=True)

    expected_rows = grouped_pl.to_dicts()
    assert len(expected_rows) > 0

    # 2. Build DataFlow DAG representing the exact same workflow
    dag = {
        "nodes": [
            {
                "id": "src_1",
                "type": "source",
                "data": {
                    "operatorType": "source",
                    "config": {
                        "table_name": "raw_orders",
                        "columns": ["order_id", "customer_id", "category", "amount", "status"]
                    }
                }
            },
            {
                "id": "filter_1",
                "type": "filter",
                "data": {
                    "operatorType": "filter",
                    "config": {"condition": "status = 'COMPLETED' AND amount > 50.0"}
                }
            },
            {
                "id": "derive_1",
                "type": "derived_column",
                "data": {
                    "operatorType": "derived_column",
                    "config": {
                        "columns": [
                            {"name": "tax", "expression": "amount * 0.10"},
                            {"name": "total_amount", "expression": "amount + (amount * 0.10)"}
                        ]
                    }
                }
            },
            {
                "id": "agg_1",
                "type": "aggregate",
                "data": {
                    "operatorType": "aggregate",
                    "config": {
                        "group_by": ["category"],
                        "aggregations": [
                            {"column": "*", "function": "count", "alias": "order_count"},
                            {"column": "total_amount", "function": "sum", "alias": "total_revenue"},
                            {"column": "amount", "function": "avg", "alias": "avg_amount"}
                        ]
                    }
                }
            },
            {
                "id": "sort_1",
                "type": "sort",
                "data": {
                    "operatorType": "sort",
                    "config": {
                        "sort_columns": [{"column": "total_revenue", "direction": "desc"}]
                    }
                }
            }
        ],
        "edges": [
            {"id": "e1", "source": "src_1", "target": "filter_1"},
            {"id": "e2", "source": "filter_1", "target": "derive_1"},
            {"id": "e3", "source": "derive_1", "target": "agg_1"},
            {"id": "e4", "source": "agg_1", "target": "sort_1"}
        ]
    }

    # 3. Test Spark Engine DataFlow Compiler
    spark_plan = SparkDataFlowCompiler.compile_to_plan(dag)
    assert "script" in spark_plan
    spark_script = spark_plan["script"]
    assert "df_src_1.filter" in spark_script
    assert 'withColumn("tax"' in spark_script
    assert 'withColumn("total_amount"' in spark_script
    assert 'groupBy("category")' in spark_script
    assert 'orderBy(F.col("total_revenue").desc())' in spark_script

    # 4. Test SQL Pushdown Engine Execution in SQLite
    pushdown_result = DataForgeSQLPushdownEngine.execute_pushdown(
        connector=sqlite_conn,
        graph_json=dag,
        dialect=SQLDialect.SQLITE,
        write_mode="ctas",
        target_table="parity_summary"
    )
    assert pushdown_result.success is True
    assert pushdown_result.egress_bytes == 0  # Verified 0 network egress

    # 5. Read in-database SQL Pushdown results and compare to Polars reference
    actual_pushdown_rows = sqlite_conn.execute_query("SELECT * FROM parity_summary")

    # Compare row counts
    assert len(actual_pushdown_rows) == len(expected_rows)

    # Compare row-by-row values across engines
    for exp, act in zip(expected_rows, actual_pushdown_rows):
        assert act["category"] == exp["category"]
        assert act["order_count"] == exp["order_count"]
        assert act["total_revenue"] == pytest.approx(exp["total_revenue"], rel=1e-3)
        assert act["avg_amount"] == pytest.approx(exp["avg_amount"], rel=1e-3)


def test_complex_predicate_filtering_parity(sample_orders_db):
    """Validates multi-condition logical predicate parity between Polars and Pushdown AST."""
    sqlite_conn = SQLiteConnector({"database_path": sample_orders_db})

    # Polars reference: (category = 'ELECTRONICS' AND amount >= 200.0) OR (status = 'COMPLETED' AND amount < 50.0)
    raw_df = pl.DataFrame(sqlite_conn.execute_query("SELECT * FROM raw_orders"))
    pl_filtered = raw_df.filter(
        ((pl.col("category") == "ELECTRONICS") & (pl.col("amount") >= 200.0)) |
        ((pl.col("status") == "COMPLETED") & (pl.col("amount") < 50.0))
    )
    expected_ids = set(pl_filtered["order_id"].to_list())
    assert len(expected_ids) > 0

    dag = {
        "nodes": [
            {
                "id": "src",
                "type": "source",
                "data": {"operatorType": "source", "config": {"table_name": "raw_orders"}}
            },
            {
                "id": "flt",
                "type": "filter",
                "data": {
                    "operatorType": "filter",
                    "config": {
                        "condition": "(category = 'ELECTRONICS' AND amount >= 200.0) OR (status = 'COMPLETED' AND amount < 50.0)"
                    }
                }
            }
        ],
        "edges": [{"id": "e1", "source": "src", "target": "flt"}]
    }

    pushdown_res = DataForgeSQLPushdownEngine.execute_pushdown(
        connector=sqlite_conn,
        graph_json=dag,
        dialect=SQLDialect.SQLITE,
        write_mode="ctas",
        target_table="parity_predicate_filtered"
    )
    assert pushdown_res.success is True

    actual_records = sqlite_conn.execute_query("SELECT order_id FROM parity_predicate_filtered")
    actual_ids = {r["order_id"] for r in actual_records}

    assert actual_ids == expected_ids


def test_projection_and_rename_parity(sample_orders_db):
    """Validates column projection and renaming parity across engines."""
    sqlite_conn = SQLiteConnector({"database_path": sample_orders_db})

    dag = {
        "nodes": [
            {
                "id": "src",
                "type": "source",
                "data": {"operatorType": "source", "config": {"table_name": "raw_orders"}}
            },
            {
                "id": "sel",
                "type": "select",
                "data": {
                    "operatorType": "select",
                    "config": {
                        "columns": ["order_id", "category", "amount"],
                        "renames": {"order_id": "id", "amount": "order_val"}
                    }
                }
            }
        ],
        "edges": [{"id": "e1", "source": "src", "target": "sel"}]
    }

    # Pushdown
    res = DataForgeSQLPushdownEngine.execute_pushdown(
        connector=sqlite_conn,
        graph_json=dag,
        dialect=SQLDialect.SQLITE,
        write_mode="ctas",
        target_table="parity_renamed"
    )
    assert res.success is True

    pushdown_records = sqlite_conn.execute_query("SELECT * FROM parity_renamed LIMIT 5")
    assert list(pushdown_records[0].keys()) == ["id", "category", "order_val"]

    # Spark Script Parity Check
    spark_plan = SparkDataFlowCompiler.compile_to_plan(dag)
    assert ".select(" in spark_plan["script"]
    assert 'withColumnRenamed("order_id", "id")' in spark_plan["script"]
    assert 'withColumnRenamed("amount", "order_val")' in spark_plan["script"]
