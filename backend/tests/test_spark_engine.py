import os
import time
import shutil
import tempfile
import polars as pl
from backend.app.engine.copy.models import CancellationToken
from backend.app.engine.spark.models import (
    SparkSessionConfig,
    SparkJobSpec,
    SparkJobStatus,
    SparkExecutionResult
)
from backend.app.engine.spark.session import (
    SparkSessionManager,
    SparkUnavailableException
)
from backend.app.engine.spark.compiler import SparkDataFlowCompiler
from backend.app.engine.spark.executor import DataForgeSparkEngine


def test_spark_environment_detection():
    info = SparkSessionManager.check_environment()
    assert isinstance(info.java_installed, bool)
    assert isinstance(info.pyspark_installed, bool)
    assert info.diagnostic_message is not None
    # Java is installed on this Linux environment
    assert info.java_installed is True
    assert "21." in (info.java_version or "")


def test_spark_session_config_validation():
    cfg = SparkSessionConfig(
        app_name="TestETL",
        master="spark://cluster-master:7077",
        executor_memory="4g",
        driver_memory="2g",
        executor_cores=4,
        shuffle_partitions=100,
        extra_configs={"spark.sql.adaptive.enabled": "true"}
    )
    assert cfg.app_name == "TestETL"
    assert cfg.master == "spark://cluster-master:7077"
    assert cfg.shuffle_partitions == 100
    assert cfg.extra_configs["spark.sql.adaptive.enabled"] == "true"


def test_spark_compiler_dataflow_to_pyspark_script():
    graph = {
        "nodes": [
            {
                "id": "src_orders",
                "type": "source",
                "data": {
                    "operatorType": "source",
                    "config": {"format": "parquet", "path": "s3a://data-lake/raw/orders.parquet"}
                }
            },
            {
                "id": "filter_active",
                "type": "filter",
                "data": {
                    "operatorType": "filter",
                    "config": {"condition": "status = 'ACTIVE' AND amount > 0"}
                }
            },
            {
                "id": "select_cols",
                "type": "select",
                "data": {
                    "operatorType": "select",
                    "config": {
                        "columns": ["order_id", "customer_id", "amount", "region"],
                        "renames": {"amount": "order_amount"}
                    }
                }
            },
            {
                "id": "derive_tax",
                "type": "derived_column",
                "data": {
                    "operatorType": "derived_column",
                    "config": {"column_name": "tax_amount", "expression": "order_amount * 0.08"}
                }
            },
            {
                "id": "agg_region",
                "type": "aggregate",
                "data": {
                    "operatorType": "aggregate",
                    "config": {
                        "group_by": ["region"],
                        "aggregates": [
                            {"column": "order_amount", "function": "sum", "alias": "total_sales"},
                            {"column": "order_id", "function": "count", "alias": "total_orders"}
                        ]
                    }
                }
            },
            {
                "id": "window_rank",
                "type": "window",
                "data": {
                    "operatorType": "window",
                    "config": {
                        "order_by": ["total_sales"],
                        "target_column": "sales_rank",
                        "function": "dense_rank"
                    }
                }
            },
            {
                "id": "sink_lake",
                "type": "sink",
                "data": {
                    "operatorType": "sink",
                    "config": {"format": "parquet", "path": "s3a://data-lake/gold/regional_sales", "mode": "overwrite"}
                }
            }
        ],
        "edges": [
            {"source": "src_orders", "target": "filter_active"},
            {"source": "filter_active", "target": "select_cols"},
            {"source": "select_cols", "target": "derive_tax"},
            {"source": "derive_tax", "target": "agg_region"},
            {"source": "agg_region", "target": "window_rank"},
            {"source": "window_rank", "target": "sink_lake"}
        ]
    }

    script = SparkDataFlowCompiler.compile_to_script(graph, app_name="RegionalSalesPipeline")
    assert "SparkSession.builder.appName(\"RegionalSalesPipeline\")" in script
    assert "spark.read.format(\"parquet\").load(\"s3a://data-lake/raw/orders.parquet\")" in script
    assert "filter(\"status = 'ACTIVE' AND amount > 0\")" in script
    assert ".select(\"order_id\", \"customer_id\", \"amount\", \"region\")" in script
    assert ".withColumnRenamed(\"amount\", \"order_amount\")" in script
    assert ".withColumn(\"tax_amount\", F.expr(\"order_amount * 0.08\"))" in script
    assert ".groupBy(\"region\").agg(" in script
    assert 'F.sum("order_amount").alias("total_sales")' in script
    assert "Window.orderBy(\"total_sales\")" in script
    assert 'F.dense_rank().over(' in script
    assert '.write.format("parquet").mode("overwrite").save("s3a://data-lake/gold/regional_sales")' in script
    assert "spark.stop()" in script


