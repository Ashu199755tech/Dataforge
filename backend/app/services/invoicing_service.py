"""
DataForge – Automated Invoicing, 18% GST Tax, and Payment Ledger Service.
Handles B2B proforma invoicing, itemized line items, and offline/wire transfer payment reconciliation.
Strictly complies with ISO 32000-1 PDF generation and zero fake card transactions.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.billing import (
    Tenant,
    CustomerSubscription,
    BillingInvoice,
    InvoiceLineItem,
    PaymentRecord,
    UsageAggregation
)
from backend.app.models.data_quality import AuditLog
from backend.app.services.billing_service import BillingService
from backend.app.services.rating_engine import RatingEngine
from backend.app.services.pdf_generator import PDFInvoiceGenerator


class BasePaymentGateway(ABC):
    """
    Extensible Payment Provider Abstraction.
    All payment providers must implement record_payment to prevent fake simulations.
    """

    @abstractmethod
    def record_payment(
        self,
        db: Session,
        invoice: BillingInvoice,
        amount: float,
        reference: str,
        method: str,
        notes: Optional[str] = None,
        verified_by_user_id: Optional[str] = None
    ) -> PaymentRecord:
        pass


class OfflineBankTransferAdapter(BasePaymentGateway):
    """
    Default enterprise B2B payment adapter for Bank Wires (NEFT/RTGS/IMPS),
    Corporate Purchase Orders, and offline transfers.
    Records verified payments and transitions invoice status with audit tracking.
    """

    def record_payment(
        self,
        db: Session,
        invoice: BillingInvoice,
        amount: float,
        reference: str,
        method: str = "BankTransfer",
        notes: Optional[str] = None,
        verified_by_user_id: Optional[str] = None
    ) -> PaymentRecord:
        payment = PaymentRecord(
            invoice_id=invoice.id,
            tenant_id=invoice.tenant_id,
            payment_reference=reference,
            payment_method=method,
            amount=Decimal(str(round(amount, 2))),
            currency=invoice.currency,
            payment_status="Completed",
            payment_date=datetime.now(timezone.utc),
            verified_by_user_id=verified_by_user_id,
            notes=notes
        )
        db.add(payment)
        db.flush()

        # Check total payments recorded against this invoice
        total_paid_query = db.query(func.coalesce(func.sum(PaymentRecord.amount), 0)).filter(
            PaymentRecord.invoice_id == invoice.id,
            PaymentRecord.payment_status == "Completed"
        ).scalar()

        total_paid = float(total_paid_query)
        if total_paid >= float(invoice.total_amount):
            invoice.status = "Paid"

        # Tamper-evident audit logging
        audit = AuditLog(
            workspace_id=invoice.subscription.workspace_id if invoice.subscription else None,
            user_id=verified_by_user_id or "system_admin",
            action="PAYMENT_RECORDED",
            resource_type="BillingInvoice",
            resource_id=invoice.id,
            details={
                "payment_id": payment.id,
                "amount": float(payment.amount),
                "reference": reference,
                "method": method,
                "total_paid": total_paid,
                "invoice_status": invoice.status
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(invoice)
        db.refresh(payment)
        return payment


class InvoiceService:
    """
    Enterprise billing invoice generator and management service.
    """

    payment_gateway: BasePaymentGateway = OfflineBankTransferAdapter()

    @classmethod
    def generate_monthly_invoice(
        cls,
        db: Session,
        tenant_id: str,
        period_key: Optional[str] = None,
        notes: Optional[str] = None
    ) -> BillingInvoice:
        """
        Generates or recalculates a monthly commercial invoice for a tenant.
        Idempotent: If an invoice for the period already exists in 'Issued' or 'Draft' state,
        it refreshes its line items and returns it.
        """
        if not period_key:
            period_key = datetime.now(timezone.utc).strftime("%Y-%m")

        # Resolve tenant
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise ValueError(f"Tenant with ID {tenant_id} not found.")

        # Check for existing invoice
        existing = db.query(BillingInvoice).filter(
            BillingInvoice.tenant_id == tenant_id,
            BillingInvoice.period_key == period_key
        ).first()

        if existing and existing.status in ("Paid", "Void"):
            # Paid or void invoices are permanently immutable
            return existing

        # Resolve active subscription
        sub = db.query(CustomerSubscription).filter(
            CustomerSubscription.tenant_id == tenant_id,
            CustomerSubscription.status.in_(["Active", "Trial", "PastDue"])
        ).first()

        pricing_version = sub.pricing_version if sub else None

        # Period date boundaries
        year, month = map(int, period_key.split("-"))
        period_start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if month == 12:
            period_end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            period_end = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=timezone.utc) - timedelta(seconds=1)

        # Retrieve rating & usage aggregation for period
        agg: UsageAggregation = RatingEngine.aggregate_usage_for_period(db, tenant_id, period_key)

        # 1. Base Subscription Fee
        sub_fee = Decimal("0.00")
        sub_desc = "DataForge Platform Subscription"
        if pricing_version:
            if sub.billing_period == "Annual":
                sub_fee = Decimal(str(pricing_version.annual_base_price)) / Decimal("12.00")
                sub_desc = f"{sub.plan.name} (Annual Allocation)"
            else:
                sub_fee = Decimal(str(pricing_version.monthly_base_price))
                sub_desc = f"{sub.plan.name} (Monthly Platform Subscription)"

        # 2. Overages
        overage_fee = Decimal(str(agg.total_overage_charge or "0.00"))

        # 3. Spark Compute
        spark_fee = Decimal(str(agg.spark_compute_charge or "0.00"))

        # Subtotal
        subtotal = sub_fee + overage_fee + spark_fee

        # 4. Tax (18.00% GST)
        tax_pct = Decimal("18.00")
        tax_amt = (subtotal * (tax_pct / Decimal("100.00"))).quantize(Decimal("0.01"))

        # Total
        total_amt = subtotal + tax_amt

        # Format Invoice Number: DF-INV-YYYY-MM-XXXX
        if existing:
            invoice = existing
            invoice.subscription_amount = sub_fee
            invoice.overage_amount = overage_fee
            invoice.compute_amount = spark_fee
            invoice.subtotal_amount = subtotal
            invoice.tax_percent = tax_pct
            invoice.tax_amount = tax_amt
            invoice.total_amount = total_amt
            invoice.notes = notes or invoice.notes

            # Clear old line items for recalculation
            db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).delete()
        else:
            inv_count = db.query(BillingInvoice).filter(BillingInvoice.period_key == period_key).count()
            inv_num = f"DF-INV-{period_key}-{inv_count + 1:04d}"

            now = datetime.now(timezone.utc)
            invoice = BillingInvoice(
                tenant_id=tenant_id,
                subscription_id=sub.id if sub else None,
                invoice_number=inv_num,
                period_key=period_key,
                billing_period_start=period_start,
                billing_period_end=period_end,
                issue_date=now,
                due_date=now + timedelta(days=15),
                currency=tenant.currency or "INR",
                subscription_amount=sub_fee,
                overage_amount=overage_fee,
                compute_amount=spark_fee,
                subtotal_amount=subtotal,
                tax_percent=tax_pct,
                tax_amount=tax_amt,
                adjustments_amount=Decimal("0.00"),
                total_amount=total_amt,
                status="Issued",
                notes=notes
            )
            db.add(invoice)
            db.flush()

        # Build itemized line items
        line_items = []

        # Line Item 1: Base Platform Subscription
        line_items.append(
            InvoiceLineItem(
                invoice_id=invoice.id,
                item_type="SubscriptionBase",
                description=sub_desc,
                quantity=Decimal("1.00"),
                unit_price=sub_fee,
                amount=sub_fee
            )
        )

        # Line Item 2: Overage pipeline executions (if any)
        if agg.overage_runs > 0:
            avg_rate = (overage_fee / Decimal(str(agg.overage_runs))).quantize(Decimal("0.0001"))
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    item_type="OverageStandard",
                    description=f"Additional Pipeline Executions ({agg.overage_runs:,} runs exceeding allowance)",
                    quantity=Decimal(str(agg.overage_runs)),
                    unit_price=avg_rate,
                    amount=overage_fee
                )
            )

        # Line Item 3: Managed Spark Compute (if any)
        if agg.spark_node_hours > 0:
            spark_rate = Decimal(str(pricing_version.spark_node_hour_rate if pricing_version else "45.00"))
            line_items.append(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    item_type="SparkCompute",
                    description=f"Managed Spark Compute ({float(agg.spark_node_hours):.2f} worker node-hours)",
                    quantity=Decimal(str(agg.spark_node_hours)),
                    unit_price=spark_rate,
                    amount=spark_fee
                )
            )

        for li in line_items:
            db.add(li)

        db.commit()
        db.refresh(invoice)
        return invoice

    @classmethod
    def list_invoices(
        cls,
        db: Session,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
        period_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[BillingInvoice], int]:
        """
        Lists invoices with optional filters and pagination.
        """
        query = db.query(BillingInvoice)
        if tenant_id:
            query = query.filter(BillingInvoice.tenant_id == tenant_id)
        if status:
            query = query.filter(BillingInvoice.status == status)
        if period_key:
            query = query.filter(BillingInvoice.period_key == period_key)

        total = query.count()
        invoices = query.order_by(BillingInvoice.issue_date.desc()).offset(offset).limit(limit).all()
        return invoices, total

    @classmethod
    def get_invoice_by_id(
        cls,
        db: Session,
        invoice_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[BillingInvoice]:
        """
        Retrieves an invoice by ID with line items and payments.
        """
        query = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id)
        if tenant_id:
            query = query.filter(BillingInvoice.tenant_id == tenant_id)
        return query.first()

    @classmethod
    def generate_invoice_pdf(cls, db: Session, invoice_id: str) -> bytes:
        """
        Generates standard ISO 32000-1 PDF statement bytes for an invoice.
        """
        invoice = cls.get_invoice_by_id(db, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found.")

        tenant = invoice.tenant
        invoice_data = {
            "invoice_number": invoice.invoice_number,
            "period_key": invoice.period_key,
            "issue_date": invoice.issue_date.strftime("%Y-%m-%d"),
            "due_date": invoice.due_date.strftime("%Y-%m-%d"),
            "status": invoice.status,
            "tenant_name": tenant.name if tenant else "Customer Tenant",
            "billing_email": tenant.billing_email if tenant else "finance@customer.com",
            "tax_identifier": tenant.tax_identifier if tenant else None,
            "deployment_model": tenant.deployment_model if tenant else "BYOC",
            "currency": invoice.currency,
            "subscription_amount": float(invoice.subscription_amount),
            "subtotal_amount": float(invoice.subtotal_amount),
            "tax_percent": float(invoice.tax_percent),
            "tax_amount": float(invoice.tax_amount),
            "adjustments_amount": float(invoice.adjustments_amount),
            "total_amount": float(invoice.total_amount),
            "line_items": [
                {
                    "description": li.description,
                    "item_type": li.item_type,
                    "quantity": float(li.quantity),
                    "unit_price": float(li.unit_price),
                    "amount": float(li.amount)
                }
                for li in invoice.line_items
            ]
        }

        return PDFInvoiceGenerator.generate(invoice_data)

    @classmethod
    def record_payment(
        cls,
        db: Session,
        invoice_id: str,
        payment_data: Dict[str, Any],
        admin_user_id: Optional[str] = None
    ) -> PaymentRecord:
        """
        Records a verified payment transaction against an invoice.
        """
        invoice = cls.get_invoice_by_id(db, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found.")

        return cls.payment_gateway.record_payment(
            db=db,
            invoice=invoice,
            amount=payment_data["amount"],
            reference=payment_data["payment_reference"],
            method=payment_data.get("payment_method", "BankTransfer"),
            notes=payment_data.get("notes"),
            verified_by_user_id=admin_user_id
        )
