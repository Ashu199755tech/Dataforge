import uuid
import time
import json
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.models.execution import ActivityRun, ExecutionLog
from backend.app.core.security import encrypt_secret, decrypt_secret
from backend.app.schemas.runtime import (
    RuntimeCreate,
    RuntimeUpdate,
    AgentRegisterRequest,
    AgentHeartbeatRequest,
    RuntimeTaskItem,
    RuntimeTaskStatusUpdate
)


class RuntimeManagerService:
    """
    Central service for managing DataForge Integration Runtimes:
    - Cloud, Self-Hosted (Linux/Windows), and Local Development Runtimes
    - Secure registration key exchange and bearer token session management
    - Heartbeat tracking, capacity limits, and online/offline detection
    - Task dispatch queueing, status tracking, and failover recovery
    """

    HEARTBEAT_TIMEOUT_SECONDS = 60

    @classmethod
    def generate_registration_key(cls) -> Tuple[str, str, str]:
        """
        Generates a 32-byte cryptographically secure registration key.
        Returns: (raw_key, encrypted_key, key_hash)
        """
        raw_key = f"df-ir-{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        encrypted_key = encrypt_secret({"key": raw_key})
        return raw_key, encrypted_key, key_hash

    @classmethod
    def hash_token(cls, token: str) -> str:
        """Computes SHA-256 hash of a bearer auth token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def create_runtime(cls, db: Session, runtime_in: RuntimeCreate) -> Tuple[IntegrationRuntime, Optional[str]]:
        """
        Creates an Integration Runtime. For SelfHosted runtimes, generates a registration key.
        """
        rtype = runtime_in.runtime_type
        raw_key = None
        enc_key = None
        key_hash = None

        if rtype == "SelfHosted":
            raw_key, enc_key, key_hash = cls.generate_registration_key()
            initial_status = "Registering"
        else:
            initial_status = "Online"

        runtime = IntegrationRuntime(
            project_id=runtime_in.project_id,
            name=runtime_in.name,
            description=runtime_in.description,
            runtime_type=rtype,
            status=initial_status,
            is_enabled=True,
            registration_key_encrypted=enc_key,
            registration_key_hash=key_hash,
            concurrency_limit=runtime_in.concurrency_limit,
            config=runtime_in.config,
            last_heartbeat_at=datetime.now(timezone.utc) if rtype != "SelfHosted" else None
        )
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return runtime, raw_key

    @classmethod
    def regenerate_key(cls, db: Session, runtime_id: str) -> Tuple[IntegrationRuntime, str]:
        """Regenerates the registration key for a SelfHosted runtime, invalidating existing sessions."""
        runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
        if not runtime:
            raise ValueError(f"Integration Runtime '{runtime_id}' not found.")

        raw_key, enc_key, key_hash = cls.generate_registration_key()
        runtime.registration_key_encrypted = enc_key
        runtime.registration_key_hash = key_hash
        runtime.auth_token_hash = None
        runtime.status = "Registering"
        runtime.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(runtime)
        return runtime, raw_key

    @classmethod
    def get_registration_key(cls, runtime: IntegrationRuntime) -> Optional[str]:
        """Decrypts and returns the registration key if available."""
        if not runtime.registration_key_encrypted:
            return None
        try:
            decrypted = decrypt_secret(runtime.registration_key_encrypted)
            return decrypted.get("key")
        except Exception:
            return None

    @classmethod
    def register_agent(cls, db: Session, req: AgentRegisterRequest) -> Tuple[IntegrationRuntime, str]:
        """
        Authenticates an agent using its registration key, generates a bearer session token,
        records agent host specs, and marks the runtime Online.
        """
        key_hash = hashlib.sha256(req.registration_key.strip().encode("utf-8")).hexdigest()
        runtime = db.query(IntegrationRuntime).filter(
            IntegrationRuntime.registration_key_hash == key_hash,
            IntegrationRuntime.is_enabled == True
        ).first()

        if not runtime:
            raise PermissionError("Invalid or revoked registration key.")

        # Generate secure bearer session token
        session_token = f"df-session-{secrets.token_urlsafe(40)}"
        runtime.auth_token_hash = cls.hash_token(session_token)
        runtime.agent_version = req.agent_version
        runtime.agent_os = req.agent_os
        runtime.host_name = req.host_name
        runtime.ip_address = req.ip_address
        runtime.cpu_cores = req.cpu_cores
        runtime.memory_total_bytes = req.memory_total_bytes
        runtime.status = "Online"
        runtime.last_heartbeat_at = datetime.now(timezone.utc)
        runtime.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(runtime)
        return runtime, session_token

    @classmethod
    def authenticate_agent(cls, db: Session, auth_token: str) -> IntegrationRuntime:
        """Authenticates agent request via bearer session token."""
        token_hash = cls.hash_token(auth_token.strip())
        runtime = db.query(IntegrationRuntime).filter(
            IntegrationRuntime.auth_token_hash == token_hash,
            IntegrationRuntime.is_enabled == True
        ).first()

        if not runtime:
            raise PermissionError("Invalid or expired agent session token.")
        return runtime

    @classmethod
    def process_heartbeat(cls, db: Session, runtime: IntegrationRuntime, req: AgentHeartbeatRequest) -> int:
        """
        Updates live telemetry from agent heartbeat and returns pending tasks count.
        """
        now = datetime.now(timezone.utc)
        runtime.cpu_usage_pct = req.cpu_usage_pct
        runtime.memory_used_bytes = req.memory_used_bytes
        runtime.active_task_count = req.active_task_count
        runtime.status = "Online"
        runtime.last_heartbeat_at = now
        runtime.updated_at = now
        db.commit()

        # Count pending tasks
        pending_count = db.query(RuntimeTask).filter(
            RuntimeTask.runtime_id == runtime.id,
            RuntimeTask.status == "Queued"
        ).count()
        return pending_count

    @classmethod
    def check_offline_runtimes(cls, db: Session) -> int:
        """
        Detects runtimes whose heartbeat is older than timeout and transitions them to Offline.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=cls.HEARTBEAT_TIMEOUT_SECONDS)
        stale_runtimes = db.query(IntegrationRuntime).filter(
            IntegrationRuntime.runtime_type == "SelfHosted",
            IntegrationRuntime.status == "Online",
            (IntegrationRuntime.last_heartbeat_at == None) | (IntegrationRuntime.last_heartbeat_at < cutoff)
        ).all()

        count = len(stale_runtimes)
        for rt in stale_runtimes:
            rt.status = "Offline"
            rt.updated_at = datetime.now(timezone.utc)
        if count > 0:
            db.commit()
        return count

    @classmethod
    def enqueue_task(
        cls,
        db: Session,
        runtime_id: str,
        task_type: str,
        payload: Dict[str, Any],
        pipeline_run_id: Optional[str] = None,
        activity_run_id: Optional[str] = None,
        timeout_seconds: int = 3600
    ) -> RuntimeTask:
        """
        Enqueues an execution task for dispatch to the assigned Integration Runtime.
        Payload is encrypted to protect sensitive connection parameters.
        """
        runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
        if not runtime:
            raise ValueError(f"Integration Runtime '{runtime_id}' not found.")

        task = RuntimeTask(
            runtime_id=runtime.id,
            pipeline_run_id=pipeline_run_id,
            activity_run_id=activity_run_id,
            task_type=task_type,
            status="Queued",
            task_payload_encrypted=encrypt_secret(payload),
            timeout_seconds=timeout_seconds,
            task_result={}
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @classmethod
    def poll_next_task(cls, db: Session, runtime: IntegrationRuntime) -> Optional[RuntimeTaskItem]:
        """
        Fetches next queued task for this runtime agent and marks it Dispatched.
        """
        if runtime.active_task_count >= runtime.concurrency_limit:
            return None

        query = db.query(RuntimeTask).filter(
            RuntimeTask.runtime_id == runtime.id,
            RuntimeTask.status == "Queued"
        ).order_by(RuntimeTask.queued_at.asc())

        try:
            task = query.with_for_update(skip_locked=True).first()
        except Exception:
            task = query.first()

        if not task:
            return None

        now = datetime.now(timezone.utc)
        task.status = "Dispatched"
        task.dispatched_at = now
        task.heartbeat_at = now
        runtime.active_task_count += 1
        db.commit()

        # Decrypt payload for execution
        payload = decrypt_secret(task.task_payload_encrypted)

        return RuntimeTaskItem(
            task_id=task.id,
            task_type=task.task_type,
            pipeline_run_id=task.pipeline_run_id,
            activity_run_id=task.activity_run_id,
            activity_name=payload.get("activity_name") or task.task_type,
            payload=payload,
            timeout_seconds=task.timeout_seconds
        )

    @classmethod
    def update_task_status(
        cls,
        db: Session,
        runtime: IntegrationRuntime,
        task_id: str,
        update: RuntimeTaskStatusUpdate
    ) -> RuntimeTask:
        """
        Updates task execution progress or terminal state from agent.
        Synchronizes status back to ActivityRun.
        """
        task = db.query(RuntimeTask).filter(
            RuntimeTask.id == task_id,
            RuntimeTask.runtime_id == runtime.id
        ).first()

        if not task:
            raise ValueError(f"Task '{task_id}' not found for runtime '{runtime.id}'.")

        now = datetime.now(timezone.utc)
        task.heartbeat_at = now
        task.status = update.status
        task.task_result = {
            "status": update.status,
            "rows_read": update.rows_read,
            "rows_written": update.rows_written,
            "bytes_processed": update.bytes_processed,
            "error_message": update.error_message,
            "metrics": update.metrics,
            "output_variables": update.output_variables
        }

        if update.status == "Running" and not task.started_at:
            task.started_at = now
        elif update.status in ("Completed", "Failed", "Cancelled"):
            task.completed_at = now
            runtime.active_task_count = max(0, runtime.active_task_count - 1)

        # Synchronize with ActivityRun if associated
        if task.activity_run_id:
            act_run = db.query(ActivityRun).filter(ActivityRun.id == task.activity_run_id).first()
            if act_run:
                if update.status == "Running":
                    act_run.status = "Running"
                    if not act_run.started_at:
                        act_run.started_at = now
                elif update.status == "Completed":
                    act_run.status = "Succeeded"
                    act_run.ended_at = now
                    act_run.rows_read = update.rows_read or 0
                    act_run.rows_written = update.rows_written or 0
                    act_run.bytes_processed = update.bytes_processed or 0
                    act_run.output_variables = update.output_variables
                elif update.status == "Failed":
                    act_run.status = "Failed"
                    act_run.ended_at = now
                    act_run.error_message = update.error_message

        db.commit()
        db.refresh(task)
        return task
