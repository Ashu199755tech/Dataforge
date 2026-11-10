# DataForge – Changelog

All notable changes to the DataForge Enterprise Platform are documented in this file.

---

## [1.5.0] - 2026-11-10 - Enterprise CI/CD Pipeline & Production Rollout (Render & Supabase)

### Added
- **Multi-Environment GitHub Actions Pipeline (`ci-cd.yml`):**
  - Automated Quality Gate running on all pushes and PRs to `master`, `main`, `test`, and `dev`.
  - Python 3.12 dependency caching, system library provisioning (`gcc`, `libpq-dev`), and full backend test execution.
  - Node.js 20 environment, dependency caching, and strict frontend production build verification (`tsc && vite build`).
  - Production deployment stage triggered automatically upon merge/push to `master`, communicating directly with Render Deployment REST API and performing healthcheck validation.
- **Test Suite Portability & Concurrency Hardening:**
  - File-backed SQLite connection pooling in `database.py` resolving SQLite multi-threaded segfaults during headless CI.
  - Test guards for external services (live daemon socket check, Azurite emulator detection, Moto S3 fallback, Java runtime version flexibility, and CRC32C fallback calculations).
- **Production Infrastructure Integration:**
  - Live production web service on Render (`https://dataforge-15mi.onrender.com`).
  - Production PostgreSQL database integration hosted on Supabase (`aws-0-ap-south-1.pooler.supabase.com`).

---

## [1.4.0] - 2026-11-09 - Pricing, Billing & Usage-Based Monetization Module (Phases 0–9)

### Added
- **Phase 0: Governance & Architecture**
  - Architecture blueprint, pricing model, technical decisions, roadmap, and test strategy documentation.
- **Phase 1: Commercial Tiers & Dynamic Pricing Models**
  - Database models: `Tenant`, `SubscriptionPlan`, `PricingConfigVersion`, and `CustomerSubscription`.
  - Default commercial plans: Starter (₹9,999/mo), Professional (₹29,999/mo), Enterprise (₹99,999/mo).
  - Versioned pricing configs (`PricingConfigVersion`) ensuring historical billing immutability.
  - REST endpoints: `/api/v1/billing/plans`, `/api/v1/billing/subscription`, `/api/v1/billing/overview`.
- **Phase 2: Usage Metering & Immutable Ledger Engine**
  - `PipelineUsageLedger` database entity with unique constraint on `pipeline_run_id` guaranteeing strict idempotency.
  - Complexity classification: Basic (1–5 activities, ₹0.50), Standard (6–15, ₹1.50), Advanced (16–30, ₹3.00), Complex (31+, ₹5.00).
  - Engine detection: CopyEngine, SparkEngine, SqlPushdownEngine, Hybrid.
  - Automated hook into `PipelineRunner.execute_sync()` upon run completion.
  - Fault-tolerant billability rules: platform worker crashes are non-billable; customer errors are billable.
  - Administrative override endpoints with tamper-evident audit logging.
- **Phase 3: Rating & Usage Aggregation Engine**
  - `UsageAggregation` database entity for monthly and daily rollups.
  - High-performance `RatingEngine` for quota allowance subtraction, graduated overage tier rating, and Spark compute node-hours (₹45.00/hr).
  - Daily trend aggregation APIs and consumption summaries.
- **Phase 4: Billing Dashboard & Cost Management UI**
  - Recharts visualizer: stacked bar chart for execution engine and complexity tier distributions.
  - Telemetry slide-over drawer: detailed run metrics, byte/row counts, and itemized surcharges.
  - Filter toolbar with multi-attribute filtering (engine, tier, status, date presets) and client-side pagination.
  - Browser exports: CSV export for usage ledgers and JSON export for consumption summaries.
- **Phase 5: Automated Invoicing, 18% GST & Standard PDF Generation**
  - Invoicing entities: `BillingInvoice`, `InvoiceLineItem`, and `PaymentRecord`.
  - Monthly commercial statement generator with 18.00% Indian GST tax computation.
  - Pure standard library ISO 32000-1 PDF statement generator (`PDFInvoiceGenerator`) with zero unapproved third-party dependencies.
  - `OfflineBankTransferAdapter` for corporate PO / UTR wire settlements with tamper-evident audit records.
- **Phase 6: Interactive Cost Estimator & Plan Comparison Calculator**
  - Deterministic sizing service `CostEstimatorService` covering 9 workload parameters.
  - Side-by-side tier comparison matrix (Starter, Professional, Enterprise) with effective per-run economics.
  - ADF equivalent TCO benchmark and realistic cost savings calculation.
  - BYOC mode transparency with 0% cloud compute markup guarantee.
- **Phase 7: Budget Management, Threshold Alerts & Execution Guardrails**
  - Budget models: `BudgetConfiguration` and `BudgetAlertRecord` with multi-tenant and workspace scoping.
  - Utilization gauges, threshold alerts (50%, 75%, 90%, 100%), and notification deduplication.
  - Real-time execution guardrail `BudgetService.check_execution_allowed()` inside `PipelineRunner.execute_sync()` enforcing hard budget limits.
- **Phase 8: Administrative Pricing, Discounts & Auditing Console**
  - `BillingAuditLog` capturing before/after states, justification, and administrator IDs.
  - `AdminPricingService`: version publishing, bespoke enterprise agreements, SLA credit adjustments.
  - RBAC security (`require_role(["Admin"])`) guarding all administrative actions.
- **Phase 9: End-to-End Validation, Chaos Testing & Hardening**
  - Complete monetization lifecycle verification (execution $\rightarrow$ metering $\rightarrow$ rating $\rightarrow$ budgets $\rightarrow$ invoicing $\rightarrow$ payment remittance $\rightarrow$ PDF statement).
  - Chaos concurrency testing: 10 concurrent threads serialized by unique database constraint with zero duplicate billing.
  - Chaos resilience: worker crash SIGKILL recovery with zero duplicate charges on retried execution.
  - Strict multi-tenant isolation: workspace-scoped authorization preventing cross-tenant data exposure.

---

## [1.3.0] - 2026-11-09 - Modern Data Stack & Analytical Warehouses
- Analytical connectors: Snowflake, DuckDB, Google BigQuery, AWS Redshift.
- Transformations: dbt activity integration.
- Replication: Incremental CDC stream engine (Debezium/WAL) and Reverse ETL (Salesforce, HubSpot, Slack).

## [1.2.0] - 2026-11-06 - Intelligent Execution Engine
- Specialized engines: CopyEngine (parallel streaming), SparkEngine (PySpark), and SQL Pushdown Engine (zero-egress ELT).
- Heuristic and cost-based Execution Planner.

## [1.1.0] - 2026-11-05 - Core DataFlow Platform
- Visual DAG designer, dynamic activity framework, monitoring, and RBAC security vault.
