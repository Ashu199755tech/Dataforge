from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class ComputeJobHandle(BaseModel):
    job_id: str
    run_id: str
    status: str  # PENDING, RUNNING, TERMINATED, SKIPPED, FAILED
    start_time_epoch_ms: Optional[int] = None
    end_time_epoch_ms: Optional[int] = None
    result_state: Optional[str] = None  # SUCCESS, FAILED, TIMEDOUT, CANCELED
    error_message: Optional[str] = None
    output_data: Dict[str, Any] = {}


class BaseComputeProvider(ABC):
    """
    Standard vendor-independent compute abstraction interface.
    Enables pluggable integration with external distributed clusters (Databricks, Spark, Synapse).
    """

    @abstractmethod
    def submit_job(self, job_spec: Dict[str, Any]) -> ComputeJobHandle:
        """Submits a remote workload or notebook to the compute cluster."""
        pass

    @abstractmethod
    def get_job_status(self, job_id: str, run_id: str) -> ComputeJobHandle:
        """Polls execution status of the remote workload."""
        pass

    @abstractmethod
    def cancel_job(self, job_id: str, run_id: str) -> bool:
        """Terminates a running remote job."""
        pass
