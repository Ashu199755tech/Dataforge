from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription,
    BillingInvoice,
    InvoiceLineItem,
    BillingAuditLog
)
from backend.app.models.data_quality import AuditLog
from backend.app.models.user import User
from backend.app.schemas.billing import (
    PricingVersionCreate,
    CustomEnterpriseAgreementRequest,
    BillingAdjustmentRequest
)


class AdminPricingService:
    """
    Administrative Billing & Pricing Configuration Service.
    Enforces RBAC-governed updates to subscription tiers, versioned pricing schedules,
    custom enterprise agreements, and financial credit adjustments with tamper-evident audit logging.
    """

    @staticmethod
    def publish_new_pricing_version(
        db: Session,
        plan_id: str,
        admin_user: User,
        data: PricingVersionCreate
    ) -> PricingConfigVersion:
        """
        Publishes a new pricing version for a subscription plan.
        Guarantees version immutability: past invoices reference historical versions
        and remain completely unaffected.
        """
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail=f"Subscription plan '{plan_id}' not found.")

        # Find latest version for this plan
        latest_version = db.query(PricingConfigVersion).filter(
            PricingConfigVersion.plan_id == plan.id
        ).order_by(PricingConfigVersion.version_number.desc()).first()

        now = datetime.now(timezone.utc)
        next_ver_num = (latest_version.version_number + 1) if latest_version else 1

        before_state = {}
        if latest_version:
            before_state = {
                "version_number": latest_version.version_number,
                "monthly_base_price": float(latest_version.monthly_base_price),
                "annual_base_price": float(latest_version.annual_base_price),
                "included_pipeline_runs": latest_version.included_pipeline_runs,
                "basic_run_rate": float(latest_version.basic_run_rate),
                "standard_run_rate": float(latest_version.standard_run_rate),
                "advanced_run_rate": float(latest_version.advanced_run_rate),
                "complex_run_rate": float(latest_version.complex_run_rate),
                "spark_node_hour_rate": float(latest_version.spark_node_hour_rate),
                "effective_from": latest_version.effective_from.isoformat() if latest_version.effective_from else None,
                "effective_to": latest_version.effective_to.isoformat() if latest_version.effective_to else None,
            }
            # Terminate validity of current version
            latest_version.effective_to = now

        new_version = PricingConfigVersion(
            plan_id=plan.id,
            version_number=next_ver_num,
            monthly_base_price=Decimal(str(data.monthly_base_price)),
            annual_base_price=Decimal(str(data.annual_base_price)),
            included_pipeline_runs=data.included_pipeline_runs,
            basic_run_rate=Decimal(str(data.basic_run_rate)),
            standard_run_rate=Decimal(str(data.standard_run_rate)),
            advanced_run_rate=Decimal(str(data.advanced_run_rate)),
            complex_run_rate=Decimal(str(data.complex_run_rate)),
            spark_node_hour_rate=Decimal(str(data.spark_node_hour_rate)),
            sql_pushdown_rate=Decimal(str(data.sql_pushdown_rate)),
            currency=data.currency.upper(),
            effective_from=now,
            effective_to=None,
            created_by_id=admin_user.id
        )
        db.add(new_version)
        db.flush()

        after_state = {
            "version_number": next_ver_num,
            "monthly_base_price": float(data.monthly_base_price),
            "annual_base_price": float(data.annual_base_price),
            "included_pipeline_runs": data.included_pipeline_runs,
            "basic_run_rate": float(data.basic_run_rate),
            "standard_run_rate": float(data.standard_run_rate),
            "advanced_run_rate": float(data.advanced_run_rate),
            "complex_run_rate": float(data.complex_run_rate),
            "spark_node_hour_rate": float(data.spark_node_hour_rate),
            "currency": data.currency.upper(),
            "effective_from": now.isoformat()
        }

        # Record specialized Billing Audit Log
        billing_audit = BillingAuditLog(
            admin_user_id=admin_user.id,
            admin_email=admin_user.email,
            action="UpdatePricingVersion",
            resource_type="PricingConfigVersion",
            resource_id=new_version.id,
            before_state=before_state,
            after_state=after_state,
            justification=data.justification
        )
        db.add(billing_audit)

        # Record platform-wide AuditLog
        platform_audit = AuditLog(
            user_id=admin_user.id,
            action="UpdatePricingVersion",
            resource_type="PricingConfigVersion",
            resource_id=new_version.id,
            details={
                "plan_code": plan.plan_code,
                "plan_name": plan.name,
                "version_number": next_ver_num,
                "justification": data.justification
            }
        )
        db.add(platform_audit)
        db.commit()
        db.refresh(new_version)
        return new_version

    @staticmethod
    def configure_custom_enterprise_agreement(
        db: Session,
        admin_user: User,
        data: CustomEnterpriseAgreementRequest
    ) -> CustomerSubscription:
        """
        Creates or binds a tenant to a bespoke enterprise volume licensing agreement.
        Overrides standard tier rules with custom allowances, volume discounts, and bespoke notes.
        """
        tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant '{data.tenant_id}' not found.")

        now = datetime.now(timezone.utc)
        custom_code = f"enterprise_custom_{tenant.id[:8]}"

        # Find or create bespoke plan for this enterprise tenant
        custom_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == custom_code).first()
        if not custom_plan:
            custom_plan = SubscriptionPlan(
                plan_code=custom_code,
                name=data.plan_name,
                description="Bespoke enterprise contract with negotiated volume pricing and dedicated SLA.",
                tier_level=3,
                is_active=True,
                is_custom=True,
                features={
                    "custom_licensing": True,
                    "included_runs": data.included_pipeline_runs,
                    "dedicated_runtime": True,
                    "git_integration": True,
                    "spark_engine": True,
                    "sql_pushdown": True,
                    "custom_sla_hours": 4
                }
            )
            db.add(custom_plan)
            db.flush()

        # Create custom pricing configuration version
        custom_version = PricingConfigVersion(
            plan_id=custom_plan.id,
            version_number=1,
            monthly_base_price=Decimal(str(data.monthly_base_price)),
            annual_base_price=Decimal(str(data.annual_base_price)),
            included_pipeline_runs=data.included_pipeline_runs,
            basic_run_rate=Decimal(str(data.basic_run_rate)),
            standard_run_rate=Decimal(str(data.standard_run_rate)),
            advanced_run_rate=Decimal(str(data.advanced_run_rate)),
            complex_run_rate=Decimal(str(data.complex_run_rate)),
            spark_node_hour_rate=Decimal(str(data.spark_node_hour_rate)),
            sql_pushdown_rate=Decimal("0.0000"),
            currency=data.currency.upper(),
            effective_from=now,
            effective_to=None,
            created_by_id=admin_user.id
        )
        db.add(custom_version)
        db.flush()

        # Update or create active subscription
        sub = db.query(CustomerSubscription).filter(
            CustomerSubscription.tenant_id == tenant.id,
            CustomerSubscription.status == "Active"
        ).first()

        before_state = {}
        if sub:
            before_state = {
                "plan_id": sub.plan_id,
                "pricing_version_id": sub.pricing_version_id,
                "billing_period": sub.billing_period,
                "notes": sub.custom_agreement_notes
            }
            sub.plan_id = custom_plan.id
            sub.pricing_version_id = custom_version.id
            sub.custom_agreement_notes = data.custom_agreement_notes
            sub.updated_at = now
        else:
            period_end = now.replace(day=28)
            sub = CustomerSubscription(
                tenant_id=tenant.id,
                plan_id=custom_plan.id,
                pricing_version_id=custom_version.id,
                billing_period="Monthly",
                status="Active",
                current_period_start=now,
                current_period_end=period_end,
                custom_agreement_notes=data.custom_agreement_notes
            )
            db.add(sub)
            db.flush()

        after_state = {
            "tenant_id": tenant.id,
            "plan_code": custom_code,
            "pricing_version_id": custom_version.id,
            "monthly_base_price": float(data.monthly_base_price),
            "included_runs": data.included_pipeline_runs,
            "notes": data.custom_agreement_notes
        }

        # Record Billing Audit Log
        billing_audit = BillingAuditLog(
            tenant_id=tenant.id,
            admin_user_id=admin_user.id,
            admin_email=admin_user.email,
            action="ConfigureCustomAgreement",
            resource_type="CustomerSubscription",
            resource_id=sub.id,
            before_state=before_state,
            after_state=after_state,
            justification=data.justification
        )
        db.add(billing_audit)

        db.commit()
        db.refresh(sub)
        return sub

    @staticmethod
    def apply_invoice_adjustment(
        db: Session,
        invoice_id: str,
        admin_user: User,
        data: BillingAdjustmentRequest
    ) -> BillingInvoice:
        """
        Applies a manual credit or discount adjustment to an invoice.
        Recomputes subtotal, tax (18%), and total amount.
        Prevents mutations on Paid or Void invoices.
        """
        invoice = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found.")

        if invoice.status in ["Paid", "Void"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot apply adjustments to an invoice in status '{invoice.status}'."
            )

        credit_amount = Decimal(str(abs(data.adjustment_amount)))

        before_state = {
            "subtotal_amount": float(invoice.subtotal_amount),
            "adjustments_amount": float(invoice.adjustments_amount or 0.0),
            "tax_amount": float(invoice.tax_amount),
            "total_amount": float(invoice.total_amount),
            "status": invoice.status
        }

        # Create credit line item
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            item_type="CreditAdjustment",
            description=f"[{data.adjustment_type}] {data.description}",
            quantity=Decimal("1.0"),
            unit_price=-credit_amount,
            amount=-credit_amount
        )
        db.add(line_item)

        # Update adjustments total
        current_adjustments = Decimal(str(invoice.adjustments_amount or 0.00))
        new_adjustments = current_adjustments + credit_amount
        invoice.adjustments_amount = new_adjustments

        # Recompute totals
        gross_software = (
            Decimal(str(invoice.subscription_amount or 0.00)) +
            Decimal(str(invoice.overage_amount or 0.00)) +
            Decimal(str(invoice.compute_amount or 0.00))
        )
        new_subtotal = max(Decimal("0.00"), gross_software - new_adjustments)
        tax_pct = Decimal(str(invoice.tax_percent or 18.00)) / Decimal("100.00")
        new_tax = (new_subtotal * tax_pct).quantize(Decimal("0.01"))
        new_total = (new_subtotal + new_tax).quantize(Decimal("0.01"))

        invoice.subtotal_amount = new_subtotal
        invoice.tax_amount = new_tax
        invoice.total_amount = new_total
        invoice.updated_at = datetime.now(timezone.utc)

        after_state = {
            "subtotal_amount": float(new_subtotal),
            "adjustments_amount": float(new_adjustments),
            "tax_amount": float(new_tax),
            "total_amount": float(new_total),
            "credit_applied": float(credit_amount)
        }

        # Audit entry
        audit = BillingAuditLog(
            tenant_id=invoice.tenant_id,
            admin_user_id=admin_user.id,
            admin_email=admin_user.email,
            action="ApplyCredit",
            resource_type="BillingInvoice",
            resource_id=invoice.id,
            before_state=before_state,
            after_state=after_state,
            justification=data.justification
        )
        db.add(audit)

        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def list_audit_logs(
        db: Session,
        tenant_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[BillingAuditLog]:
        """Returns paginated audit trail of billing administrative events."""
        q = db.query(BillingAuditLog)
        if tenant_id:
            q = q.filter(BillingAuditLog.tenant_id == tenant_id)
        return q.order_by(BillingAuditLog.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def list_all_admin_plans(db: Session) -> List[SubscriptionPlan]:
        """Returns all subscription plans with full version histories."""
        return db.query(SubscriptionPlan).options(
            joinedload(SubscriptionPlan.pricing_versions)
        ).order_by(SubscriptionPlan.tier_level.asc()).all()