def test_spark_compiler_join_and_union():
    graph = {
        "nodes": [
            {"id": "src_a", "type": "source", "data": {"operatorType": "source", "config": {"format": "csv", "path": "a.csv"}}},
            {"id": "src_b", "type": "source", "data": {"operatorType": "source", "config": {"format": "csv", "path": "b.csv"}}},
            {"id": "join_ab", "type": "join", "data": {"operatorType": "join", "config": {"join_type": "left", "left_keys": ["id"], "right_keys": ["id"]}}},
            {"id": "sink_c", "type": "sink", "data": {"operatorType": "sink", "config": {"format": "parquet", "path": "out.parquet"}}}
        ],
        "edges": [
            {"source": "src_a", "target": "join_ab"},
            {"source": "src_b", "target": "join_ab"},
            {"source": "join_ab", "target": "sink_c"}
        ]
    }
    script = SparkDataFlowCompiler.compile_to_script(graph)
    assert 'join(df_src_b, on=["id"], how="left")' in script


def test_spark_compiler_topological_cycle_detection():
    cyclic_graph = {
        "nodes": [
            {"id": "node_1", "type": "filter", "data": {"operatorType": "filter", "config": {}}},
            {"id": "node_2", "type": "filter", "data": {"operatorType": "filter", "config": {}}}
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_1"}
        ]
    }
    try:
        SparkDataFlowCompiler.compile_to_script(cyclic_graph)
        assert False, "Should have raised ValueError on cycle"
    except ValueError as e:
        assert "Cycle detected" in str(e)


def test_spark_engine_fallback_execution():
    tmp_dir = tempfile.mkdtemp()
    src_file = os.path.join(tmp_dir, "input.parquet")
    sink_file = os.path.join(tmp_dir, "output.parquet")

    try:
        # Create 500 rows input dataset using Polars
        df = pl.DataFrame({
            "id": list(range(1, 501)),
            "category": ["A" if i % 2 == 0 else "B" for i in range(1, 501)],
            "value": [float(i * 1.5) for i in range(1, 501)]
        })
        df.write_parquet(src_file)

        # Build dataflow graph
        graph = {
            "nodes": [
                {
                    "id": "src",
                    "type": "source",
                    "data": {
                        "operatorType": "source",
                        "config": {"source_type": "file", "format": "parquet", "file_path": src_file}
                    }
                },
                {
                    "id": "filter_cat",
                    "type": "filter",
                    "data": {
                        "operatorType": "filter",
                        "config": {"condition": "category = 'A'"}
                    }
                },
                {
                    "id": "sink",
                    "type": "sink",
                    "data": {
                        "operatorType": "sink",
                        "config": {"sink_type": "file", "format": "parquet", "file_path": sink_file}
                    }
                }
            ],
            "edges": [
                {"source": "src", "target": "filter_cat"},
                {"source": "filter_cat", "target": "sink"}
            ]
        }

        res = DataForgeSparkEngine.execute_dataflow(
            graph_json=graph,
            fallback_to_polars=True
        )

        assert res.success is True
        assert res.status == SparkJobStatus.COMPLETED
        assert res.engine == "spark-fallback-vectorized"
        assert res.total_rows_read == 500
        assert res.total_rows_written == 250
        assert res.generated_script is not None
        assert "spark.read" in res.generated_script

        # Verify output file exists and has 250 rows
        out_df = pl.read_parquet(sink_file)
        assert len(out_df) == 250
        assert set(out_df["category"].to_list()) == {"A"}

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_spark_engine_unavailable_without_fallback():
    # When fallback_to_polars is False and PySpark is absent
    graph = {
        "nodes": [
            {"id": "src", "type": "source", "data": {"operatorType": "source", "config": {}}}
        ],
        "edges": []
    }
    res = DataForgeSparkEngine.execute_dataflow(graph, fallback_to_polars=False)
    # PySpark is not installed in the test venv, so it must return clean diagnostic failure
    assert res.success is False
    assert res.status == SparkJobStatus.FAILED
    assert "PySpark" in (res.error_message or "")


