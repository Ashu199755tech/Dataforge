"""
DataForge – Budget Management, Threshold Alerts & Notification System.
Provides workspace/project spending limits, run count caps, 50%/75%/90%/100% threshold alerts,
and optional hard stop execution enforcement.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.billing import (
    Tenant,
    BudgetConfiguration,
    BudgetAlertRecord,
    PipelineUsageLedger,
    UsageAggregation
)
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.monitoring.alert_engine import AlertEngine
from backend.app.schemas.billing import (
    BudgetConfigurationCreate,
    BudgetConfigurationUpdate,
    BudgetAlertRecordResponse,
    BudgetStatusResponse,
    BudgetEvaluationResult
)


class BudgetService:
    """
    Enterprise Budget & Spending Threshold Service.
    """

    @classmethod
    def create_budget(
        cls,
        db: Session,
        tenant_id: str,
        budget_in: BudgetConfigurationCreate
    ) -> BudgetConfiguration:
        """Creates a new budget limit configuration."""
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found.")

        # Ensure valid thresholds
        thresholds = budget_in.threshold_percents or [50, 75, 90, 100]
        thresholds = sorted(list(set(thresholds)))

        budget = BudgetConfiguration(
            tenant_id=tenant_id,
            workspace_id=budget_in.workspace_id,
            project_id=budget_in.project_id,
            name=budget_in.name,
            period_type=budget_in.period_type,
            monthly_limit_amount=Decimal(str(round(budget_in.monthly_limit_amount, 2))),
            monthly_run_limit=budget_in.monthly_run_limit,
            enforce_hard_limit=budget_in.enforce_hard_limit,
            alert_recipients=budget_in.alert_recipients or [{"channel": "email", "target": tenant.billing_email}],
            threshold_percents=thresholds,
            is_active=budget_in.is_active
        )
        db.add(budget)
        db.commit()
        db.refresh(budget)
        return budget

    @classmethod
    def update_budget(
        cls,
        db: Session,
        budget_id: str,
        budget_update: BudgetConfigurationUpdate
    ) -> BudgetConfiguration:
        """Updates an existing budget limit configuration."""
        budget = db.query(BudgetConfiguration).filter(BudgetConfiguration.id == budget_id).first()
        if not budget:
            raise ValueError(f"Budget {budget_id} not found.")

        if budget_update.name is not None:
            budget.name = budget_update.name
        if budget_update.monthly_limit_amount is not None:
            budget.monthly_limit_amount = Decimal(str(round(budget_update.monthly_limit_amount, 2)))
        if budget_update.monthly_run_limit is not None:
            budget.monthly_run_limit = budget_update.monthly_run_limit
        if budget_update.enforce_hard_limit is not None:
            budget.enforce_hard_limit = budget_update.enforce_hard_limit
        if budget_update.alert_recipients is not None:
            budget.alert_recipients = budget_update.alert_recipients
        if budget_update.threshold_percents is not None:
            budget.threshold_percents = sorted(list(set(budget_update.threshold_percents)))
        if budget_update.is_active is not None:
            budget.is_active = budget_update.is_active

        db.commit()
        db.refresh(budget)
        return budget

    @classmethod
    def list_budgets(
        cls,
        db: Session,
        tenant_id: str,
        workspace_id: Optional[str] = None
    ) -> List[BudgetConfiguration]:
        """Lists all budgets for a tenant with optional workspace filter."""
        query = db.query(BudgetConfiguration).filter(BudgetConfiguration.tenant_id == tenant_id)
        if workspace_id:
            query = query.filter(
                (BudgetConfiguration.workspace_id == workspace_id) | (BudgetConfiguration.workspace_id == None)
            )
        return query.order_by(BudgetConfiguration.created_at.desc()).all()

    @classmethod
    def get_budget_by_id(cls, db: Session, budget_id: str) -> Optional[BudgetConfiguration]:
        return db.query(BudgetConfiguration).filter(BudgetConfiguration.id == budget_id).first()

    @classmethod
    def delete_budget(cls, db: Session, budget_id: str) -> bool:
        budget = db.query(BudgetConfiguration).filter(BudgetConfiguration.id == budget_id).first()
        if not budget:
            return False
        db.delete(budget)
        db.commit()
        return True

    @classmethod
    def get_budget_status(
        cls,
        db: Session,
        budget_id: str,
        period_key: Optional[str] = None
    ) -> BudgetStatusResponse:
        """
        Calculates real-time consumption metrics and threshold status for a budget.
        """
        budget = cls.get_budget_by_id(db, budget_id)
        if not budget:
            raise ValueError(f"Budget {budget_id} not found.")

        if not period_key:
            period_key = datetime.now(timezone.utc).strftime("%Y-%m")

        # Query consumption in ledger for this period
        ledger_query = db.query(
            func.coalesce(func.sum(PipelineUsageLedger.calculated_charge), 0),
            func.count(PipelineUsageLedger.id)
        ).filter(
            PipelineUsageLedger.tenant_id == budget.tenant_id,
            PipelineUsageLedger.billing_period_key == period_key,
            PipelineUsageLedger.is_billable == True
        )

        if budget.workspace_id:
            ledger_query = ledger_query.filter(PipelineUsageLedger.workspace_id == budget.workspace_id)
        if budget.project_id:
            ledger_query = ledger_query.filter(PipelineUsageLedger.project_id == budget.project_id)

        spend_sum, run_count = ledger_query.first()
        current_spend = float(spend_sum or 0.0)
        current_runs = int(run_count or 0)

        # Calculate utilization percentages
        spend_limit = float(budget.monthly_limit_amount)
        run_limit = int(budget.monthly_run_limit)

        spend_util = (current_spend / spend_limit * 100.0) if spend_limit > 0 else 0.0
        run_util = (current_runs / run_limit * 100.0) if run_limit > 0 else 0.0

        is_breached = budget.enforce_hard_limit and ((spend_limit > 0 and spend_util >= 100.0) or (run_limit > 0 and run_util >= 100.0))

        recent_alerts = [
            BudgetAlertRecordResponse.model_validate(a) for a in budget.alerts[:10]
        ]

        return BudgetStatusResponse(
            id=budget.id,
            tenant_id=budget.tenant_id,
            workspace_id=budget.workspace_id,
            project_id=budget.project_id,
            name=budget.name,
            period_type=budget.period_type,
            monthly_limit_amount=spend_limit,
            monthly_run_limit=run_limit,
            enforce_hard_limit=budget.enforce_hard_limit,
            alert_recipients=budget.alert_recipients or [],
            threshold_percents=budget.threshold_percents or [50, 75, 90, 100],
            is_active=budget.is_active,
            current_spend=round(current_spend, 2),
            current_runs=current_runs,
            spend_utilization_pct=round(spend_util, 1),
            run_utilization_pct=round(run_util, 1),
            is_hard_limit_breached=is_breached,
            recent_alerts=recent_alerts,
            created_at=budget.created_at,
            updated_at=budget.updated_at
        )

    @classmethod
    def evaluate_budgets_for_tenant(
        cls,
        db: Session,
        tenant_id: str,
        period_key: Optional[str] = None
    ) -> BudgetEvaluationResult:
        """
        Evaluates all active budgets against current period consumption.
        Dispatches threshold alerts (50%, 75%, 90%, 100%) across configured channels
        with deduplication to prevent spamming.
        """
        if not period_key:
            period_key = datetime.now(timezone.utc).strftime("%Y-%m")

        budgets = db.query(BudgetConfiguration).filter(
            BudgetConfiguration.tenant_id == tenant_id,
            BudgetConfiguration.is_active == True
        ).all()

        dispatched_alerts: List[BudgetAlertRecordResponse] = []

        for b in budgets:
            status = cls.get_budget_status(db, b.id, period_key)
            max_util = max(status.spend_utilization_pct, status.run_utilization_pct)

            for threshold in sorted(b.threshold_percents):
                if max_util >= threshold:
                    # Check deduplication: Was an alert for this threshold already triggered in this period?
                    existing = db.query(BudgetAlertRecord).filter(
                        BudgetAlertRecord.budget_id == b.id,
                        BudgetAlertRecord.period_key == period_key,
                        BudgetAlertRecord.threshold_percent == threshold
                    ).first()

                    if not existing:
                        # Construct alert message
                        title = f"DataForge Budget Alert: [{threshold}% Limit] {b.name}"
                        severity = "Critical" if threshold >= 90 else "Warning"
                        msg = (
                            f"Budget threshold of {threshold}% reached for '{b.name}' in billing period {period_key}.\n"
                            f"• Current Spend: INR {status.current_spend:,.2f} / Limit: INR {status.monthly_limit_amount:,.2f} ({status.spend_utilization_pct}%)\n"
                            f"• Current Runs: {status.current_runs:,} / Limit: {status.monthly_run_limit:,} ({status.run_utilization_pct}%)\n"
                            f"• Hard Stop Enforcement: {'Active (Executions Blocked)' if status.is_hard_limit_breached else 'Warn-Only (Unblocked)'}."
                        )

                        for recipient in (b.alert_recipients or [{"channel": "email", "target": "ops@dataforge.internal"}]):
                            channel = recipient.get("channel", "email")
                            target = recipient.get("target", "admin@dataforge.internal")

                            record = BudgetAlertRecord(
                                budget_id=b.id,
                                period_key=period_key,
                                threshold_percent=threshold,
                                current_spend=Decimal(str(status.current_spend)),
                                budget_limit=Decimal(str(status.monthly_limit_amount)),
                                current_runs=status.current_runs,
                                run_limit=status.monthly_run_limit,
                                notification_channel=channel,
                                dispatched_to=target,
                                status="Delivered",
                                triggered_at=datetime.now(timezone.utc)
                            )
                            db.add(record)
                            db.flush()

                            # Dispatch through AlertEngine infrastructure
                            temp_rule = AlertRule(
                                name=title,
                                target_type="Global",
                                condition_type="BudgetThreshold",
                                action_type=channel if channel in ("email", "slack", "teams", "webhook") else "log",
                                action_config={"recipients": [target], "webhook_url": target, "url": target}
                            )
                            temp_event = AlertEvent(
                                alert_rule_id="budget_engine",
                                title=title,
                                severity=severity,
                                message=msg,
                                payload={"budget_id": b.id, "threshold": threshold, "utilization": max_util}
                            )
                            try:
                                AlertEngine.dispatch_action(temp_rule, temp_event)
                            except Exception as e:
                                record.status = "Delivered"

                            dispatched_alerts.append(BudgetAlertRecordResponse.model_validate(record))

        db.commit()
        return BudgetEvaluationResult(
            period_key=period_key,
            evaluated_budgets=len(budgets),
            triggered_alerts_count=len(dispatched_alerts),
            alerts_dispatched=dispatched_alerts
        )

    @classmethod
    def check_execution_allowed(cls, db: Session, workspace_id: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether a pipeline run is allowed to proceed or should be hard-stopped
        due to an active budget hard limit at 100% consumption.
        Warn-only budgets will never block pipeline execution.
        """
        if not workspace_id:
            return True, None

        active_hard_budgets = db.query(BudgetConfiguration).filter(
            BudgetConfiguration.workspace_id == workspace_id,
            BudgetConfiguration.enforce_hard_limit == True,
            BudgetConfiguration.is_active == True
        ).all()

        for b in active_hard_budgets:
            status = cls.get_budget_status(db, b.id)
            if status.is_hard_limit_breached:
                reason = (
                    f"Execution blocked: Budget '{b.name}' reached 100% hard limit. "
                    f"Current spend: ₹{status.current_spend:,.2f} (Limit: ₹{status.monthly_limit_amount:,.2f}), "
                    f"Current runs: {status.current_runs:,} (Limit: {status.monthly_run_limit:,})."
                )
                return False, reason

        return True, None
