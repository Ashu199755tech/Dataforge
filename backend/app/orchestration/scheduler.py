import time
import threading
from datetime import datetime, timezone
from typing import Optional
from croniter import croniter
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.pipeline import Trigger, Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.execution.runner import PipelineRunner


class TriggerScheduler:
    """
    Background daemon for recurring cron-based and time-based pipeline triggers.
    Continuously monitors active triggers and dispatches execution runs.
    """

    def __init__(self, poll_interval_seconds: int = 5):
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def calculate_next_fire(self, cron_expression: str, base_time: Optional[datetime] = None) -> datetime:
        """Calculates next execution datetime from cron expression."""
        base = base_time or datetime.now(timezone.utc)
        iter_cron = croniter(cron_expression, base)
        return iter_cron.get_next(datetime)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="DataFlow-Scheduler")
        self._thread.start()
        print("[INFO] DataFlow Trigger Scheduler started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        print("[INFO] DataFlow Trigger Scheduler stopped.")

    def _run_loop(self):
        while self._running:
            try:
                self.check_and_fire_triggers()
                self.check_runtimes_health()
            except Exception as e:
                print(f"[ERROR] Scheduler error: {str(e)}")
            time.sleep(self.poll_interval)

    def check_runtimes_health(self):
        db: Session = SessionLocal()
        try:
            from backend.app.services.runtime_manager import RuntimeManagerService
            RuntimeManagerService.check_offline_runtimes(db)
        except Exception as e:
            pass
        finally:
            db.close()

    def check_and_fire_triggers(self):
        db: Session = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            # Find all active triggers that are due to fire
            active_triggers = db.query(Trigger).filter(
                Trigger.is_active == True,
                Trigger.next_fire_time != None,
                Trigger.next_fire_time <= now
            ).all()

            for trigger in active_triggers:
                print(f"[INFO] Firing trigger '{trigger.name}' for pipeline '{trigger.pipeline_id}'")
                
                # Create pipeline run
                run = PipelineRun(
                    pipeline_id=trigger.pipeline_id,
                    run_type=f"Trigger:{trigger.trigger_type}",
                    status="Pending",
                    parameters=trigger.parameters or {},
                    started_at=datetime.now(timezone.utc)
                )
                db.add(run)
                db.commit()
                db.refresh(run)

                # Update trigger next fire time
                trigger.last_fired_at = now
                if trigger.cron_expression:
                    try:
                        trigger.next_fire_time = self.calculate_next_fire(trigger.cron_expression, now)
                    except Exception as ce:
                        print(f"[WARN] Invalid cron in trigger {trigger.id}: {str(ce)}")
                db.commit()

                # Dispatch execution asynchronously
                threading.Thread(
                    target=lambda r_id: PipelineRunner(r_id).execute_sync(),
                    args=(run.id,),
                    daemon=True
                ).start()
        finally:
            db.close()


scheduler = TriggerScheduler(poll_interval_seconds=3)