def test_spark_submit_missing_binary():
    spec = SparkJobSpec(
        job_id="test_sub",
        script_content="print('Hello Spark')",
        session_config=SparkSessionConfig(master="local[1]")
    )
    res = DataForgeSparkEngine.execute_spark_submit(spec)
    assert res.success is False
    assert "spark-submit" in (res.error_message or "")


def test_spark_cancellation():
    token = CancellationToken()
    token.cancel("User aborted dataflow")

    graph = {
        "nodes": [
            {"id": "src", "type": "source", "data": {"operatorType": "source", "config": {}}}
        ],
        "edges": []
    }
    try:
        DataForgeSparkEngine.execute_dataflow(graph, cancellation_token=token)
        assert False, "Should have raised InterruptedError on cancellation"
    except InterruptedError:
        pass


def test_spark_empirical_benchmark():
    """
    Empirical benchmark testing DataForge Spark compilation throughput
    and vectorized execution on a 10,000 row transformation pipeline.
    """
    tmp_dir = tempfile.mkdtemp()
    src_file = os.path.join(tmp_dir, "bench_orders.parquet")
    sink_file = os.path.join(tmp_dir, "bench_gold.parquet")

    try:
        # Generate 10,000 records
        df = pl.DataFrame({
            "order_id": list(range(1, 10001)),
            "region": [f"Region-{i % 5}" for i in range(1, 10001)],
            "status": ["COMPLETED" if i % 3 != 0 else "CANCELLED" for i in range(1, 10001)],
            "amount": [float((i * 7) % 500 + 10) for i in range(1, 10001)]
        })
        df.write_parquet(src_file)

        graph = {
            "nodes": [
                {
                    "id": "src",
                    "type": "source",
                    "data": {"operatorType": "source", "config": {"source_type": "file", "format": "parquet", "file_path": src_file}}
                },
                {
                    "id": "filter_completed",
                    "type": "filter",
                    "data": {"operatorType": "filter", "config": {"condition": "status = 'COMPLETED'"}}
                },
                {
                    "id": "sink",
                    "type": "sink",
                    "data": {"operatorType": "sink", "config": {"sink_type": "file", "format": "parquet", "file_path": sink_file}}
                }
            ],
            "edges": [
                {"source": "src", "target": "filter_completed"},
                {"source": "filter_completed", "target": "sink"}
            ]
        }

        # Measure AST Compilation time
        start_compile = time.time()
        plan = SparkDataFlowCompiler.compile_to_plan(graph)
        compile_duration = time.time() - start_compile

        # Measure Execution time
        start_exec = time.time()
        res = DataForgeSparkEngine.execute_dataflow(graph, fallback_to_polars=True)
        exec_duration = time.time() - start_exec

        assert res.success is True
        assert res.total_rows_read == 10000
        # 2/3 of 10000 = ~6667 completed
        assert res.total_rows_written > 6000

        rows_per_sec = 10000 / max(0.001, exec_duration)

        print(f"\n[BENCHMARK] Spark AST Compilation Time: {compile_duration * 1000:.2f} ms")
        print(f"[BENCHMARK] Spark Engine Execution Time (10k rows): {exec_duration:.4f} s ({rows_per_sec:.0f} rows/s)")
        print(f"[BENCHMARK] Compiled PySpark Script Lines: {len(plan['script'].splitlines())}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
