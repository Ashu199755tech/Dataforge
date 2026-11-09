from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from backend.app.models.billing import (
    UsageAggregation,
    PipelineUsageLedger,
    Tenant,
    CustomerSubscription,
    PricingConfigVersion
)
from backend.app.models.workspace import Workspace
from backend.app.services.billing_service import BillingService


class RatingEngine:
    """
    Dedicated Rating & Usage Aggregation Engine.
    Evaluates immutable pipeline execution ledger entries against subscription allowances,
    calculates graduated overage rates across Basic/Standard/Advanced/Complex tiers,
    meters Spark worker node-hours, and generates high-performance rollups for the Billing portal.
    """

    @staticmethod
    def aggregate_usage_for_period(
        db: Session,
        tenant_id: str,
        period_key: str,
        workspace_id: Optional[str] = None
    ) -> UsageAggregation:
        """
        Calculates or recalculates the monthly usage rollup and charges for a given tenant.
        Ensures exact attribution of included allowance vs graduated overage rates.
        """
        # Resolve active subscription & versioned rates for tenant
        sub = None
        if tenant_id:
            sub = db.query(CustomerSubscription).filter(
                CustomerSubscription.tenant_id == tenant_id,
                CustomerSubscription.status == "Active"
            ).first()
        if not sub:
            sub = BillingService.get_subscription_for_workspace(db, workspace_id)
        pv = sub.pricing_version if sub else None

        # Fetch all usage ledger records for this tenant and billing period
        query = db.query(PipelineUsageLedger).filter(
            PipelineUsageLedger.tenant_id == tenant_id,
            PipelineUsageLedger.billing_period_key == period_key
        )
        if workspace_id:
            query = query.filter(PipelineUsageLedger.workspace_id == workspace_id)

        records: List[PipelineUsageLedger] = query.order_by(PipelineUsageLedger.started_at.asc()).all()

        total_runs = len(records)
        billable_records = [r for r in records if r.is_billable]
        billable_runs = len(billable_records)
        non_billable_runs = total_runs - billable_runs

        # Classifications
        basic_runs = sum(1 for r in records if r.classification == "Basic")
        standard_runs = sum(1 for r in records if r.classification == "Standard")
        advanced_runs = sum(1 for r in records if r.classification == "Advanced")
        complex_runs = sum(1 for r in records if r.classification == "Complex")

        # Execution Engines
        copy_runs = sum(1 for r in records if r.execution_engine == "CopyEngine")
        spark_runs = sum(1 for r in records if r.execution_engine == "SparkEngine")
        sql_runs = sum(1 for r in records if r.execution_engine == "SqlPushdownEngine")
        hybrid_runs = sum(1 for r in records if r.execution_engine == "Hybrid")

        # Spark compute consumption (node-hours)
        spark_duration_secs = sum(
            float(r.duration_seconds or 0.0)
            for r in records
            if r.execution_engine in ("SparkEngine", "Hybrid")
        )
        spark_node_hours = round(spark_duration_secs / 3600.0, 4)

        # Allowance & Graduated Overages
        included_allowance = int(pv.included_pipeline_runs) if pv else 50000
        included_runs_consumed = min(billable_runs, included_allowance)
        overage_runs = max(0, billable_runs - included_allowance)

        # Rate overage runs chronologically
        total_overage_charge = 0.0
        if overage_runs > 0:
            overage_items = billable_records[included_allowance:]
            for r in overage_items:
                charge = float(r.calculated_charge)
                if charge == 0.0 and pv:
                    if r.classification == "Basic":
                        charge = float(pv.basic_run_rate)
                    elif r.classification == "Standard":
                        charge = float(pv.standard_run_rate)
                    elif r.classification == "Advanced":
                        charge = float(pv.advanced_run_rate)
                    else:
                        charge = float(pv.complex_run_rate)
                elif charge == 0.0:
                    fallback_rates = {"Basic": 0.50, "Standard": 1.50, "Advanced": 3.00, "Complex": 5.00}
                    charge = fallback_rates.get(r.classification, 0.50)
                total_overage_charge += charge

        total_overage_charge = round(total_overage_charge, 2)

        # Spark Compute Rating
        spark_rate = float(pv.spark_node_hour_rate) if pv else 45.00
        spark_compute_charge = round(spark_node_hours * spark_rate, 2)

        total_variable_charge = round(total_overage_charge + spark_compute_charge, 2)

        # Idempotent Upsert into usage_aggregations
        agg = db.query(UsageAggregation).filter(
            UsageAggregation.tenant_id == tenant_id,
            UsageAggregation.period_key == period_key
        ).first()

        now = datetime.now(timezone.utc)
        if not agg:
            agg = UsageAggregation(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                subscription_id=sub.id if sub else None,
                period_key=period_key,
                total_runs=total_runs,
                billable_runs=billable_runs,
                non_billable_runs=non_billable_runs,
                basic_runs=basic_runs,
                standard_runs=standard_runs,
                advanced_runs=advanced_runs,
                complex_runs=complex_runs,
                copy_engine_runs=copy_runs,
                spark_runs=spark_runs,
                sql_pushdown_runs=sql_runs,
                hybrid_runs=hybrid_runs,
                spark_node_hours=spark_node_hours,
                included_runs_consumed=included_runs_consumed,
                overage_runs=overage_runs,
                total_overage_charge=total_overage_charge,
                spark_compute_charge=spark_compute_charge,
                total_charge=total_variable_charge,
                last_calculated_at=now
            )
            db.add(agg)
        else:
            agg.subscription_id = sub.id if sub else agg.subscription_id
            agg.total_runs = total_runs
            agg.billable_runs = billable_runs
            agg.non_billable_runs = non_billable_runs
            agg.basic_runs = basic_runs
            agg.standard_runs = standard_runs
            agg.advanced_runs = advanced_runs
            agg.complex_runs = complex_runs
            agg.copy_engine_runs = copy_runs
            agg.spark_runs = spark_runs
            agg.sql_pushdown_runs = sql_runs
            agg.hybrid_runs = hybrid_runs
            agg.spark_node_hours = spark_node_hours
            agg.included_runs_consumed = included_runs_consumed
            agg.overage_runs = overage_runs
            agg.total_overage_charge = total_overage_charge
            agg.spark_compute_charge = spark_compute_charge
            agg.total_charge = total_variable_charge
            agg.last_calculated_at = now

        db.commit()
        db.refresh(agg)
        return agg

    @staticmethod
    def get_daily_consumption(
        db: Session,
        tenant_id: str,
        period_key: str
    ) -> List[Dict[str, Any]]:
        """
        Aggregates daily consumption breakdown for ADF-parity daily consumption charts.
        """
        records = db.query(PipelineUsageLedger).filter(
            PipelineUsageLedger.tenant_id == tenant_id,
            PipelineUsageLedger.billing_period_key == period_key
        ).order_by(PipelineUsageLedger.started_at.asc()).all()

        daily_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            day_str = r.started_at.strftime("%Y-%m-%d") if r.started_at else datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if day_str not in daily_map:
                daily_map[day_str] = {
                    "date": day_str,
                    "total_runs": 0,
                    "billable_runs": 0,
                    "non_billable_runs": 0,
                    "basic_runs": 0,
                    "standard_runs": 0,
                    "advanced_runs": 0,
                    "complex_runs": 0,
                    "spark_runs": 0,
                    "copy_runs": 0,
                    "sql_runs": 0,
                    "estimated_charges": 0.0
                }

            daily = daily_map[day_str]
            daily["total_runs"] += 1
            if r.is_billable:
                daily["billable_runs"] += 1
                daily["estimated_charges"] = round(daily["estimated_charges"] + float(r.calculated_charge), 2)
            else:
                daily["non_billable_runs"] += 1

            if r.classification == "Basic": daily["basic_runs"] += 1
            elif r.classification == "Standard": daily["standard_runs"] += 1
            elif r.classification == "Advanced": daily["advanced_runs"] += 1
            elif r.classification == "Complex": daily["complex_runs"] += 1

            if r.execution_engine == "SparkEngine": daily["spark_runs"] += 1
            elif r.execution_engine == "CopyEngine": daily["copy_runs"] += 1
            elif r.execution_engine == "SqlPushdownEngine": daily["sql_runs"] += 1

        return sorted(list(daily_map.values()), key=lambda d: d["date"])

    @staticmethod
    def get_consumption_summary(
        db: Session,
        workspace_id: Optional[str] = None,
        period_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compiles the complete ADF-parity consumption report combining rollups,
        classification distributions, engine splits, and daily trend curves.
        """
        now = datetime.now(timezone.utc)
        effective_period = period_key or now.strftime("%Y-%m")

        tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
        sub = BillingService.get_subscription_for_workspace(db, workspace_id)
        pv = sub.pricing_version if sub else None

        # Calculate or update aggregation
        agg = RatingEngine.aggregate_usage_for_period(
            db=db,
            tenant_id=tenant.id,
            period_key=effective_period,
            workspace_id=workspace_id
        )

        daily = RatingEngine.get_daily_consumption(
            db=db,
            tenant_id=tenant.id,
            period_key=effective_period
        )

        included_runs = int(pv.included_pipeline_runs) if pv else 50000
        plan_name = sub.plan.name if sub and sub.plan else "Professional Plan"
        tier_level = sub.plan.tier_level if sub and sub.plan else 2

        monthly_base = float(pv.monthly_base_price) if pv else 29999.0
        if sub and sub.billing_period == "Annual" and pv:
            monthly_base = float(pv.annual_base_price) / 12.0

        estimated_total_software = round(monthly_base + float(agg.total_charge), 2)

        return {
            "period_key": effective_period,
            "plan_name": plan_name,
            "tier_level": tier_level,
            "included_runs": included_runs,
            "consumed_runs": agg.billable_runs,
            "remaining_runs": max(0, included_runs - agg.billable_runs),
            "overage_runs": agg.overage_runs,
            "total_runs": agg.total_runs,
            "billable_runs": agg.billable_runs,
            "non_billable_runs": agg.non_billable_runs,
            "classification_breakdown": {
                "Basic": agg.basic_runs,
                "Standard": agg.standard_runs,
                "Advanced": agg.advanced_runs,
                "Complex": agg.complex_runs
            },
            "engine_breakdown": {
                "CopyEngine": agg.copy_engine_runs,
                "SparkEngine": agg.spark_runs,
                "SqlPushdownEngine": agg.sql_pushdown_runs,
                "Hybrid": agg.hybrid_runs
            },
            "spark_node_hours": float(agg.spark_node_hours),
            "estimated_overage_charge": float(agg.total_overage_charge),
            "estimated_spark_compute_charge": float(agg.spark_compute_charge),
            "estimated_total_software_charge": estimated_total_software,
            "daily_consumption": daily
        }
