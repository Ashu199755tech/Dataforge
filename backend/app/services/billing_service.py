from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription,
    PipelineUsageLedger
)
from backend.app.models.workspace import Workspace
from backend.app.models.execution import PipelineRun
from backend.app.schemas.billing import (
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    PricingConfigVersionResponse,
    CustomerSubscriptionCreate,
    CustomerSubscriptionUpdate,
    BillingOverviewResponse,
    TenantResponse
)


class BillingService:
    """
    Core Billing & Pricing Management Service.
    Manages tenant subscription contracts, versioned pricing tiers,
    and commercial overview compilation.
    """

    @staticmethod
    def seed_default_plans(db: Session):
        """Initializes standard Starter, Professional, and Enterprise plans if not existing."""
        plans_data = [
            {
                "plan_code": "starter",
                "name": "Starter Plan",
                "description": "Essential data movement and database ingestion for growing data teams.",
                "tier_level": 1,
                "is_active": True,
                "is_custom": False,
                "features": {
                    "max_workspaces": 1,
                    "max_concurrency": 5,
                    "copy_engine": "Basic",
                    "spark_engine": False,
                    "sql_pushdown": False,
                    "data_quality": "Basic",
                    "git_sync": False,
                    "support_tier": "Standard"
                },
                "pricing": {
                    "monthly_base_price": 9999.00,
                    "annual_base_price": 99990.00,
                    "included_pipeline_runs": 10000,
                    "basic_run_rate": 0.5000,
                    "standard_run_rate": 1.5000,
                    "advanced_run_rate": 3.0000,
                    "complex_run_rate": 5.0000,
                    "spark_node_hour_rate": 45.0000,
                    "sql_pushdown_rate": 0.0000,
                    "currency": "INR"
                }
            },
            {
                "plan_code": "professional",
                "name": "Professional Plan",
                "description": "High-throughput parallel Copy Engine, Spark, SQL Pushdown, and enterprise Git CI/CD.",
                "tier_level": 2,
                "is_active": True,
                "is_custom": False,
                "features": {
                    "max_workspaces": 5,
                    "max_concurrency": 20,
                    "copy_engine": "Advanced Parallel",
                    "spark_engine": True,
                    "sql_pushdown": True,
                    "data_quality": "Continuous & Reconciliation",
                    "git_sync": True,
                    "support_tier": "Priority 24/5"
                },
                "pricing": {
                    "monthly_base_price": 29999.00,
                    "annual_base_price": 299990.00,
                    "included_pipeline_runs": 50000,
                    "basic_run_rate": 0.5000,
                    "standard_run_rate": 1.5000,
                    "advanced_run_rate": 3.0000,
                    "complex_run_rate": 5.0000,
                    "spark_node_hour_rate": 45.0000,
                    "sql_pushdown_rate": 0.0000,
                    "currency": "INR"
                }
            },
            {
                "plan_code": "enterprise",
                "name": "Enterprise Plan",
                "description": "Massive scale execution, self-hosted integration runtimes, dedicated SLA, and custom adapters.",
                "tier_level": 3,
                "is_active": True,
                "is_custom": False,
                "features": {
                    "max_workspaces": 50,
                    "max_concurrency": 100,
                    "copy_engine": "Full High-Throughput",
                    "spark_engine": True,
                    "sql_pushdown": True,
                    "data_quality": "Full Enterprise Governance",
                    "git_sync": True,
                    "self_hosted_runtime": True,
                    "support_tier": "Dedicated 24/7 & 99.9% SLA"
                },
                "pricing": {
                    "monthly_base_price": 99999.00,
                    "annual_base_price": 999990.00,
                    "included_pipeline_runs": 250000,
                    "basic_run_rate": 0.5000,
                    "standard_run_rate": 1.5000,
                    "advanced_run_rate": 3.0000,
                    "complex_run_rate": 5.0000,
                    "spark_node_hour_rate": 45.0000,
                    "sql_pushdown_rate": 0.0000,
                    "currency": "INR"
                }
            }
        ]

        for p_data in plans_data:
            existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == p_data["plan_code"]).first()
            if not existing:
                plan = SubscriptionPlan(
                    plan_code=p_data["plan_code"],
                    name=p_data["name"],
                    description=p_data["description"],
                    tier_level=p_data["tier_level"],
                    is_active=p_data["is_active"],
                    is_custom=p_data["is_custom"],
                    features=p_data["features"]
                )
                db.add(plan)
                db.flush()

                p_cfg = p_data["pricing"]
                version = PricingConfigVersion(
                    plan_id=plan.id,
                    version_number=1,
                    monthly_base_price=p_cfg["monthly_base_price"],
                    annual_base_price=p_cfg["annual_base_price"],
                    included_pipeline_runs=p_cfg["included_pipeline_runs"],
                    basic_run_rate=p_cfg["basic_run_rate"],
                    standard_run_rate=p_cfg["standard_run_rate"],
                    advanced_run_rate=p_cfg["advanced_run_rate"],
                    complex_run_rate=p_cfg["complex_run_rate"],
                    spark_node_hour_rate=p_cfg["spark_node_hour_rate"],
                    sql_pushdown_rate=p_cfg["sql_pushdown_rate"],
                    currency=p_cfg["currency"],
                    effective_from=datetime.now(timezone.utc)
                )
                db.add(version)
        db.commit()

    @staticmethod
    def get_or_create_default_tenant(db: Session, workspace_id: Optional[str] = None) -> Tenant:
        """Retrieves or provisions the primary corporate tenant."""
        tenant = db.query(Tenant).filter(Tenant.name == "Default Enterprise Organization").first()
        if not tenant:
            tenant = Tenant(
                name="Default Enterprise Organization",
                billing_email="billing@dataflow.enterprise",
                currency="INR",
                country="IN",
                deployment_model="BYOC"
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        # Ensure active workspace links to tenant
        if workspace_id:
            ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if ws and not getattr(ws, "tenant_id", None):
                ws.tenant_id = tenant.id
                db.commit()

        # Ensure tenant has an active subscription
        sub = db.query(CustomerSubscription).filter(CustomerSubscription.tenant_id == tenant.id).first()
        if not sub:
            pro_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "professional").first()
            if pro_plan and pro_plan.pricing_versions:
                now = datetime.now(timezone.utc)
                sub = CustomerSubscription(
                    tenant_id=tenant.id,
                    workspace_id=workspace_id,
                    plan_id=pro_plan.id,
                    pricing_version_id=pro_plan.pricing_versions[0].id,
                    billing_period="Monthly",
                    status="Active",
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                    cancel_at_period_end=False
                )
                db.add(sub)
                db.commit()

        return tenant

    @staticmethod
    def get_available_plans(db: Session) -> List[Dict[str, Any]]:
        """Returns all active plans along with their latest versioned pricing rules."""
        plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.tier_level.asc()).all()
        result = []
        for p in plans:
            latest_v = db.query(PricingConfigVersion).filter(
                PricingConfigVersion.plan_id == p.id
            ).order_by(PricingConfigVersion.version_number.desc()).first()

            result.append({
                "id": p.id,
                "plan_code": p.plan_code,
                "name": p.name,
                "description": p.description,
                "tier_level": p.tier_level,
                "is_active": p.is_active,
                "is_custom": p.is_custom,
                "features": p.features,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "active_pricing": latest_v
            })
        return result

    @staticmethod
    def get_plan_by_id(db: Session, plan_id: str) -> Optional[SubscriptionPlan]:
        return db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

    @staticmethod
    def get_subscription_for_workspace(db: Session, workspace_id: Optional[str] = None) -> Optional[CustomerSubscription]:
        """Resolves active subscription for a workspace or tenant."""
        tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
        sub = db.query(CustomerSubscription).filter(
            CustomerSubscription.tenant_id == tenant.id,
            CustomerSubscription.status == "Active"
        ).first()
        return sub

    @staticmethod
    def update_subscription(
        db: Session,
        plan_id: str,
        billing_period: str = "Monthly",
        workspace_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> CustomerSubscription:
        """Upgrades, downgrades, or modifies subscription terms."""
        tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
        target_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not target_plan:
            raise ValueError(f"Subscription plan '{plan_id}' does not exist.")

        latest_version = db.query(PricingConfigVersion).filter(
            PricingConfigVersion.plan_id == target_plan.id
        ).order_by(PricingConfigVersion.version_number.desc()).first()
        if not latest_version:
            raise ValueError(f"No active pricing version available for plan '{target_plan.name}'.")

        sub = db.query(CustomerSubscription).filter(CustomerSubscription.tenant_id == tenant.id).first()
        now = datetime.now(timezone.utc)
        duration_days = 365 if billing_period.lower() == "annual" else 30

        if not sub:
            sub = CustomerSubscription(
                tenant_id=tenant.id,
                workspace_id=workspace_id,
                plan_id=target_plan.id,
                pricing_version_id=latest_version.id,
                billing_period=billing_period.capitalize(),
                status="Active",
                current_period_start=now,
                current_period_end=now + timedelta(days=duration_days),
                custom_agreement_notes=notes
            )
            db.add(sub)
        else:
            sub.plan_id = target_plan.id
            sub.pricing_version_id = latest_version.id
            sub.billing_period = billing_period.capitalize()
            sub.status = "Active"
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=duration_days)
            if notes is not None:
                sub.custom_agreement_notes = notes

        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def get_billing_overview(db: Session, workspace_id: Optional[str] = None) -> BillingOverviewResponse:
        """
        Compiles the comprehensive commercial overview: active plan, included allowance,
        actual execution runs in period, overage estimate, and software charges.
        """
        tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
        sub = BillingService.get_subscription_for_workspace(db, workspace_id)
        
        # Resolve pricing
        if sub and sub.pricing_version:
            pv = sub.pricing_version
            plan = sub.plan
            monthly_price = float(pv.monthly_base_price)
            annual_price = float(pv.annual_base_price)
            included_runs = int(pv.included_pipeline_runs)
            tier_lvl = plan.tier_level
            plan_name = plan.name
            currency = pv.currency
            period = sub.billing_period
            sub_status = sub.status
            next_bill = sub.current_period_end
            p_start = sub.current_period_start
            p_end = sub.current_period_end
        else:
            monthly_price = 29999.00
            annual_price = 299990.00
            included_runs = 50000
            tier_lvl = 2
            plan_name = "Professional Plan"
            currency = "INR"
            period = "Monthly"
            sub_status = "Active"
            now = datetime.now(timezone.utc)
            next_bill = now + timedelta(days=30)
            p_start = now - timedelta(days=now.day - 1)
            p_end = next_bill

        # Check authoritative PipelineUsageLedger first for metered billable executions
        period_key = p_start.strftime("%Y-%m")
        ledger_billable_count = db.query(PipelineUsageLedger).filter(
            PipelineUsageLedger.billing_period_key == period_key,
            PipelineUsageLedger.is_billable == True
        ).count()

        if ledger_billable_count > 0:
            consumed_runs = ledger_billable_count
        else:
            # Query actual billable runs executed within current period
            runs_query = db.query(PipelineRun).filter(
                PipelineRun.started_at >= p_start,
                PipelineRun.started_at <= p_end,
                PipelineRun.status.in_(["Succeeded", "Failed"])
            )
            consumed_runs = runs_query.count()

        overage_runs = max(consumed_runs - included_runs, 0)
        remaining_runs = max(included_runs - consumed_runs, 0)

        # Baseline overage estimated at Standard rate (₹1.50)
        avg_overage_rate = 1.50
        estimated_overage = round(overage_runs * avg_overage_rate, 2)
        base_software_fee = annual_price / 12.0 if period.lower() == "annual" else monthly_price
        total_software_charges = round(base_software_fee + estimated_overage, 2)

        return BillingOverviewResponse(
            tenant=TenantResponse.model_validate(tenant),
            subscription=sub,
            plan_name=plan_name,
            tier_level=tier_lvl,
            monthly_subscription_amount=monthly_price,
            annual_subscription_amount=annual_price,
            currency=currency,
            billing_period=period,
            subscription_status=sub_status,
            next_billing_date=next_bill,
            included_runs=included_runs,
            consumed_runs=consumed_runs,
            remaining_runs=remaining_runs,
            overage_runs=overage_runs,
            estimated_overage_charges=estimated_overage,
            estimated_spark_compute_charges=0.00,
            estimated_total_software_charges=total_software_charges,
            previous_month_charges=monthly_price,
            deployment_model=tenant.deployment_model
        )
