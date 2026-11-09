# DataForge – Billing & Usage-Based Monetization Technical Decisions (ADRs)

**Document Version:** 1.0.0  
**Status:** Approved Architectural Decision Records  
**Governing Charter:** [GEMINI.md](file:///home/fifity-five/projects/Dataforge/GEMINI.md)  

---

## Index of Decisions

- [ADR-B01: Dual-Layer Multi-Tenancy Hierarchy (Tenant vs Workspace)](#adr-b01-dual-layer-multi-tenancy-hierarchy)
- [ADR-B02: Immutable Append-Only Ledger for Usage Metering](#adr-b02-immutable-append-only-ledger)
- [ADR-B03: Idempotency Natural Key via PipelineRun ID](#adr-b03-idempotency-natural-key)
- [ADR-B04: Strict Separation of Software Charges from Cloud Infrastructure](#adr-b04-software-vs-cloud-infrastructure)
- [ADR-B05: Versioned Pricing Configurations with Effective Date Gating](#adr-b05-versioned-pricing-configurations)
- [ADR-B06: Extensible Payment Gateway Abstraction & Zero Mock Transactions](#adr-b06-extensible-payment-gateway-abstraction)
- [ADR-B07: Asynchronous Rating & Decoupled Execution Hook](#adr-b07-asynchronous-rating-and-execution-hook)
- [ADR-B08: Activity-Count Complexity Classification with Admin Override](#adr-b08-complexity-classification)

---

### ADR-B01: Dual-Layer Multi-Tenancy Hierarchy

**Context:**  
The existing DataForge database model isolates workloads at the `Workspace` level (`workspaces` table). However, enterprise customers frequently operate multiple workspaces (e.g. `Finance-Prod`, `Marketing-Analytics`, `Data-Platform-Sandbox`) that roll up to a single corporate entity for consolidated invoicing.

**Decision:**  
Introduce a `Tenant` (or `Organization`) entity that owns one or more `Workspaces`. To guarantee 100% backward compatibility with all existing pipelines, projects, and tests:
1. `workspaces` table gains an optional `tenant_id` foreign key.
2. In single-tenant or existing installations, a default tenant is automatically mapped to existing workspaces.
3. Billing subscriptions, invoices, and aggregated allowances are scoped to the `Tenant`, while budgets and usage filtering can be inspected at both the `Tenant` and `Workspace` levels.

**Consequences:**  
- Positive: Solves enterprise consolidated billing without breaking single-workspace operations.
- Negative: Requires one additional relationship traversal when resolving tenant from a pipeline run.

---

### ADR-B02: Immutable Append-Only Ledger

**Context:**  
Financial and enterprise usage data must be legally tamper-evident and audit-compliant. Updating usage rows in-place risks accounting discrepancies, lost history, and calculation disputes.

**Decision:**  
Implement `pipeline_usage_ledger` as an immutable append-only ledger. Once a run is recorded, its record is never updated or deleted. Corrections, billing refunds, or goodwill credits must be recorded as separate entries in a `billing_adjustments` table.

**Consequences:**  
- Positive: Absolute audit integrity; clean historical reconciliation.
- Negative: Storage grows linearly with runs; mitigated via daily/monthly summary aggregations (`usage_aggregations`).

---

### ADR-B03: Idempotency Natural Key via PipelineRun ID

**Context:**  
Distributed execution runtimes, worker retries, network dropped packets, or event replays can re-invoke run completion hooks. Duplicate metering records would result in double-billing customers.

**Decision:**  
Enforce a unique database constraint on `pipeline_usage_ledger.pipeline_run_id`. The metering engine executes an idempotent upsert/insert pattern (`INSERT ... ON CONFLICT (pipeline_run_id) DO NOTHING`).

**Consequences:**  
- Positive: Zero possibility of duplicate charges for the same execution.
- Negative: Requires pipeline runs to always possess a globally unique UUID.

---

### ADR-B04: Strict Separation of Software Charges from Cloud Infrastructure

**Context:**  
Azure Data Factory obscures charges between Data Flow vCore-hours, cluster startup delays, and pipeline activity charges. Hyperscalers also bill for storage and egress. In DataForge's Bring-Your-Own-Cloud (BYOC) deployment model, the customer already pays AWS, Azure, or GCP directly.

**Decision:**  
DataForge software invoices explicitly list **only** DataForge software charges (Subscription + Overage Run Surcharges + DataForge Managed SaaS Compute). Cloud provider costs (e.g. AWS S3 egress, Databricks compute) are categorized in a separate "Estimated Infrastructure" section of the UI and are never billed on DataForge invoices unless the customer opts into DataForge Managed SaaS.

**Consequences:**  
- Positive: Complete commercial transparency; prevents customer billing confusion.
- Negative: The UI must clearly label estimated infrastructure consumption vs actual DataForge fees.

---

### ADR-B05: Versioned Pricing Configurations with Effective Date Gating

**Context:**  
Commercial pricing changes over time (e.g. annual price increases, promotional tier adjustments). Modifying pricing rules must never retroactively change historical invoices or alter in-flight contracts.

**Decision:**  
Separate subscription plan metadata (`subscription_plans`) from versioned pricing rules (`pricing_config_versions`). Each version defines base prices, included run quotas, overage tiers, and currency, with `effective_from` and `effective_to` timestamps. Subscriptions hold a direct foreign key to their agreed pricing version.

**Consequences:**  
- Positive: Full historical reversibility; existing customers retain their grandfathered rates until renewal.
- Negative: Administrative updates require creating new version records rather than simple `UPDATE` statements.

---

### ADR-B06: Extensible Payment Gateway Abstraction & Zero Mock Transactions

**Context:**  
Enterprise customers pay via corporate purchase orders, bank wires (NEFT/RTGS/ACH), or automated credit card billing. The prompt strictly forbids fabricating or simulating fake successful payments.

**Decision:**  
Implement an extensible `BasePaymentGateway` interface:
1. `OfflineBankTransferAdapter` (Default): Generates proforma invoices, tracks corporate purchase orders, and records verified wire payments with admin approval audit logs.
2. `StripePaymentAdapter` / `RazorpayPaymentAdapter`: Extension adapters that initialize payment intents when credentials exist in `SecretVaultEntry`.
If no gateway is configured, invoices remain in `Issued` / `Pending Payment` state until verified via bank receipt.

**Consequences:**  
- Positive: Strictly truthful; enterprise compliant.
- Negative: Automated card checkout requires external gateway credentials.

---

### ADR-B07: Asynchronous Rating & Decoupled Execution Hook

**Context:**  
Pipeline performance and data movement speed must never be degraded by metering or billing calculations.

**Decision:**  
The execution hook in `PipelineRunner.execute_sync()` writes the raw telemetry record to the ledger at the conclusion of the run within the same final transaction as the status update. Complex monthly rating and overage calculations are performed asynchronously or upon dashboard read, ensuring zero execution latency overhead.

**Consequences:**  
- Positive: Near-zero overhead (< 2ms) added to pipeline run finalization.
- Negative: Usage rollups must handle near-real-time aggregation queries.

---

### ADR-B08: Activity-Count Complexity Classification with Admin Override

**Context:**  
Pipeline compute intensity correlates with activity graph complexity. Azure Data Factory charges flat activity fees regardless of graph complexity.

**Decision:**  
Classify pipelines based on the activity count defined in `definition_json.activities`:
- Basic: 2–5 activities (or single activity).
- Standard: 6–15 activities.
- Advanced: 16–30 activities.
- Complex: 31+ activities.
Administrators can override the classification for enterprise pipelines requiring custom pricing.

**Consequences:**  
- Positive: Fair, graduated pricing that reflects actual orchestration orchestration workload.
- Negative: Requires maintaining classification thresholds in versioned pricing configs.
