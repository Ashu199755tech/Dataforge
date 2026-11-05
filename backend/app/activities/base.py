from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.app.models.execution import ActivityRun, ExecutionLog


class ActivityExecutionContext(BaseModel):
    pipeline_run_id: str
    activity_id: str
    activity_name: str
    activity_type: str
    config: Dict[str, Any]
    pipeline_parameters: Dict[str, Any] = {}
    pipeline_variables: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class ActivityExecutionResult(BaseModel):
    status: str  # Succeeded, Failed, Skipped
    rows_read: int = 0
    rows_written: int = 0
    bytes_processed: int = 0
    error_message: Optional[str] = None
    output_variables: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}

    @property
    def outputs(self) -> Dict[str, Any]:
        return self.output_variables


class BaseActivity(ABC):
    """
    Abstract base class for all DataFlow activities.
    """

    def __init__(self, context: ActivityExecutionContext, db_session: Optional[Session] = None):
        self.context = context
        self.db = db_session
        self.activity_run_id: Optional[str] = None

    def log(self, level: str, message: str):
        """Persists structured activity log to the database."""
        timestamp = datetime.now(timezone.utc)
        print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] [{self.context.activity_name}] {message}")
        if self.activity_run_id:
            log_entry = ExecutionLog(
                activity_run_id=self.activity_run_id,
                level=level.upper(),
                message=message,
                timestamp=timestamp
            )
            self.db.add(log_entry)
            self.db.commit()

    @abstractmethod
    def execute(self) -> ActivityExecutionResult:
        """Executes the activity logic."""
        pass
