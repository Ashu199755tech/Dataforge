import time
import uuid
import re
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
import zoneinfo
from croniter import croniter
from sqlalchemy.orm import Session

from backend.app.models.trigger import Trigger, TriggerRun
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.models.connection import Connection
from backend.app.schemas.trigger import TriggerCreate, TriggerUpdate
from backend.app.core.security import decrypt_secret
from backend.app.connectors.factory import get_connector
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.execution.runner import PipelineRunner


class TriggerService:
    """
    Enterprise DataForge Trigger Execution Service:
    - Manual Trigger: on-demand parameterized dispatch
    - Schedule Trigger: timezone-aware cron and frequency recurrence with start/end bounds
    - Storage Event Trigger: event-driven detection for Azure Blob/ADLS, AWS S3, GCP GCS, Local
    - Tumbling Window Trigger: non-overlapping time slices, backfills, concurrency & prior window dependency
    - Pipeline Dependency Trigger: upstream status triggers with circular dependency prevention graph check
    """

    @classmethod
    def calculate_next_schedule_fire(
        cls,
        trigger_type: str,
        cron_expression: Optional[str],
        schedule_config: Optional[Dict[str, Any]],
        base_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Calculates next execution datetime from cron expression or schedule recurrence config in specific timezone."""
        cfg = schedule_config or {}
        tz_name = cfg.get("timezone") or "UTC"
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        base = base_time or datetime.now(timezone.utc)
        base_in_tz = base.astimezone(tz)

        # Start and end date bounds check
        start_time_raw = cfg.get("start_time")
        end_time_raw = cfg.get("end_time")

        start_time = None
        if start_time_raw:
            if isinstance(start_time_raw, str):
                start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            elif isinstance(start_time_raw, datetime):
                start_time = start_time_raw
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)

        end_time = None
        if end_time_raw:
            if isinstance(end_time_raw, str):
                end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
            elif isinstance(end_time_raw, datetime):
                end_time = end_time_raw
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

        # If base is before start_time, use start_time as base
        if start_time and base < start_time:
            base_in_tz = start_time.astimezone(tz)

        next_time: Optional[datetime] = None

        if cron_expression:
            iter_cron = croniter(cron_expression, base_in_tz)
            next_local = iter_cron.get_next(datetime)
            next_time = next_local.astimezone(timezone.utc)
        else:
            # Frequency-based schedule (Minute, Hour, Day, Week, Month)
            freq = (cfg.get("frequency") or "Hour").lower()
            interval = int(cfg.get("interval") or 1)
            if freq == "minute":
                next_time = base + timedelta(minutes=interval)
            elif freq == "hour":
                next_time = base + timedelta(hours=interval)
            elif freq == "day":
                next_time = base + timedelta(days=interval)
            elif freq == "week":
                next_time = base + timedelta(weeks=interval)
            else:
                next_time = base + timedelta(hours=interval)

        # Check if next_time exceeds end_time
        if end_time and next_time and next_time > end_time:
            return None

        return next_time

    @classmethod
    def calculate_tumbling_window_bounds(
        cls,
        window_config: Dict[str, Any],
        current_window_start: Optional[str] = None
    ) -> Tuple[datetime, datetime, datetime]:
        """
        Computes (window_start, window_end, fire_due_time).
        fire_due_time = window_end + delay_minutes.
        """
        freq = (window_config.get("frequency") or "Hour").lower()
        interval = int(window_config.get("interval") or 1)
        delay_min = int(window_config.get("delay_minutes") or 0)

        if current_window_start:
            if isinstance(current_window_start, str):
                w_start = datetime.fromisoformat(current_window_start.replace("Z", "+00:00"))
            else:
                w_start = current_window_start
        else:
            raw_start = window_config.get("start_time")
            if isinstance(raw_start, str):
                w_start = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            elif isinstance(raw_start, datetime):
                w_start = raw_start
            else:
                w_start = datetime.now(timezone.utc)

        if w_start.tzinfo is None:
            w_start = w_start.replace(tzinfo=timezone.utc)

        if freq == "minute":
            delta = timedelta(minutes=interval)
        elif freq == "hour":
            delta = timedelta(hours=interval)
        elif freq == "day":
            delta = timedelta(days=interval)
        else:
            delta = timedelta(hours=interval)

        w_end = w_start + delta
        fire_due = w_end + timedelta(minutes=delay_min)
        return w_start, w_end, fire_due

    @classmethod
    def detect_circular_dependency(
        cls,
        db: Session,
        current_trigger_id: Optional[str],
        upstream_pipeline_id: str,
        downstream_pipeline_ids: List[str]
    ) -> bool:
        """
        Detects whether adding an upstream -> downstream pipeline dependency introduces a circular cycle.
        Raises ValueError if a cycle is detected.
        """
        # Build dependency graph from all active pipeline_dependency triggers
        triggers = db.query(Trigger).filter(
            Trigger.is_active == True,
            Trigger.trigger_type == "pipeline_dependency"
        ).all()

        adj: Dict[str, Set[str]] = {}

        def add_edge(u: str, v: str):
            if u not in adj:
                adj[u] = set()
            adj[u].add(v)

        for t in triggers:
            if current_trigger_id and t.id == current_trigger_id:
                continue
            u_id = (t.pipeline_dependency_config or {}).get("upstream_pipeline_id")
            if not u_id:
                continue
            targets = []
            if t.pipeline_id:
                targets.append(t.pipeline_id)
            for p in (t.pipelines_to_run or []):
                p_id = p.get("pipeline_id") if isinstance(p, dict) else getattr(p, "pipeline_id", None)
                if p_id:
                    targets.append(p_id)
            for d in targets:
                add_edge(u_id, d)

        # Add candidate edges
        for d in downstream_pipeline_ids:
            add_edge(upstream_pipeline_id, d)

        # Run cycle detection using DFS
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycle_path: List[str] = []

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:] + [neighbor])
                    return True

            rec_stack.remove(node)
            path.pop()
            return False

        for node in list(adj.keys()):
            if node not in visited:
                if dfs(node, []):
                    cycle_str = " -> ".join(cycle_path)
                    raise ValueError(
                        f"Circular pipeline trigger dependency detected: [{cycle_str}]. "
                        "This configuration would cause an infinite trigger loop."
                    )

        return False

    @classmethod
    def create_trigger(cls, db: Session, trigger_in: TriggerCreate) -> Trigger:
        """Creates and initializes a new enterprise trigger."""
        targets = []
        if trigger_in.pipelines_to_run:
            for p in trigger_in.pipelines_to_run:
                p_dict = p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p)
                targets.append(p_dict)
        elif trigger_in.pipeline_id:
            pipe = db.query(Pipeline).filter(Pipeline.id == trigger_in.pipeline_id).first()
            if not pipe:
                raise ValueError(f"Target pipeline '{trigger_in.pipeline_id}' not found.")
            targets.append({
                "pipeline_id": trigger_in.pipeline_id,
                "pipeline_name": pipe.name,
                "parameters": trigger_in.parameters or {}
            })

        if not targets and not trigger_in.pipeline_id:
            raise ValueError("Trigger must target at least one pipeline.")

        # Resolve primary pipeline_id for backwards compatibility
        primary_pipe_id = trigger_in.pipeline_id or (targets[0]["pipeline_id"] if targets else None)

        ttype = trigger_in.trigger_type.lower()
        sched_cfg = trigger_in.schedule_config.model_dump(mode="json") if trigger_in.schedule_config else {}
        tumb_cfg = trigger_in.tumbling_window_config.model_dump(mode="json") if trigger_in.tumbling_window_config else {}
        stor_cfg = trigger_in.storage_event_config.model_dump(mode="json") if trigger_in.storage_event_config else {}
        pipe_dep_cfg = trigger_in.pipeline_dependency_config.model_dump(mode="json") if trigger_in.pipeline_dependency_config else {}

        next_fire = None
        window_state = {}

        if ttype in ("cron", "schedule") and trigger_in.is_active:
            try:
                next_fire = cls.calculate_next_schedule_fire(ttype, trigger_in.cron_expression, sched_cfg)
            except Exception as e:
                raise ValueError(f"Invalid cron or recurrence schedule: {str(e)}")

        elif ttype == "tumbling_window":
            if not tumb_cfg.get("start_time"):
                raise ValueError("Tumbling window trigger requires 'start_time'.")
            w_start, w_end, fire_due = cls.calculate_tumbling_window_bounds(tumb_cfg)
            window_state = {
                "current_window_start": w_start.isoformat(),
                "current_window_end": w_end.isoformat(),
                "processed_windows": []
            }
            if trigger_in.is_active:
                next_fire = fire_due

        elif ttype == "storage_event":
            conn_id = stor_cfg.get("connection_id")
            if not conn_id:
                raise ValueError("Storage event trigger requires 'connection_id'.")
            conn = db.query(Connection).filter(Connection.id == conn_id).first()
            if not conn:
                raise ValueError(f"Referenced storage connection '{conn_id}' not found.")
            window_state = {"seen_storage_events": {}}

        elif ttype == "pipeline_dependency":
            u_pipe_id = pipe_dep_cfg.get("upstream_pipeline_id")
            if not u_pipe_id:
                raise ValueError("Pipeline dependency trigger requires 'upstream_pipeline_id'.")
            u_pipe = db.query(Pipeline).filter(Pipeline.id == u_pipe_id).first()
            if not u_pipe:
                raise ValueError(f"Upstream pipeline '{u_pipe_id}' not found.")
            pipe_dep_cfg["upstream_pipeline_name"] = u_pipe.name

            # Check circular dependencies
            downstream_ids = [t["pipeline_id"] for t in targets if "pipeline_id" in t]
            cls.detect_circular_dependency(db, None, u_pipe_id, downstream_ids)
            window_state = {"seen_upstream_run_ids": []}

        trigger = Trigger(
            name=trigger_in.name,
            description=trigger_in.description,
            trigger_type=ttype,
            pipeline_id=primary_pipe_id,
            pipelines_to_run=targets,
            cron_expression=trigger_in.cron_expression,
            schedule_config=sched_cfg,
            tumbling_window_config=tumb_cfg,
            storage_event_config=stor_cfg,
            pipeline_dependency_config=pipe_dep_cfg,
            is_active=trigger_in.is_active,
            parameters=trigger_in.parameters or {},
            next_fire_time=next_fire,
            window_state=window_state
        )
        db.add(trigger)
        db.commit()
        db.refresh(trigger)
        return trigger

    @classmethod
    def update_trigger(cls, db: Session, trigger_id: str, trigger_in: TriggerUpdate) -> Trigger:
        """Updates trigger configuration with state recalculation and cycle validation."""
        trigger = db.query(Trigger).filter(Trigger.id == trigger_id).first()
        if not trigger:
            raise ValueError(f"Trigger '{trigger_id}' not found.")

        if trigger_in.name is not None:
            trigger.name = trigger_in.name
        if trigger_in.description is not None:
            trigger.description = trigger_in.description
        if trigger_in.trigger_type is not None:
            trigger.trigger_type = trigger_in.trigger_type.lower()
        if trigger_in.parameters is not None:
            trigger.parameters = trigger_in.parameters

        if trigger_in.pipelines_to_run is not None:
            trigger.pipelines_to_run = [
                p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p)
                for p in trigger_in.pipelines_to_run
            ]
            if trigger.pipelines_to_run:
                trigger.pipeline_id = trigger.pipelines_to_run[0].get("pipeline_id")
        elif trigger_in.pipeline_id is not None:
            trigger.pipeline_id = trigger_in.pipeline_id
            if not trigger.pipelines_to_run:
                pipe = db.query(Pipeline).filter(Pipeline.id == trigger_in.pipeline_id).first()
                trigger.pipelines_to_run = [{
                    "pipeline_id": trigger_in.pipeline_id,
                    "pipeline_name": pipe.name if pipe else trigger_in.pipeline_id,
                    "parameters": trigger.parameters or {}
                }]

        if trigger_in.cron_expression is not None:
            trigger.cron_expression = trigger_in.cron_expression
        if trigger_in.schedule_config is not None:
            trigger.schedule_config = (
                trigger_in.schedule_config.model_dump(mode="json")
                if hasattr(trigger_in.schedule_config, "model_dump")
                else dict(trigger_in.schedule_config)
            )
        if trigger_in.tumbling_window_config is not None:
            trigger.tumbling_window_config = (
                trigger_in.tumbling_window_config.model_dump(mode="json")
                if hasattr(trigger_in.tumbling_window_config, "model_dump")
                else dict(trigger_in.tumbling_window_config)
            )
        if trigger_in.storage_event_config is not None:
            trigger.storage_event_config = (
                trigger_in.storage_event_config.model_dump(mode="json")
                if hasattr(trigger_in.storage_event_config, "model_dump")
                else dict(trigger_in.storage_event_config)
            )
        if trigger_in.pipeline_dependency_config is not None:
            trigger.pipeline_dependency_config = (
                trigger_in.pipeline_dependency_config.model_dump(mode="json")
                if hasattr(trigger_in.pipeline_dependency_config, "model_dump")
                else dict(trigger_in.pipeline_dependency_config)
            )
            # Validate cycle check on update
            u_id = trigger.pipeline_dependency_config.get("upstream_pipeline_id")
            if u_id:
                downstream_ids = [t.get("pipeline_id") for t in (trigger.pipelines_to_run or []) if t.get("pipeline_id")]
                cls.detect_circular_dependency(db, trigger.id, u_id, downstream_ids)

        if trigger_in.is_active is not None:
            trigger.is_active = trigger_in.is_active

        # Recalculate next fire time
        if trigger.is_active:
            ttype = trigger.trigger_type.lower()
            if ttype in ("cron", "schedule"):
                trigger.next_fire_time = cls.calculate_next_schedule_fire(
                    ttype, trigger.cron_expression, trigger.schedule_config
                )
            elif ttype == "tumbling_window":
                curr_w_start = (trigger.window_state or {}).get("current_window_start")
                _, _, fire_due = cls.calculate_tumbling_window_bounds(trigger.tumbling_window_config, curr_w_start)
                trigger.next_fire_time = fire_due
        else:
            trigger.next_fire_time = None

        trigger.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(trigger)
        return trigger

    @classmethod
    def fire_trigger_now(
        cls,
        db: Session,
        trigger: Trigger,
        event_payload: Optional[Dict[str, Any]] = None,
        override_parameters: Optional[Dict[str, Any]] = None,
        run_status: str = "Succeeded"
    ) -> TriggerRun:
        """
        Executes a trigger dispatch across all associated pipelines.
        Records TriggerRun history and dispatches execution asynchronously.
        """
        now = datetime.now(timezone.utc)
        start_ts = time.time()
        payload = dict(event_payload or {})

        # Collect target pipelines
        targets = list(trigger.pipelines_to_run or [])
        if not targets and trigger.pipeline_id:
            targets = [{"pipeline_id": trigger.pipeline_id, "parameters": trigger.parameters or {}}]

        if not targets:
            raise ValueError(f"Trigger '{trigger.id}' has no target pipelines configured.")

        # Create TriggerRun record
        trigger_run = TriggerRun(
            trigger_id=trigger.id,
            run_status="Running",
            fired_at=now,
            event_payload=payload
        )
        db.add(trigger_run)
        db.commit()
        db.refresh(trigger_run)

        dispatched_runs = []

        try:
            for target in targets:
                pipe_id = target.get("pipeline_id")
                if not pipe_id:
                    continue

                # Merge parameters: trigger defaults + target parameters + event payload + overrides
                merged_params = {}
                if trigger.parameters:
                    merged_params.update(trigger.parameters)
                if target.get("parameters"):
                    merged_params.update(target["parameters"])
                if payload:
                    # Expose under triggerBody or top-level
                    merged_params["triggerBody"] = payload
                    for k, v in payload.items():
                        merged_params[f"trigger_{k}"] = v
                if override_parameters:
                    merged_params.update(override_parameters)

                pipeline_run = PipelineRun(
                    pipeline_id=pipe_id,
                    run_type=f"Trigger:{trigger.trigger_type}",
                    status="Pending",
                    parameters=merged_params,
                    started_at=now
                )
                db.add(pipeline_run)
                db.commit()
                db.refresh(pipeline_run)

                dispatched_runs.append({
                    "pipeline_id": pipe_id,
                    "pipeline_name": target.get("pipeline_name", pipe_id),
                    "pipeline_run_id": pipeline_run.id,
                    "status": "Pending"
                })

                # Dispatch background runner
                threading.Thread(
                    target=lambda r_id: PipelineRunner(r_id).execute_sync(),
                    args=(pipeline_run.id,),
                    daemon=True,
                    name=f"DataForge-Run-{pipeline_run.id[:8]}"
                ).start()

            trigger_run.run_status = run_status
            trigger_run.triggered_pipeline_runs = dispatched_runs
            trigger_run.completed_at = datetime.now(timezone.utc)
            trigger_run.duration_ms = int((time.time() - start_ts) * 1000)

            # Update trigger last fired and next fire time
            trigger.last_fired_at = now
            ttype = trigger.trigger_type.lower()
            if ttype in ("cron", "schedule") and trigger.is_active:
                trigger.next_fire_time = cls.calculate_next_schedule_fire(
                    ttype, trigger.cron_expression, trigger.schedule_config, now
                )

            db.commit()
            db.refresh(trigger_run)
            return trigger_run

        except Exception as e:
            trigger_run.run_status = "Failed"
            trigger_run.error_message = str(e)
            trigger_run.completed_at = datetime.now(timezone.utc)
            trigger_run.duration_ms = int((time.time() - start_ts) * 1000)
            db.commit()
            raise

    @classmethod
    def evaluate_tumbling_window_trigger(
        cls,
        db: Session,
        trigger: Trigger,
        now: Optional[datetime] = None
    ) -> Optional[TriggerRun]:
        """
        Evaluates a Tumbling Window trigger slice:
        - Respects delay_minutes
        - Enforces max_concurrency
        - Checks prior window dependency (window N requires window N-1 succeeded)
        - Advances window state and dispatches execution
        """
        cur_now = now or datetime.now(timezone.utc)
        cfg = trigger.tumbling_window_config or {}
        w_state = dict(trigger.window_state or {})

        curr_w_start_str = w_state.get("current_window_start")
        if not curr_w_start_str:
            curr_w_start_str = cfg.get("start_time")
            if isinstance(curr_w_start_str, datetime):
                curr_w_start_str = curr_w_start_str.isoformat()

        if not curr_w_start_str:
            return None

        w_start, w_end, fire_due = cls.calculate_tumbling_window_bounds(cfg, curr_w_start_str)

        # Check if window end has passed end_time
        end_time_raw = cfg.get("end_time")
        if end_time_raw:
            if isinstance(end_time_raw, str):
                end_time = datetime.fromisoformat(end_time_raw.replace("Z", "+00:00"))
            else:
                end_time = end_time_raw
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)
            if w_start >= end_time:
                trigger.is_active = False
                trigger.next_fire_time = None
                db.commit()
                return None

        # Check if due (fire_due <= cur_now)
        if cur_now < fire_due:
            trigger.next_fire_time = fire_due
            db.commit()
            return None

        # Concurrency limit check
        max_concurrency = int(cfg.get("max_concurrency") or 1)
        running_runs = db.query(TriggerRun).filter(
            TriggerRun.trigger_id == trigger.id,
            TriggerRun.run_status == "Running"
        ).count()
        if running_runs >= max_concurrency:
            return None

        # Prior window dependency check
        if cfg.get("depends_on_prior_window", True):
            last_run = db.query(TriggerRun).filter(
                TriggerRun.trigger_id == trigger.id
            ).order_by(TriggerRun.fired_at.desc()).first()
            if last_run and last_run.run_status not in ("Succeeded", "Running"):
                # Prior window failed or not succeeded; wait or retry
                return None

        # Prepare window event payload
        event_payload = {
            "windowStartTime": w_start.isoformat(),
            "windowEndTime": w_end.isoformat(),
            "windowFrequency": cfg.get("frequency", "Hour"),
            "windowInterval": cfg.get("interval", 1)
        }

        # Advance window state
        processed = list(w_state.get("processed_windows", []))
        processed.append({"start": w_start.isoformat(), "end": w_end.isoformat()})
        next_w_start = w_end
        _, next_w_end, next_fire_due = cls.calculate_tumbling_window_bounds(cfg, next_w_start.isoformat())

        w_state["current_window_start"] = next_w_start.isoformat()
        w_state["current_window_end"] = next_w_end.isoformat()
        w_state["processed_windows"] = processed[-50:]  # keep recent 50 windows
        trigger.window_state = w_state
        trigger.next_fire_time = next_fire_due
        db.commit()

        # Fire the trigger
        return cls.fire_trigger_now(db, trigger, event_payload=event_payload)

    @classmethod
    def evaluate_storage_event_trigger(
        cls,
        db: Session,
        trigger: Trigger
    ) -> List[TriggerRun]:
        """
        Polls storage connector for newly created or modified files matching prefix/suffix/regex.
        Deduplicates against seen storage events and dispatches pipeline runs.
        """
        cfg = trigger.storage_event_config or {}
        conn_id = cfg.get("connection_id")
        container = cfg.get("container")
        if not conn_id or not container:
            return []

        conn = db.query(Connection).filter(Connection.id == conn_id).first()
        if not conn:
            return []

        prefix = cfg.get("prefix", "")
        suffix = cfg.get("suffix", "")
        regex_pattern = cfg.get("blob_path_regex")
        compiled_regex = re.compile(regex_pattern) if regex_pattern else None
        ignore_empty = cfg.get("ignore_empty_blobs", True)

        try:
            decrypted_config = decrypt_secret(conn.config_encrypted)
            connector = get_connector(conn.connector_type, decrypted_config)
            if not isinstance(connector, BaseStorageConnector):
                return []

            files = connector.list_files(container=container, prefix=prefix, recursive=True)
        except Exception as e:
            print(f"[WARN] StorageEventTrigger '{trigger.id}' list_files failed: {e}")
            return []

        w_state = dict(trigger.window_state or {})
        seen_events: Dict[str, Any] = dict(w_state.get("seen_storage_events") or {})

        dispatched_runs: List[TriggerRun] = []
        newly_seen: Dict[str, Any] = {}

        for f in files:
            path = getattr(f, "path", None) or getattr(f, "name", "")
            size = getattr(f, "size_in_bytes", getattr(f, "size_bytes", getattr(f, "size", 0)))
            etag = getattr(f, "etag", None) or str(getattr(f, "last_modified", ""))

            # Filter suffix
            if suffix and not path.endswith(suffix):
                continue
            # Filter regex
            if compiled_regex and not compiled_regex.search(path):
                continue
            # Filter empty files if requested
            if ignore_empty and size == 0:
                continue

            event_key = f"{path}:{etag}"
            if event_key in seen_events:
                continue

            # New or modified file event detected!
            file_name = path.split("/")[-1] if "/" in path else path
            folder_path = "/".join(path.split("/")[:-1]) if "/" in path else ""

            event_payload = {
                "fileName": file_name,
                "folderPath": folder_path,
                "filePath": path,
                "container": container,
                "fileSize": size,
                "etag": etag,
                "eventType": "BlobCreated",
                "detectedAt": datetime.now(timezone.utc).isoformat()
            }

            try:
                run = cls.fire_trigger_now(db, trigger, event_payload=event_payload)
                dispatched_runs.append(run)
                seen_events[event_key] = {
                    "path": path,
                    "etag": etag,
                    "size": size,
                    "first_seen": datetime.now(timezone.utc).isoformat()
                }
                newly_seen[event_key] = True
            except Exception as fe:
                print(f"[ERROR] Failed to fire storage event trigger '{trigger.id}' for {path}: {fe}")

        if newly_seen:
            w_state["seen_storage_events"] = seen_events
            trigger.window_state = w_state
            db.commit()

        return dispatched_runs

    @classmethod
    def evaluate_pipeline_dependency_trigger(
        cls,
        db: Session,
        trigger: Trigger
    ) -> List[TriggerRun]:
        """
        Evaluates completion of upstream pipeline runs.
        Fires downstream pipeline(s) when upstream matches required status.
        """
        cfg = trigger.pipeline_dependency_config or {}
        u_id = cfg.get("upstream_pipeline_id")
        if not u_id:
            return []

        desired_statuses = [s.lower() for s in cfg.get("fire_on_status", ["Succeeded"])]
        w_state = dict(trigger.window_state or {})
        seen_runs: List[str] = list(w_state.get("seen_upstream_run_ids") or [])

        # Fetch recent completed runs of the upstream pipeline
        query = db.query(PipelineRun).filter(
            PipelineRun.pipeline_id == u_id,
            PipelineRun.status.in_(["Succeeded", "Failed", "Completed"])
        )
        if trigger.created_at:
            query = query.filter(PipelineRun.started_at >= trigger.created_at)
        recent_runs = query.order_by(PipelineRun.ended_at.desc(), PipelineRun.started_at.desc()).limit(20).all()

        dispatched = []

        for prun in recent_runs:
            if prun.id in seen_runs:
                continue

            # Check status match
            status_match = False
            curr_status = prun.status.lower()
            if "completed" in desired_statuses:
                status_match = True
            elif curr_status in desired_statuses:
                status_match = True

            seen_runs.append(prun.id)

            if status_match:
                event_payload = {
                    "upstreamPipelineId": prun.pipeline_id,
                    "upstreamRunId": prun.id,
                    "upstreamStatus": prun.status,
                    "upstreamStartedAt": prun.started_at.isoformat() if prun.started_at else None,
                    "upstreamCompletedAt": prun.ended_at.isoformat() if prun.ended_at else None
                }

                # Parameter forwarding
                forward_params = {}
                if cfg.get("forward_parameters", True) and prun.parameters:
                    forward_params = {f"upstream_{k}": v for k, v in prun.parameters.items()}

                try:
                    tr_run = cls.fire_trigger_now(
                        db,
                        trigger,
                        event_payload=event_payload,
                        override_parameters=forward_params
                    )
                    dispatched.append(tr_run)
                except Exception as fe:
                    print(f"[ERROR] Failed to fire pipeline dependency trigger {trigger.id}: {fe}")

        w_state["seen_upstream_run_ids"] = seen_runs[-100:]  # retain recent 100
        trigger.window_state = w_state
        db.commit()
        return dispatched

    @classmethod
    def evaluate_all_active_triggers(cls, db: Session):
        """
        Main execution hook invoked periodically by TriggerScheduler.
        Evaluates all active triggers across all 5 trigger types.
        """
        now = datetime.now(timezone.utc)
        active_triggers = db.query(Trigger).filter(Trigger.is_active == True).all()

        for t in active_triggers:
            ttype = t.trigger_type.lower()
            try:
                if ttype in ("cron", "schedule"):
                    if t.next_fire_time:
                        nft = t.next_fire_time
                        if nft.tzinfo is None:
                            nft = nft.replace(tzinfo=timezone.utc)
                        if nft <= now:
                            cls.fire_trigger_now(db, t)
                elif ttype == "tumbling_window":
                    cls.evaluate_tumbling_window_trigger(db, t, now)
                elif ttype == "storage_event":
                    cls.evaluate_storage_event_trigger(db, t)
                elif ttype == "pipeline_dependency":
                    cls.evaluate_pipeline_dependency_trigger(db, t)
            except Exception as e:
                print(f"[ERROR] Trigger evaluation exception for trigger '{t.id}' ({t.name}): {e}")
