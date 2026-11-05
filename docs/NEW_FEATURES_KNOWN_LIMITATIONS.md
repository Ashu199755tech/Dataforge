# DataForge — Six New Enterprise Features: Known Limitations & Boundaries

## 1. Overview

This document establishes the technical boundaries, intentional design constraints, and operational guidelines for the six new enterprise modules.

---

## 2. Feature-by-Feature Technical Boundaries

### Feature 1: Integration Runtime Manager
1. **Outbound-Only Communication:** Self-Hosted Integration Runtime (SHIR) agents operate strictly via outbound HTTPS polling and webhooks to the DataForge Control Plane. No inbound firewall rules or public IP addresses are required on agent nodes.
2. **Agent Host Capacity:** Concurrency limit is bounded by the host machine's hardware profile (CPU cores, RAM). When an agent reaches its configured concurrency limit, tasks remain safely queued in the control plane until capacity is freed.
3. **Heartbeat Grace Period:** If an agent fails to report a heartbeat within 60 seconds (due to machine restart or network drop), the control plane transitions its status to `Offline` and triggers failover / recovery policies.

### Feature 2: Reusable Dataset Management
1. **Preview Memory Boundary:** The dataset preview endpoint strictly limits sample retrieval to between 10 and 100 rows. Files larger than 2MB are read with streaming chunking to guarantee bounded server memory.
2. **Schema Drift Thresholds:** Schema drift detection reports added columns as non-breaking, but flags dropped or mutated data type columns as breaking changes requiring explicit operator acknowledgement.
3. **Expression Evaluation Scope:** Parameterized datasets (e.g. `@{formatDateTime(pipeline().parameters.WindowStart, 'yyyy/MM')}`) are evaluated within the active pipeline run's execution context.

### Feature 3: Advanced Trigger Management
1. **Storage Event Ingestion Modes:** Supports both push-based cloud webhook arrival events (AWS EventBridge, Azure Event Grid, GCP PubSub) and pull-based polling for isolated environments.
2. **Tumbling Window Backfill Limits:** Tumbling window backfill is bounded to a maximum of 100 historical windows per execution to prevent server resource starvation.
3. **Circular Dependency Detection:** Dependency triggers inspect the dependency graph across all pipelines using Tarjan's cycle-finding algorithm to prevent infinite execution loops.

### Feature 4: Git Integration & CI/CD
1. **Secret Stripping Rule:** Sensitive connection credentials, passwords, and tokens are **never** exported into Git repositories. All resources reference connection IDs or environment substitution tokens.
2. **Conflict Resolution Policy:** If remote Git changes conflict with local changes, the engine detects conflicts and requires a branch pull or manual resolution; it never executes destructive automatic merges.
3. **Supported Providers:** Initial implementation provides first-class support for GitHub via REST API and standard Git protocols, with extensible interfaces designed for future GitLab support.

### Feature 5: Data Lineage & Impact Analysis
1. **Static vs. Dynamic Analysis:** Lineage is statically determined from pipeline activity configurations, Copy Data column mappings, and Data Flow DAGs.
2. **Partial / Unknown Lineage Handling:** Custom Python scripts (`CustomActivity`) or unparseable raw dynamic SQL statements are explicitly labeled as `Lineage: Partial / Unknown` rather than guessing or generating hallucinated column relationships.

### Feature 6: Advanced Monitoring & Observability
1. **Prometheus Metrics Endpoint:** Exposes standard `/metrics` in Prometheus format. Scraping intervals should be configured between 10s and 60s.
2. **Log Retention:** Historical execution logs older than the configured retention policy (default: 30 days) are archived or pruned to maintain database performance.
3. **Trace Header Propagation:** Distributed tracing adheres to W3C `traceparent` standards, propagating correlation IDs from trigger event through pipeline execution to worker tasks.

---

## 3. Enterprise Production Operational Guidelines

1. **Self-Hosted Agent High Availability:** For mission-critical private-network access, deploy at least 2 active self-hosted agent nodes per environment with shared runtime keys to guarantee zero-downtime task pickup if one node restarts.
2. **Alert Flood Suppression:** Use a minimum `cooldown_minutes` of 10–15 minutes on high-frequency pipelines to prevent alert fatigue across Slack and Microsoft Teams webhooks.
3. **Database Maintenance & Index Health:** High-frequency agent heartbeat and task polling queries utilize dedicated B-Tree indices on `(runtime_id, status)` and `(alert_rule_id, status)`. Maintain standard periodic vacuum and query analyzer runs on PostgreSQL/MySQL.
4. **Git CI/CD Promotion Workflows:** Restricted target environments (`Production`) strictly enforce the `PendingApproval` gate, requiring an independent approver before assets are promoted.
