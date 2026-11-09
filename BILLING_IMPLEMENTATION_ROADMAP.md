# DataForge – Billing & Usage-Based Monetization Roadmap

**Document Version:** 1.0.0  
**Status:** Approved Phased Execution Plan  
**Governing Charter:** [GEMINI.md](file:///home/fifity-five/projects/Dataforge/GEMINI.md) (Rule 2: Scope Control, Rule 9: Stop Gates)  

---

## 1. Roadmap Overview & Phasing Principles

To guarantee stability, zero regressions, and full compatibility with DataForge's control and execution planes, implementation follows a strict 10-phase sequence (Phases 0 through 9).

> [!IMPORTANT]
> In accordance with `GEMINI.md` Rule 9, the agent must pause at the conclusion of each phase, run the comprehensive verification suite, provide a detailed Phase Completion Report, and await explicit user approval before advancing to the next phase.

---

## 2. Phase-by-Phase Implementation Plan

### Phase 0 – Architecture Audit & Governance Alignment
- **Status:** **Active / In-Progress**
- **Objectives:**
  - Audit existing execution runner, database schema, user/RBAC structures, run models, and frontend navigation.
  - Establish the architectural blueprint, pricing model, roadmap, tracker, technical decisions, and test strategy.
  - Formulate schema additions and ensure zero breaking changes to existing 405 tests.
- **Deliverables:**
  - `BILLING_ARCHITECTURE.md`
  - `BILLING_PRICING_MODEL.md`
  - `BILLING_IMPLEMENTATION_ROADMAP.md`
  - `BILLING_IMPLEMENTATION_TRACKER.md`
  - `BILLING_TECHNICAL_DECISIONS.md`
  - `BILLING_TEST_STRATEGY.md`
- **Gate:** Stop and wait for user approval of Phase 0 audit before writing implementation code.

---

### Phase 1 – Dynamic Pricing & Subscription Configuration Engine
- **Objectives:**
  - Create database entities for `SubscriptionPlan`, `PricingConfigVersion`, and `CustomerSubscription`.
  - Create idempotent migration script in `backend/app/core/migrations.py`.
  - Populate default plans (Starter ₹9,999, Professional ₹29,999, Enterprise ₹99,999) and version 1 pricing rules.
  - Implement service layer `SubscriptionService` and Pydantic schemas.
  - Implement REST APIs: `GET /api/v1/billing/plans`, `GET /api/v1/billing/subscription`, `POST /api/v1/billing/subscription`.
  - Write unit tests validating plan configuration, pricing versions, and tenant subscription retrieval.
- **Gate:** Verify tests pass; await user approval.

---

### Phase 2 – Pipeline Usage Metering & Immutable Ledger Engine
- **Objectives:**
  - Create database entity `PipelineUsageLedger` with natural idempotency constraint on `pipeline_run_id`.
  - Implement `UsageMeteringEngine` with activity complexity classifier:
    - Basic: 2–5 activities (or single activity).
    - Standard: 6–15 activities.
    - Advanced: 16–30 activities.
    - Complex: 31+ activities.
  - Implement billability decision rules:
    - Succeeded $\rightarrow$ Billable.
    - Manual rerun $\rightarrow$ Billable.
    - Automatic internal retry $\rightarrow$ Non-billable extra charge.
    - Platform error (`SystemError`) $\rightarrow$ Non-billable.
    - Customer error (`UserError`) $\rightarrow$ Billable.
    - Cancelled before execution $\rightarrow$ Non-billable.
    - Pre-execution validation $\rightarrow$ Non-billable.
    - Child pipeline execution $\rightarrow$ Separate billable run.
  - Hook into `PipelineRunner.execute_sync()` in `backend/app/execution/runner.py` upon run completion.
  - Write unit and execution tests verifying usage records, idempotency, and classification across all scenarios.
- **Gate:** Verify tests pass; await user approval.

---

### Phase 3 – Rating & Usage Aggregation Engine
- **Objectives:**
  - Implement `RatingEngine` to evaluate usage ledger against subscription allowances and graduated rates.
  - Create `UsageAggregation` database entity for hourly, daily, and monthly rollups (`YYYY-MM`).
  - Calculate included allowance consumption vs overage runs:
    - Basic: ₹0.50 / run.
    - Standard: ₹1.50 / run.
    - Advanced: ₹3.00 / run.
    - Complex: Configurable rate.
  - Implement compute rating for Spark node-hours and execution engine affinity attribution.
  - Implement REST APIs: `GET /api/v1/billing/usage`, `GET /api/v1/billing/usage/summary`, `GET /api/v1/billing/usage/runs/{run_id}`.
  - Write unit and rating calculation tests.
- **Gate:** Verify tests pass; await user approval.

---

### Phase 4 – Billing Dashboard & Cost Management UI
- **Objectives:**
  - Add **Billing & Cost Management** navigation item in `StudioSidebar.tsx` and route in `App.tsx`.
  - Create unified `BillingPage.tsx` with sub-views:
    1. **Billing Overview:** Active plan badge, subscription fee, runs consumed vs included allowance, current month charges, previous month charges, next billing date.
    2. **Pipeline Usage Table:** Filterable by date range, pipeline, workspace, execution engine, status, and billability, with pagination.
    3. **Consumption Details:** ADF-parity visual consumption breakdown (Basic, Standard, Advanced, Spark, SQL Pushdown, Non-billable).
    4. **Cost Breakdown:** Clear segregation between DataForge Software, Additional Run Surcharges, Spark Compute, and BYOC Infrastructure.
  - Connect to backend APIs with loading, empty, and error states.
- **Gate:** Production build check; verify zero UI errors; await user approval.

---

### Phase 5 – Automated Invoicing, Tax & Payment Ledger Engine
- **Objectives:**
  - Create `BillingInvoice`, `InvoiceLineItem`, and `PaymentRecord` entities.
  - Implement monthly invoice generation service calculating subscription base, overage line items, GST (18%), and credits.
  - Implement downloadable PDF invoice generation using standard server-side rendering.
  - Implement extensible `BasePaymentGateway` with `OfflineBankTransferAdapter` and webhook handlers.
  - Implement REST APIs: `GET /api/v1/billing/invoices`, `GET /api/v1/billing/invoices/{id}`, `GET /api/v1/billing/invoices/{id}/download`.
  - Add Invoices and Payment History tab in `BillingPage.tsx`.
- **Gate:** Verify tests pass; await user approval.

---

### Phase 6 – Interactive Cost Estimator & Plan Comparison Calculator
- **Objectives:**
  - Implement interactive pricing calculator in backend service and frontend calculator component.
  - Inputs: Expected pipelines, monthly runs, average activities, Copy Engine %, Spark Engine %, SQL Pushdown %, data volume, runtime hours, deployment model (BYOC vs SaaS).
  - Outputs: Recommended plan, included runs, overage estimates, platform total, estimated infrastructure, and plan comparison matrix (Starter vs Professional vs Enterprise).
  - Add **Cost Estimator** tab in `BillingPage.tsx`.
- **Gate:** Verify calculation accuracy with empirical test suite; await user approval.

---

### Phase 7 – Budget Management, Threshold Alerts & Notification System
- **Objectives:**
  - Create `BudgetConfiguration` and `BudgetAlertRecord` entities.
  - Support workspace-level and project-level monthly spending limits and run count limits.
  - Implement threshold evaluators for 50%, 75%, 90%, and 100% budget consumption.
  - Integrate with `AlertEngine` to dispatch SMTP email, Slack, Teams, and in-platform notifications.
  - Add optional hard limit enforcement flag (warn-only by default; hard stop only if explicitly opted in).
  - Add Budget Management UI in `BillingPage.tsx`.
- **Gate:** Verify notification dispatch; await user approval.

---

### Phase 8 – Administrative Pricing, Discounts & Auditing Console
- **Objectives:**
  - Create administration-only pricing management section restricted via `require_role(["Admin"])`.
  - Capabilities: Update base plan prices, modify included allowances, change overage tiers, configure enterprise custom agreements, apply manual billing credits with audit logs.
  - Create `BillingAuditLog` table capturing admin ID, action, resource, timestamp, and before/after payloads.
  - Implement Admin Pricing Management tab in UI for administrative users.
- **Gate:** Verify RBAC enforcement and audit trail; await user approval.

---

### Phase 9 – End-to-End Validation, Chaos Testing & Final Hardening
- **Objectives:**
  - Run full end-to-end integration scenario: Pipeline Execution $\rightarrow$ Metering Ledger $\rightarrow$ Rating $\rightarrow$ Budget Alert $\rightarrow$ Invoicing.
  - Chaos & boundary testing:
    - Concurrent duplicate run events (idempotency validation).
    - SIGKILL / worker crash retry (duplicate charge prevention).
    - Malformed payload rating recovery.
    - Zero data leak between tenants (tenant isolation verification).
  - Run complete platform regression suite (all 405+ tests must pass).
  - Update all master documentation, changelogs, and architecture guides.
- **Gate:** Final Milestone Completion Report; deliver production-ready module.
