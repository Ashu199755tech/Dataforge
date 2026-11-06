import os
import sys
import time
import shutil
import tempfile
import subprocess
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.app.engine.copy.models import CancellationToken
from backend.app.engine.spark.models import (
    SparkSessionConfig,
    SparkJobSpec,
    SparkJobStatus,
    SparkExecutionResult
)
from backend.app.engine.spark.session import SparkSessionManager, SparkUnavailableException
from backend.app.engine.spark.compiler import SparkDataFlowCompiler
from backend.app.dataflow.engine import DataFlowEngine


class DataForgeSparkEngine:
    """
    DataForge Standalone Spark Execution Engine.
    Executes distributed processing workloads using Apache Spark and PySpark.
    Provides automated script compilation, cluster job submission, and seamless
    vectorized fallback when PySpark runtime is not present.
    """

    @classmethod
    def execute_dataflow(
        cls,
        graph_json: Dict[str, Any],
        config: Optional[SparkSessionConfig] = None,
        fallback_to_polars: bool = True,
        db_session: Optional[Session] = None,
        cancellation_token: Optional[CancellationToken] = None
    ) -> SparkExecutionResult:
        """
        Executes a Visual Data Flow transformation graph.
        If PySpark is available, executes natively across Spark workers.
        If PySpark is unavailable and fallback_to_polars is True, transparently executes
        via the high-performance Polars vectorized engine while preserving full Spark script compilation.
        """
        start_time = time.time()
        token = cancellation_token or CancellationToken()

        # Compile DAG to PySpark script representation
        plan = SparkDataFlowCompiler.compile_to_plan(graph_json)
        script = plan.get("script")

        token.raise_if_cancelled()

        # Check PySpark environment availability
        env_info = SparkSessionManager.check_environment()

        if env_info.is_available:
            return cls._execute_native_spark(
                graph_json=graph_json,
                config=config,
                script=script,
                start_time=start_time,
                token=token
            )
        elif fallback_to_polars:
            # Fallback to high-performance local vectorized engine
            return cls._execute_vectorized_fallback(
                graph_json=graph_json,
                script=script,
                db_session=db_session,
                start_time=start_time,
                token=token
            )
        else:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.FAILED,
                engine="spark",
                duration_seconds=round(time.time() - start_time, 3),
                generated_script=script,
                error_message=env_info.diagnostic_message
            )

    @classmethod
    def _execute_native_spark(
        cls,
        graph_json: Dict[str, Any],
        config: Optional[SparkSessionConfig],
        script: str,
        start_time: float,
        token: CancellationToken
    ) -> SparkExecutionResult:
        try:
            spark = SparkSessionManager.get_session(config)
            job_group_id = f"dataforge_job_{int(time.time() * 1000)}"
            spark.sparkContext.setJobGroup(job_group_id, "DataForge DataFlow Execution")

            token.raise_if_cancelled()

            # Execute compiled script in isolated scope with active spark session
            exec_globals = {
                "spark": spark,
                "sys": sys,
                "os": os
            }
            exec_locals: Dict[str, Any] = {}

            # Execute the generated script logic
            exec(script, exec_globals, exec_locals)

            # If script defined main(), invoke it
            if "main" in exec_locals:
                exec_locals["main"]()

            duration = max(0.001, time.time() - start_time)

            return SparkExecutionResult(
                success=True,
                status=SparkJobStatus.COMPLETED,
                engine="spark",
                duration_seconds=round(duration, 3),
                generated_script=script,
                stage_metrics={"job_group_id": job_group_id, "spark_version": spark.version}
            )
        except InterruptedError as ie:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.CANCELLED,
                engine="spark",
                duration_seconds=round(time.time() - start_time, 3),
                generated_script=script,
                cancelled=True,
                error_message=str(ie)
            )
        except Exception as e:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.FAILED,
                engine="spark",
                duration_seconds=round(time.time() - start_time, 3),
                generated_script=script,
                error_message=str(e)
            )

    @classmethod
    def _execute_vectorized_fallback(
        cls,
        graph_json: Dict[str, Any],
        script: str,
        db_session: Optional[Session],
        start_time: float,
        token: CancellationToken
    ) -> SparkExecutionResult:
        token.raise_if_cancelled()
        dataflow_engine = DataFlowEngine(db_session=db_session)
        result = dataflow_engine.execute_graph(graph_json)

        duration = max(0.001, time.time() - start_time)
        is_success = (result.status == "Succeeded")

        return SparkExecutionResult(
            success=is_success,
            status=SparkJobStatus.COMPLETED if is_success else SparkJobStatus.FAILED,
            engine="spark-fallback-vectorized",
            total_rows_read=result.total_rows_read,
            total_rows_written=result.total_rows_written,
            duration_seconds=round(duration, 3),
            sink_metrics=result.sink_metrics,
            node_outputs=result.node_outputs,
            generated_script=script,
            error_message=result.error_message
        )

    @classmethod
    def execute_spark_submit(
        cls,
        job_spec: SparkJobSpec,
        cancellation_token: Optional[CancellationToken] = None
    ) -> SparkExecutionResult:
        """
        Submits a PySpark or Java/Scala Spark job to a cluster via spark-submit CLI.
        """
        start_time = time.time()
        token = cancellation_token or CancellationToken()

        spark_submit_bin = shutil.which("spark-submit")
        if not spark_submit_bin:
            spark_home = os.environ.get("SPARK_HOME")
            if spark_home:
                candidate = os.path.join(spark_home, "bin", "spark-submit")
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    spark_submit_bin = candidate

        if not spark_submit_bin:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.FAILED,
                engine="spark-submit",
                duration_seconds=0.0,
                error_message="spark-submit executable was not found on PATH or under SPARK_HOME."
            )

        # Write script to temporary file if provided inline
        tmp_script_path = None
        target_script = job_spec.script_path
        if not target_script and job_spec.script_content:
            tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
            tmp.write(job_spec.script_content)
            tmp.flush()
            tmp.close()
            tmp_script_path = tmp.name
            target_script = tmp_script_path

        if not target_script:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.FAILED,
                engine="spark-submit",
                duration_seconds=0.0,
                error_message="Neither script_path nor script_content was provided in SparkJobSpec."
            )

        cmd = [
            spark_submit_bin,
            "--master", job_spec.session_config.master,
            "--name", job_spec.session_config.app_name,
            "--executor-memory", job_spec.session_config.executor_memory,
            "--driver-memory", job_spec.session_config.driver_memory
        ]

        if job_spec.jars:
            cmd.extend(["--jars", ",".join(job_spec.jars)])
        if job_spec.pyfiles:
            cmd.extend(["--py-files", ",".join(job_spec.pyfiles)])

        cmd.append(target_script)
        cmd.extend(job_spec.args)

        env = dict(os.environ)
        env.update(job_spec.env_vars)

        try:
            token.raise_if_cancelled()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            # Monitor process with cooperative cancellation
            while proc.poll() is None:
                if token.is_cancelled:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise InterruptedError(f"Job cancelled: {token.reason}")
                time.sleep(0.5)

            stdout, stderr = proc.communicate()
            duration = max(0.001, time.time() - start_time)

            if proc.returncode == 0:
                return SparkExecutionResult(
                    success=True,
                    status=SparkJobStatus.COMPLETED,
                    engine="spark-submit",
                    duration_seconds=round(duration, 3),
                    stage_metrics={"stdout_snippet": stdout[-500:] if stdout else ""}
                )
            else:
                return SparkExecutionResult(
                    success=False,
                    status=SparkJobStatus.FAILED,
                    engine="spark-submit",
                    duration_seconds=round(duration, 3),
                    error_message=f"spark-submit exited with code {proc.returncode}: {stderr[-1000:] if stderr else ''}"
                )

        except InterruptedError as ie:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.CANCELLED,
                engine="spark-submit",
                duration_seconds=round(time.time() - start_time, 3),
                cancelled=True,
                error_message=str(ie)
            )
        except Exception as ex:
            return SparkExecutionResult(
                success=False,
                status=SparkJobStatus.FAILED,
                engine="spark-submit",
                duration_seconds=round(time.time() - start_time, 3),
                error_message=str(ex)
            )
        finally:
            if tmp_script_path and os.path.exists(tmp_script_path):
                try:
                    os.remove(tmp_script_path)
                except Exception:
                    pass
