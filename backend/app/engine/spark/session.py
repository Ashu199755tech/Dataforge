import os
import sys
import shutil
import subprocess
from typing import Optional, Dict, Any

from backend.app.engine.spark.models import (
    SparkSessionConfig,
    SparkEnvironmentInfo
)


class SparkUnavailableException(Exception):
    """Raised when an operation requires an active PySpark session but PySpark is not available."""
    pass


class SparkSessionManager:
    """
    Manages Apache Spark session lifecycle, cluster configuration,
    and runtime environment detection.
    """

    _active_session = None

    @classmethod
    def check_environment(cls) -> SparkEnvironmentInfo:
        """
        Inspects host OS and Python environment for Java and PySpark capability.
        """
        # 1. Check Java
        java_installed = bool(shutil.which("java"))
        java_version = None
        if java_installed:
            try:
                proc = subprocess.run(
                    ["java", "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=5
                )
                first_line = proc.stdout.split("\n")[0] if proc.stdout else ""
                java_version = first_line.strip()
            except Exception:
                java_version = "Unknown (detected)"

        # 2. Check PySpark
        pyspark_installed = False
        pyspark_version = None
        try:
            import pyspark
            pyspark_installed = True
            pyspark_version = getattr(pyspark, "__version__", "unknown")
        except ImportError:
            pyspark_installed = False

        spark_home = os.environ.get("SPARK_HOME")

        is_available = java_installed and pyspark_installed

        if is_available:
            msg = f"Apache Spark runtime is ready (PySpark {pyspark_version}, Java: {java_version})."
        elif not java_installed and not pyspark_installed:
            msg = "Neither Java JRE nor PySpark is installed. Spark engine is disabled."
        elif not java_installed:
            msg = "PySpark is installed, but Java JRE was not found on PATH. Spark requires Java 11 or 17/21."
        else:
            msg = f"Java is installed ({java_version}), but PySpark is not installed in the current virtual environment."

        return SparkEnvironmentInfo(
            is_available=is_available,
            pyspark_installed=pyspark_installed,
            pyspark_version=pyspark_version,
            java_installed=java_installed,
            java_version=java_version,
            spark_home=spark_home,
            diagnostic_message=msg
        )

    @classmethod
    def is_spark_available(cls) -> bool:
        """Quick boolean probe for Spark engine readiness."""
        info = cls.check_environment()
        return info.is_available

    @classmethod
    def get_session(cls, config: Optional[SparkSessionConfig] = None) -> Any:
        """
        Returns an active PySpark SparkSession configured according to config specifications.
        Raises SparkUnavailableException if environment lacks required runtime binaries.
        """
        env_info = cls.check_environment()
        if not env_info.is_available:
            raise SparkUnavailableException(env_info.diagnostic_message)

        if cls._active_session is not None:
            return cls._active_session

        import pyspark
        from pyspark.sql import SparkSession

        cfg = config or SparkSessionConfig()
        builder = SparkSession.builder.appName(cfg.app_name).master(cfg.master)

        builder = builder.config("spark.executor.memory", cfg.executor_memory)
        builder = builder.config("spark.driver.memory", cfg.driver_memory)
        builder = builder.config("spark.executor.cores", str(cfg.executor_cores))
        builder = builder.config("spark.sql.shuffle.partitions", str(cfg.shuffle_partitions))

        if cfg.warehouse_dir:
            builder = builder.config("spark.sql.warehouse.dir", cfg.warehouse_dir)

        if cfg.enable_hive_support:
            builder = builder.enableHiveSupport()

        for k, v in cfg.extra_configs.items():
            builder = builder.config(k, str(v))

        cls._active_session = builder.getOrCreate()
        if cfg.log_level:
            cls._active_session.sparkContext.setLogLevel(cfg.log_level)

        return cls._active_session

    @classmethod
    def stop_session(cls) -> None:
        """Stops and cleans up the active PySpark session."""
        if cls._active_session is not None:
            try:
                cls._active_session.stop()
            except Exception:
                pass
            cls._active_session = None
