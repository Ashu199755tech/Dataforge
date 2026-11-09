# DataForge – Billing & Usage-Based Monetization Tracker

**Document Version:** 1.0.0  
**Last Updated:** 2026-11-09  
**Governing Charter:** [GEMINI.md](file:///home/fifity-five/projects/Dataforge/GEMINI.md)  

---

## 1. Master Execution Ledger

| Phase | Milestone Name | Commit | Status | Tests Passed | Completed Date |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Phase 0** | **Architecture Audit & Governance Alignment** | `d8a74b0` | **Completed** | 405 Passed (Baseline) | 2026-11-09 |
| **Phase 1** | **Dynamic Pricing & Subscription Configuration Engine** | `4735d36` | **Completed** | 6 / 6 Passed (Billing Suite) | 2026-11-09 |
| **Phase 2** | **Pipeline Usage Metering & Immutable Ledger Engine** | `a926496` | **Completed** | 6 / 6 Passed (12/12 Billing Total) | 2026-11-09 |
| **Phase 3** | **Rating & Usage Aggregation Engine** | `18fc461` | **Completed** | 4 / 4 Passed (16/16 Billing Total) | 2026-11-09 |
| **Phase 4** | **Billing Dashboard & Cost Management UI** | `95557ee` | **Completed** | 16 / 16 Billing + Frontend Build Verified | 2026-11-09 |
| **Phase 5** | **Automated Invoicing, Tax & Payment Ledger Engine** | `2f1012b` | **Completed** | 5 / 5 Passed (21/21 Billing Total) | 2026-11-09 |
| **Phase 6** | **Interactive Cost Estimator & Plan Comparison Calculator** | `6df92a2` | **Completed** | 6 / 6 Passed (27/27 Billing Total) | 2026-11-09 |
| **Phase 7** | **Budget Management, Threshold Alerts & Notification System** | `04ff9b8` | **Completed** | 5 / 5 Passed (32/32 Billing Total) | 2026-11-09 |
| **Phase 8** | **Administrative Pricing, Discounts & Auditing Console** | `50da3ef` | **Completed** | 5 / 5 Passed (37/37 Billing Total) | 2026-11-09 |
| **Phase 9** | **End-to-End Validation, Chaos Testing & Final Hardening** | `HEAD` | **Completed** | 5 / 5 Passed (42/42 Billing Total) | 2026-11-09 |

---

## 2. Phase 0 Audit Artifacts Checklist
- [x] Audit existing execution framework, database schema, and frontend navigation.
- [x] Create `BILLING_ARCHITECTURE.md`: Subsystem architecture, data models, state machines.
- [x] Create `BILLING_PRICING_MODEL.md`: Commercial tiers, run overages, compute multipliers, BYOC boundaries.
- [x] Create `BILLING_IMPLEMENTATION_ROADMAP.md`: 10-phase sequence and stop-gate criteria.
- [x] Create `BILLING_IMPLEMENTATION_TRACKER.md`: Active milestone execution ledger.
- [x] Create `BILLING_TECHNICAL_DECISIONS.md`: Architectural Decision Records (ADRs).
- [x] Create `BILLING_TEST_STRATEGY.md`: Test matrix, boundary cases, idempotency & chaos coverage.
- [x] Phase 0 approved by user.

---

## 3. Phase 1 Implementation Checklist
- [x] Create `Tenant`, `SubscriptionPlan`, `PricingConfigVersion`, and `CustomerSubscription` SQLAlchemy models.
- [x] Implement schema migration script updating `workspaces.tenant_id`.
- [x] Create Pydantic v2 validation schemas with `ConfigDict(from_attributes=True)`.
- [x] Implement `BillingService` seeding default plans (Starter ₹9,999, Professional ₹29,999, Enterprise ₹99,999) and active pricing versions.
- [x] Register `/api/v1/billing` REST endpoints (`GET /plans`, `GET /plans/{id}`, `GET /subscription`, `POST /subscription`, `GET /overview`).
- [x] Wire up frontend sidebar navigation with `Billing & Cost Management` icon under Manage group.
- [x] Implement complete `BillingPage.tsx` with Overview, Plans & Tiers, Usage Ledger, Consumption, Software vs Cloud Breakdown, Invoices, and Interactive Cost Estimator.
- [x] Run test suite: 6/6 tests passed in `test_billing_plans.py`.
- [x] Run frontend build: 0 TypeScript errors.

---

## 4. Phase 2 Implementation Checklist
- [x] Create `PipelineUsageLedger` entity with unique idempotency constraint on `pipeline_run_id`.
- [x] Implement `UsageMeteringEngine` with activity count complexity classification (Basic, Standard, Advanced, Complex).
- [x] Implement execution engine detection (CopyEngine, SparkEngine, SqlPushdownEngine, Hybrid).
- [x] Implement fault-tolerant billability rules (PlatformSystemError non-billable; Customer errors billable).
- [x] Hook `UsageMeteringEngine.record_pipeline_execution()` directly into `PipelineRunner.execute_sync()` upon run completion.
- [x] Implement administrative billability manual override with tamper-evident audit logging.
- [x] Expose REST APIs: `GET /api/v1/billing/usage`, `GET /api/v1/billing/usage/{run_id}`, `POST /api/v1/billing/usage/{ledger_id}/override`.
- [x] Update frontend usage ledger view with engine, classification, and billability filters.
- [x] Add automated test suite `test_usage_metering.py` (6/6 passed).
- [x] Full regression test run: 417 passed, 0 failures.

---

## 5. Phase 3 Implementation Checklist
- [x] Create `UsageAggregation` database entity for monthly, daily, and hourly rollups.
- [x] Implement `RatingEngine` evaluating usage ledger records against versioned subscription allowances.
- [x] Implement graduated overage rating schedule (Basic ₹0.50, Standard ₹1.50, Advanced ₹3.00, Complex ₹5.00).
- [x] Implement compute consumption rating for Spark worker node-hours (₹45.00 / hr) and SQL Pushdown zero egress.
- [x] Implement daily aggregation rollups (`get_daily_consumption`) for chronological trend charts.
- [x] Register REST APIs: `GET /api/v1/billing/usage/summary`, `GET /api/v1/billing/usage/daily`, `POST /api/v1/billing/usage/recalculate`.
- [x] Connect frontend Consumption Details tab to live `/api/v1/billing/usage/summary` and `/api/v1/billing/usage/daily`.
- [x] Add automated test suite `test_rating_engine.py` (4/4 passed).
- [x] Full platform regression suite: 421 passed, 0 failures.
- [x] Frontend production build: 0 TypeScript errors.

---

## 6. Phase 4 Implementation Checklist
- [x] Integrate interactive Recharts visualizer in Consumption Details (stacked bar chart by complexity tier & execution engine with dark tooltip styling).
- [x] Implement slide-over Run Details Drawer displaying run telemetry, byte/row metrics, billability rationale, and itemized surcharge breakdown.
- [x] Implement administrative billability toggle (Waive / Reinstate) inside the Run Details Drawer with reason prompt.
- [x] Build multi-attribute filter toolbar for Usage Ledger: search query (pipeline name & run ID), engine dropdown, classification tier, billability status, and date range filters (Today, 7d, 30d, All).
- [x] Implement client-side pagination (15 items/page) with entry counters and previous/next page navigation controls.
- [x] Implement browser export capabilities: CSV export for Usage Ledger and formatted JSON export for Consumption Summary.
- [x] Verify complete frontend build (`tsc && vite build`) with zero compiler errors.

---

## 7. Phase 5 Implementation Checklist
- [x] Create `BillingInvoice`, `InvoiceLineItem`, and `PaymentRecord` entities in `backend/app/models/billing.py`.
- [x] Implement `InvoiceService` with monthly invoice generator, 18.00% GST tax calculation, itemized line items, and allowance reconciliation.
- [x] Enforce idempotent monthly invoice generation preventing duplicate statements.
- [x] Build pure standard library ISO 32000-1 PDF statement generator (`PDFInvoiceGenerator`) with zero unapproved third-party dependencies.
- [x] Implement extensible `BasePaymentGateway` with `OfflineBankTransferAdapter` recording verified wire transfers / POs with tamper-evident audit logs.
- [x] Expose REST APIs: `GET /api/v1/billing/invoices`, `POST /api/v1/billing/invoices/generate`, `GET /api/v1/billing/invoices/{id}`, `GET /api/v1/billing/invoices/{id}/download`, `POST /api/v1/billing/invoices/{id}/payments`.
- [x] Implement interactive Invoices & Statements tab in `BillingPage.tsx` with live invoice table, PDF download, invoice details drawer, and payment recording modal.
- [x] Add automated test suite `test_invoicing_service.py` (5/5 passed).
- [x] Full regression test run: 426 passed, 3 skipped, 0 failures.
- [x] Frontend production build: 0 TypeScript errors (6.83s).

---

## 8. Phase 6 Implementation Checklist
- [x] Implement deterministic sizing and workload modeling service `CostEstimatorService` in `backend/app/services/cost_estimator_service.py`.
- [x] Support full parameter matrix: active pipelines, monthly runs, activities per pipeline, engine distribution (Copy, Spark, SQL Pushdown), data volume, compute hours, deployment model (BYOC vs SaaS), and term (Monthly vs Annual).
- [x] Generate side-by-side comparison matrix across Starter (₹9,999), Professional (₹29,999), and Enterprise (₹99,999) with effective per-run unit economics.
- [x] Provide ADF equivalent TCO benchmark and realistic savings percentage calculation.
- [x] Enforce BYOC 0% cloud markup transparent disclosure and stated pricing assumptions.
- [x] Expose REST API: `POST /api/v1/billing/estimate`.
- [x] Implement comprehensive interactive Cost Estimator tab in `BillingPage.tsx` with dual-column layout, dynamic sliders, side-by-side tier comparison table, and one-click plan subscription buttons.
- [x] Add automated test suite `test_cost_estimator.py` (6/6 passed).
- [x] Full platform regression suite: 432 passed, 3 skipped, 0 failures in 69.37s.
- [x] Frontend production build: 0 TypeScript errors (4.35s).

---

## 9. Phase 7 Implementation Checklist
- [x] Create budget models `BudgetConfiguration` and `BudgetAlertRecord` in `backend/app/models/billing.py` with multi-tenant and workspace scoping.
- [x] Expose Pydantic validation schemas in `backend/app/schemas/billing.py`: `BudgetConfigurationCreate`, `BudgetConfigurationUpdate`, `BudgetAlertRecordResponse`, `BudgetStatusResponse`, `BudgetEvaluationResult`.
- [x] Implement deterministic budget monitoring engine `BudgetService` in `backend/app/services/budget_service.py` with spend aggregation, run count aggregation, threshold detection (50%, 75%, 90%, 100%), and alert deduplication to prevent notification spam.
- [x] Hook real-time execution prevention guardrail `BudgetService.check_execution_allowed` directly into `PipelineRunner.execute_sync` with hard limit enforcement.
- [x] Wire alert dispatch into platform `AlertEngine` with fallback channel simulation (email, slack, webhook).
- [x] Expose REST APIs in `backend/app/api/billing.py`: `GET/POST /budgets`, `GET/PUT/DELETE /budgets/{id}`, `POST /budgets/evaluate`.
- [x] Implement interactive Budgets & Threshold Alerts tab in `BillingPage.tsx` with spending/run utilization gauges, color-coded threshold pills, hard stop warning banner, recipient pills, and create/edit budget modal.
- [x] Add automated test suite `test_budget_alerts.py` (5/5 passed).
- [x] Full platform regression suite: 437 passed, 3 skipped, 0 failures.
- [x] Frontend production build: 0 TypeScript errors.

---

## 10. Phase 8 Implementation Checklist
- [x] Create `BillingAuditLog` model in `backend/app/models/billing.py` capturing `admin_user_id`, `admin_email`, `action`, `resource_type`, `resource_id`, `before_state`, `after_state`, and `justification`.
- [x] Expose Pydantic validation schemas in `backend/app/schemas/billing.py`: `PricingVersionCreate`, `CustomEnterpriseAgreementRequest`, `BillingAdjustmentRequest`, `BillingAuditLogResponse`.
- [x] Implement administrative pricing governance service `AdminPricingService` in `backend/app/services/admin_pricing_service.py`:
  - `publish_new_pricing_version`: version incrementing, immutable validity windows (`effective_from`, `effective_to`), past invoices untouched.
  - `configure_custom_enterprise_agreement`: bespoke volume tiers, custom quotas, tenant subscription binding.
  - `apply_invoice_adjustment`: manual SLA goodwill credits/deductions, subtotal & 18% tax recalculation.
  - `list_audit_logs`: paginated audit history retrieval.
- [x] Expose RBAC-guarded REST APIs (`require_role(["Admin"])`):
  - `GET /api/v1/billing/admin/plans`
  - `POST /api/v1/billing/admin/plans/{id}/pricing-versions`
  - `POST /api/v1/billing/admin/custom-agreement`
  - `POST /api/v1/billing/admin/invoices/{id}/adjustments`
  - `GET /api/v1/billing/admin/audit-logs`
- [x] Implement Admin Pricing & Audit Console tab in `BillingPage.tsx` with tier version management, custom enterprise agreement creator, manual invoice adjustment tool, and audit state diff inspector.
- [x] Add automated test suite `backend/tests/test_admin_pricing_audit.py` (5/5 passed).
- [x] Full platform regression suite: 442 passed, 3 skipped, 0 failures.
- [x] Frontend production build: 0 TypeScript errors.

---

## 11. Phase 9 Implementation Checklist
- [x] Create comprehensive E2E & Chaos validation test suite `backend/tests/test_billing_e2e_chaos.py`:
  - `test_full_e2e_billing_monetization_lifecycle`: End-to-end monetization flow (Pipeline execution $\rightarrow$ automated usage metering ledger $\rightarrow$ rating engine periodic rollup $\rightarrow$ budget evaluation $\rightarrow$ monthly invoice with 18% GST $\rightarrow$ offline bank wire remittance $\rightarrow$ standard ISO 32000-1 PDF statement generation).
  - `test_chaos_concurrent_duplicate_metering_prevention`: 10 concurrent threads attempting duplicate metering on the same pipeline run simultaneously; strict serialization by unique database constraint; exactly 1 billable ledger entry created.
  - `test_chaos_worker_crash_and_retry_zero_duplicate_charge`: Worker crash with Fatal engine error/WorkerCrash classified as non-billable zero charge; subsequent manual/system retry billable; total charges exactly 1x.
  - `test_strict_multi_tenant_isolation`: Tenant A cannot see or access Tenant B's invoices or budgets via REST endpoints; direct ID access responds 404.
  - `test_malformed_corrupted_payload_recovery`: Malformed/empty pipeline definition runs without crashing rating or metering engines.
- [x] Harden multi-tenant isolation in `backend/app/api/billing.py` for `get_invoice_details`, `download_invoice_pdf`, and `get_budget_status`.
- [x] Run billing test suite: 42/42 tests passed across Phases 1–9 (`test_billing_plans.py`, `test_usage_metering.py`, `test_rating_engine.py`, `test_invoicing_service.py`, `test_cost_estimator.py`, `test_budget_alerts.py`, `test_admin_pricing_audit.py`, `test_billing_e2e_chaos.py`).
- [x] Run full platform regression test suite: 447 passed, 3 skipped, 0 failures in 83.75s.
- [x] Verify frontend build cleanliness: 0 TypeScript errors, clean Vite production bundle generated.
- [x] Module completion: All 10 phases (0 through 9) completed, verified, and production-ready.




