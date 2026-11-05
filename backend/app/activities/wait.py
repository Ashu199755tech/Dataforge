import time
from backend.app.activities.base import BaseActivity, ActivityExecutionResult


class WaitActivity(BaseActivity):
    """
    Wait Activity: Pauses pipeline execution for a configurable duration in seconds.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        wait_seconds = int(config.get("wait_time_in_seconds", 1))

        self.log("INFO", f"Pausing pipeline execution for {wait_seconds} seconds...")
        time.sleep(wait_seconds)
        self.log("INFO", f"Wait completed.")

        return ActivityExecutionResult(
            status="Succeeded",
            metrics={"waited_seconds": wait_seconds}
        )
