import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SparkJobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SparkSessionConfig(BaseModel):
    """Configuration parameters for configuring and tuning an Apache Spark session."""
    app_name: str = "DataForgeSparkEngine"
    master: str = "local[*]"
    executor_memory: str = "2g"
    driver_memory: str = "2g"
    executor_cores: int = 2
    shuffle_partitions: int = 200
    warehouse_dir: Optional[str] = None
    log_level: str = "WARN"
    extra_configs: Dict[str, str] = Field(default_factory=dict)
    enable_hive_support: bool = False


class SparkEnvironmentInfo(BaseModel):
    """Diagnostic environment metadata for Apache Spark and PySpark capabilities."""
    is_available: bool
    pyspark_installed: bool
    pyspark_version: Optional[str] = None
    java_installed: bool
    java_version: Optional[str] = None
    spark_home: Optional[str] = None
    diagnostic_message: str


class SparkJobSpec(BaseModel):
    """Specification for executing a Spark batch job or script."""
    job_id: str
    job_type: str = "DATAFLOW"  # DATAFLOW, SCRIPT, SQL
    script_path: Optional[str] = None
    script_content: Optional[str] = None
    entrypoint: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    pyfiles: List[str] = Field(default_factory=list)
    jars: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    session_config: SparkSessionConfig = Field(default_factory=SparkSessionConfig)


class SparkExecutionResult(BaseModel):
    """Comprehensive execution summary returned by DataForge Spark Engine."""
    success: bool
    status: SparkJobStatus
    engine: str = "spark"  # "spark" or "spark-fallback-vectorized"
    total_rows_read: int = 0
    total_rows_written: int = 0
    duration_seconds: float = 0.0
    stage_metrics: Dict[str, Any] = Field(default_factory=dict)
    sink_metrics: Dict[str, Any] = Field(default_factory=dict)
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    generated_script: Optional[str] = None
    error_message: Optional[str] = None
    cancelled: bool = False
