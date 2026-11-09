# DataForge – Billing & Usage-Based Monetization Test Strategy

**Document Version:** 1.0.0  
**Status:** Approved Test Strategy  
**Governing Charter:** [GEMINI.md](file:///home/fifity-five/projects/Dataforge/GEMINI.md) (Rule 8: Mandatory Testing Requirements)  

---

## 1. Test Philosophy & Quality Guardrails

The **DataForge Billing & Usage-Based Monetization Module** is financially sensitive. A bug in metering or rating directly impacts customer revenue, platform trust, and compliance.

In strict adherence to `GEMINI.md` Rule 8:
- No feature is marked complete based only on code compilation.
- All numbers, rates, and row counts in tests must be derived empirically from executed code.
- Full regression verification must be executed at each phase gate (all 405+ existing tests must pass).

---

## 2. Test Pyramid & Coverage Matrix

```
                 / \
                /   \     E2E Lifecycle & Chaos Tests (Phase 9)
               /-----\    Integration Tests: Runner & Database (Phases 2, 3, 5, 7)
              /       \   API Contract & Security Tests (Phases 1, 3, 5, 8)
             /---------\  Unit Tests: Rating, Classifiers, Rules (Phases 1, 2, 3)
```

---

## 3. Detailed Scenario Test Specifications

### Category 1: Pipeline Complexity Classification
- **TC-CLS-01 (Basic Tier):** Pipeline with 1 to 5 activities (e.g. Copy Data + Webhook) is classified as `Basic`.
- **TC-CLS-02 (Standard Tier):** Pipeline with 6 to 15 activities (e.g. 8 activity ETL pipeline) is classified as `Standard`.
- **TC-CLS-03 (Advanced Tier):** Pipeline with 16 to 30 activities is classified as `Advanced`.
- **TC-CLS-04 (Complex Tier):** Pipeline with 31+ activities is classified as `Complex`.
- **TC-CLS-05 (Admin Override):** Pipeline with 2 activities flagged with administrative override is rated under its custom classification.

### Category 2: Billability State Machine Rules
- **TC-BIL-01 (Successful Run):** Succeeded pipeline run generates a ledger record with `is_billable = True` and `non_billable_reason = None`.
- **TC-BIL-02 (Manual User Rerun):** Rerunning an existing pipeline generates a new unique `pipeline_run_id` and a distinct billable ledger entry.
- **TC-BIL-03 (Internal Worker Retry):** An activity that fails and retries 3 times within the same `PipelineRun` incurs **zero additional orchestration run charge**.
- **TC-BIL-04 (Platform Infrastructure Failure):** Pipeline failing with `error_classification = 'SystemError'` generates `is_billable = False` with `non_billable_reason = 'PlatformSystemError'` and ₹0.00 charge.
- **TC-BIL-05 (Customer Configuration Failure):** Pipeline failing with `error_classification = 'UserError'` (e.g. bad SQL syntax, missing table) generates `is_billable = True` because compute was initiated.
- **TC-BIL-06 (Cancelled Before Execution):** Run cancelled in `Pending` state produces `is_billable = False` with `non_billable_reason = 'CancelledBeforeStart'`.
- **TC-BIL-07 (Cancelled During Execution):** Run cancelled while in `Running` state produces `is_billable = True` with `non_billable_reason = 'CancelledDuringRun'`.
- **TC-BIL-08 (Child Pipeline Execution):** Executing `ExecutePipelineActivity` creates a sub-pipeline run with its own unique `pipeline_run_id` and independent billable ledger record.
- **TC-BIL-09 (Pre-Execution Validation):** DAG validation check via API endpoint executes with ₹0.00 charge and zero ledger entry.

### Category 3: Idempotency & Duplicate Billing Prevention
- **TC-IDP-01 (Sequential Duplication):** Attempting to insert a ledger record with an existing `pipeline_run_id` is safely ignored with zero duplicate records created.
- **TC-IDP-02 (Concurrent Race Condition):** Multi-threaded concurrent calls attempting to meter the same run are serialized by the unique database constraint.
- **TC-IDP-03 (Worker Replay / Event Bus):** Replaying event bus messages for already metered runs creates no secondary charges.

### Category 4: Pricing & Subscription Allowance Rating
- **TC-RAT-01 (Starter Plan Under Allowance):** 7,500 basic runs on Starter Plan (10,000 allowance) results in ₹9,999 base fee and ₹0.00 overage charges.
- **TC-RAT-02 (Starter Plan Overage):** 12,000 basic runs on Starter Plan incurs ₹9,999 base fee + (2,000 $\times$ ₹0.50) = ₹10,999 total.
- **TC-RAT-03 (Mixed Complexity Overage):** 5,000 runs exceeding allowance with 3,000 Basic (₹0.50), 1,500 Standard (₹1.50), and 500 Advanced (₹3.00) calculates exact graduated sum.
- **TC-RAT-04 (Spark Engine Surcharges):** Spark runs in SaaS mode accurately compute worker node-hours based on duration and node type.
- **TC-RAT-05 (SQL Pushdown Surcharges):** SQL Pushdown runs bill at standard activity rates with zero cloud egress markup.

### Category 5: Invoicing, Taxes & Billing Adjustments
- **TC-INV-01 (Monthly Invoice Calculation):** Generates itemized line items: Base subscription, Basic overage, Standard overage, 18% GST tax, and net total.
- **TC-INV-02 (Tax Exemption):** Tenant with verified international VAT/tax identifier calculates 0% export tax.
- **TC-INV-03 (Billing Credits / Adjustments):** Credit applied via `BillingAdjustment` reduces invoice balance without altering underlying immutable usage ledger.
- **TC-INV-04 (Historical Pricing Immobility):** Creating a new pricing version (v2) leaves previously generated invoices (v1) completely unchanged.

### Category 6: Budget Management & Threshold Alerts
- **TC-BDG-01 (50% Threshold):** When month-to-date spending crosses 50% of monthly budget limit, a notification event is dispatched.
- **TC-BDG-02 (75% & 90% Thresholds):** Escalating warning notifications are dispatched as usage progresses.
- **TC-BDG-03 (100% Threshold - Soft Limit):** At 100% budget, alert is issued; pipelines continue executing normally (no unexpected production stoppage).
- **TC-BDG-04 (100% Threshold - Hard Limit):** If customer explicitly enabled `enforce_hard_limit = True`, new pipeline runs are rejected with structured budget limit error.

### Category 7: Tenant Isolation & RBAC Security
- **TC-SEC-01 (Cross-Tenant Data Isolation):** Tenant A cannot retrieve, view, or aggregate Tenant B's usage ledger, subscription, or invoices.
- **TC-SEC-02 (RBAC Pricing Modification):** Non-Admin user attempting to create or modify pricing plans receives `HTTP 403 Forbidden`.
- **TC-SEC-03 (Viewer Access):** Viewer role can inspect their workspace usage but cannot modify subscriptions or budgets.

### Category 8: Full End-to-End Execution Flow
- **TC-E2E-01:**
  1. Trigger pipeline execution through `PipelineRunner`.
  2. Verify pipeline run completes.
  3. Verify `PipelineUsageLedger` entry is created with exact duration, rows, and engine classification.
  4. Verify monthly usage aggregation updates.
  5. Verify invoice preview reflects accurate cost.

---

## 4. Test Execution Commands & Milestones

All test suites will be located in `backend/tests/`:
- `backend/tests/test_billing_models.py`
- `backend/tests/test_usage_metering.py`
- `backend/tests/test_billing_rating.py`
- `backend/tests/test_invoicing_engine.py`
- `backend/tests/test_budget_alerts.py`
- `backend/tests/test_billing_security.py`

Command to execute billing test suite:
```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/test_billing*.py -v
```

Command to execute full regression suite:
```bash
PYTHONPATH=. ./venv/bin/pytest backend/tests/ -q
```
All existing 405 tests must pass alongside newly created tests at every milestone gate.
