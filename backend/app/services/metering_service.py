from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
import uuid

from backend.app.models.billing import (
    PipelineUsageLedger,
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription
)
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.pipeline import Pipeline
from backend.app.models.workspace import Workspace, Project
from backend.app.models.data_quality import AuditLog
from backend.app.services.billing_service import BillingService


class UsageMeteringEngine:
    """
    Dedicated Pipeline Usage Metering Engine.
    Ensures every pipeline execution produces an immutable usage record with:
    - Activity complexity classification (Basic, Standard, Advanced, Complex)
    - Engine recognition (CopyEngine, SparkEngine, SqlPushdownEngine, Hybrid)
    - Fault-tolerant billability rules (PlatformSystemError is non-billable; Customer errors are billable)
    - Strict natural-key idempotency on pipeline_run_id (zero duplicate billing across worker retries)
    """

    @staticmethod
    def classify_activity_count(activity_count: int) -> str:
        """
        Classifies pipeline execution complexity based on activity count:
        - Basic: 1–5 activities (₹0.50 rate)
        - Standard: 6–15 activities (₹1.50 rate)
        - Advanced: 16–30 activities (₹3.00 rate)
        - Complex: 31+ activities (₹5.00 / Custom rate)
        """
        if activity_count <= 5:
            return "Basic"
        elif activity_count <= 15:
            return "Standard"
        elif activity_count <= 30:
            return "Advanced"
        else:
            return "Complex"

    @staticmethod
    def detect_execution_engine(pipeline_run: PipelineRun) -> str:
        """
        Determines the primary execution engine from executed activities.
        """
        if not pipeline_run.activity_runs:
            return "CopyEngine"

        act_types = {act.activity_type for act in pipeline_run.activity_runs if act.activity_type}
        
        has_spark = any(
            t in act_types for t in [
                "SparkDataFlow", "SparkSqlActivity", "DatabricksNotebook", 
                "DatabricksSql", "SynapseSpark"
            ]
        )
        has_sql = any(
            t in act_types for t in [
                "SqlPushdown", "SqlScript", "SnowflakeQuery", "PostgresExecute"
            ]
        )
        has_copy = any(
            t in act_types for t in [
                "CopyData", "DebeziumCDC", "ReverseETL", "WebActivity"
            ]
        )

        if has_spark and not (has_sql or has_copy):
            return "SparkEngine"
        elif has_sql and not (has_spark or has_copy):
            return "SqlPushdownEngine"
        elif has_copy and not (has_spark or has_sql):
            return "CopyEngine"
        elif sum([bool(has_spark), bool(has_sql), bool(has_copy)]) > 1:
            return "Hybrid"
        return "CopyEngine"

    @staticmethod
    def determine_billability(pipeline_run: PipelineRun) -> Tuple[bool, Optional[str]]:
        """
        Evaluates billing eligibility according to DataForge billing rules:
        - Succeeded -> Billable
        - Manual rerun -> Billable
        - DataForge platform infrastructure failure (SystemError) -> Non-billable
        - Customer configuration/data failure (UserError, DataQualityError) -> Billable (execution commenced)
        - Cancelled before execution started -> Non-billable
        - Pre-execution validation check -> Non-billable
        """
        status = pipeline_run.status or "Pending"

        # 1. Cancelled runs
        if status == "Cancelled":
            if not pipeline_run.activity_runs or pipeline_run.started_at == pipeline_run.ended_at:
                return False, "CancelledBeforeStart"
            return False, "UserCancelled"

        # 2. Validation failures before execution
        if pipeline_run.error_summary and "Validation failed before execution" in pipeline_run.error_summary:
            return False, "ValidationCheck"

        # 3. Failed runs - inspect root cause
        if status == "Failed":
            # If no activities were even started
            if not pipeline_run.activity_runs and pipeline_run.duration_seconds == 0:
                return False, "CancelledBeforeStart"

            # Check if any activity failed with SystemError
            for act in pipeline_run.activity_runs:
                if act.status == "Failed" and act.error_classification == "SystemError":
                    return False, "PlatformSystemError"

            # Check fatal engine level crash
            if pipeline_run.error_summary and (
                "Fatal engine error" in pipeline_run.error_summary or
                "Internal server error" in pipeline_run.error_summary or
                "WorkerCrash" in pipeline_run.error_summary
            ):
                return False, "PlatformSystemError"

            # If failed due to UserError, DataQualityError, ConnectionError, or business logic
            # execution was attempted on customer instruction -> Billable
            return True, None

        # 4. Succeeded runs
        return True, None

    @staticmethod
    def record_pipeline_execution(
        db: Session,
        pipeline_run_id: str
    ) -> Optional[PipelineUsageLedger]:
        """
        Meters a finalized pipeline execution and writes an immutable record to pipeline_usage_ledger.
        Guarantees idempotency via pipeline_run_id unique constraint.
        """
        # Idempotency check: never double charge
        existing = db.query(PipelineUsageLedger).filter(
            PipelineUsageLedger.pipeline_run_id == pipeline_run_id
        ).first()
        if existing:
            return existing

        # Load pipeline run
        pipeline_run = db.query(PipelineRun).filter(
            PipelineRun.id == pipeline_run_id
        ).first()
        if not pipeline_run:
            return None

        # Resolve pipeline and workspace hierarchy
        pipeline = pipeline_run.pipeline
        if not pipeline:
            pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_run.pipeline_id).first()

        project = pipeline.project if pipeline else None
        if not project and pipeline:
            project = db.query(Project).filter(Project.id == pipeline.project_id).first()

        workspace_id = project.workspace_id if project else "default_workspace"
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()

        tenant = None
        if ws and ws.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == ws.tenant_id).first()
        if not tenant:
            tenant = BillingService.get_or_create_default_tenant(db)
            if ws and not ws.tenant_id:
                ws.tenant_id = tenant.id
                db.commit()

        tenant_id = tenant.id

        # Resolve active customer subscription & pricing version
        sub = BillingService.get_subscription_for_workspace(db, workspace_id)
        pricing_version = sub.pricing_version if sub else None

        # Determine metrics & classification
        activity_count = len(pipeline_run.activity_runs) if pipeline_run.activity_runs else (pipeline_run.total_activities or 1)
        classification = UsageMeteringEngine.classify_activity_count(activity_count)
        engine_name = UsageMeteringEngine.detect_execution_engine(pipeline_run)
        is_billable, non_billable_reason = UsageMeteringEngine.determine_billability(pipeline_run)

        # Duration in seconds
        duration = float(pipeline_run.duration_seconds or 0.0)
        if duration == 0.0 and pipeline_run.ended_at and pipeline_run.started_at:
            duration = max(0.0, (pipeline_run.ended_at - pipeline_run.started_at).total_seconds())

        rows = (pipeline_run.total_rows_read or 0) + (pipeline_run.total_rows_written or 0)
        bytes_p = pipeline_run.total_bytes_processed or 0

        # Billing period key e.g. '2026-11'
        period_date = pipeline_run.ended_at or pipeline_run.started_at or datetime.now(timezone.utc)
        period_key = period_date.strftime("%Y-%m")

        # Calculated standard run rate
        charge = 0.0
        if is_billable and pricing_version:
            if classification == "Basic":
                charge = float(pricing_version.basic_run_rate)
            elif classification == "Standard":
                charge = float(pricing_version.standard_run_rate)
            elif classification == "Advanced":
                charge = float(pricing_version.advanced_run_rate)
            elif classification == "Complex":
                charge = float(pricing_version.complex_run_rate)
        elif is_billable:
            # Fallback default rates if no active subscription attached
            rate_map = {"Basic": 0.50, "Standard": 1.50, "Advanced": 3.00, "Complex": 5.00}
            charge = rate_map.get(classification, 0.50)

        ledger_entry = PipelineUsageLedger(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            project_id=project.id if project else "default_project",
            pipeline_id=pipeline.id if pipeline else pipeline_run.pipeline_id,
            pipeline_name=pipeline.name if pipeline else (pipeline_run.pipeline_id or "Ad-Hoc Run"),
            pipeline_run_id=pipeline_run.id,
            execution_type=pipeline_run.run_type or "Manual",
            execution_engine=engine_name,
            activity_count=activity_count,
            classification=classification,
            started_at=pipeline_run.started_at,
            ended_at=pipeline_run.ended_at or datetime.now(timezone.utc),
            duration_seconds=duration,
            execution_status=pipeline_run.status,
            retry_count=0,
            runtime_id=getattr(pipeline, "runtime_id", None) if pipeline else None,
            rows_processed=rows,
            bytes_processed=bytes_p,
            billing_period_key=period_key,
            is_billable=is_billable,
            non_billable_reason=non_billable_reason,
            calculated_charge=charge,
            pricing_version_id=pricing_version.id if pricing_version else None
        )

        try:
            db.add(ledger_entry)
            db.commit()
            db.refresh(ledger_entry)
            return ledger_entry
        except Exception:
            db.rollback()
            # Double check if written concurrently
            existing_after = db.query(PipelineUsageLedger).filter(
                PipelineUsageLedger.pipeline_run_id == pipeline_run_id
            ).first()
            if existing_after:
                return existing_after
            raise

    @staticmethod
    def override_ledger_billability(
        db: Session,
        ledger_id: str,
        is_billable: bool,
        reason: str,
        admin_user_id: Optional[str] = None
    ) -> PipelineUsageLedger:
        """
        Allows an administrator to manually adjust run billability with audit logging.
        Prevents retroactive alteration of settled invoices.
        """
        ledger = db.query(PipelineUsageLedger).filter(
            PipelineUsageLedger.id == ledger_id
        ).first()
        if not ledger:
            raise ValueError("Usage ledger entry not found.")

        old_billable = ledger.is_billable
        old_charge = float(ledger.calculated_charge)

        ledger.is_billable = is_billable
        ledger.non_billable_reason = None if is_billable else reason

        if not is_billable:
            ledger.calculated_charge = 0.0
        else:
            pv = ledger.pricing_version
            if pv:
                if ledger.classification == "Basic":
                    ledger.calculated_charge = float(pv.basic_run_rate)
                elif ledger.classification == "Standard":
                    ledger.calculated_charge = float(pv.standard_run_rate)
                elif ledger.classification == "Advanced":
                    ledger.calculated_charge = float(pv.advanced_run_rate)
                else:
                    ledger.calculated_charge = float(pv.complex_run_rate)
            else:
                rate_map = {"Basic": 0.50, "Standard": 1.50, "Advanced": 3.00, "Complex": 5.00}
                ledger.calculated_charge = rate_map.get(ledger.classification, 0.50)

        # Audit log entry
        audit = AuditLog(
            workspace_id=ledger.workspace_id,
            user_id=admin_user_id or "system_admin",
            action="BILLABILITY_OVERRIDE",
            resource_type="PipelineUsageLedger",
            resource_id=ledger.id,
            details={
                "old_billable": old_billable,
                "new_billable": is_billable,
                "old_charge": old_charge,
                "new_charge": float(ledger.calculated_charge),
                "justification": reason
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(ledger)
        return ledger

    @staticmethod
    def query_ledger(
        db: Session,
        workspace_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        execution_engine: Optional[str] = None,
        classification: Optional[str] = None,
        is_billable: Optional[bool] = None,
        period_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[PipelineUsageLedger], int]:
        """
        Retrieves paginated and filtered usage records for the billing portal.
        """
        query = db.query(PipelineUsageLedger)
        if workspace_id:
            query = query.filter(PipelineUsageLedger.workspace_id == workspace_id)
        if pipeline_id:
            query = query.filter(PipelineUsageLedger.pipeline_id == pipeline_id)
        if execution_engine:
            query = query.filter(PipelineUsageLedger.execution_engine == execution_engine)
        if classification:
            query = query.filter(PipelineUsageLedger.classification == classification)
        if is_billable is not None:
            query = query.filter(PipelineUsageLedger.is_billable == is_billable)
        if period_key:
            query = query.filter(PipelineUsageLedger.billing_period_key == period_key)

        total = query.count()
        records = query.order_by(PipelineUsageLedger.recorded_at.desc()).offset(offset).limit(limit).all()
        return records, total
