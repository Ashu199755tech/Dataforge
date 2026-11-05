# DataFlow Enterprise — Known Limitations & Technical Constraints

**Document Version:** 1.10.0  
**Last Updated:** 2026-11-05  

---

## 1. Resolved In Phases 1 Through 10

1. **In-Process Scripting & Process Isolation (Resolved in Phase 4):**
   - Python Script, Custom Activities, and Stored Procedures execute inside isolated sub-processes with real-time stdout streaming, timeout enforcement, and parameter injection.

2. **Distributed Compute Cluster Integration (Resolved in Phase 4):**
   - Clean-room Databricks Jobs REST API 2.1 integration and generic PySpark submission interfaces established.

3. **Hierarchical Control Flow & Sub-DAGs (Resolved in Phase 3):**
   - Hierarchical sub-DAGs, `ForEach` (sequential & parallel worker pools), `ExecutePipeline`, `Switch`, `Filter`, `Fail`, `AppendVariable`, and `Until` fully verified.

4. **Vectorized In-Memory Data Flows (Resolved in Phase 6):**
   - Dedicated visual Data Flow Designer with vectorized Polars multi-node execution graphs and intermediate node caching.

5. **Dynamic Expression Language (Resolved in Phase 7):**
   - Clean-room recursive descent tokenizer and parser supporting 35+ ADF-grade functions, system parameters, and string interpolation.

6. **Enterprise Data Quality & Governance (Resolved in Phase 8):**
   - Vectorized data quality validation (13 rules), PII detection, masking, statistical profiling, and source-to-target reconciliation.

7. **Real-time Observability & Telemetry (Resolved in Phase 9):**
   - Millisecond Gantt waterfall timeline, throughput telemetry (rows/s, MB/s), standard domain error classification, attempt retry histories, downloadable executive reports (JSON, CSV, TXT), and dynamic SLA alert rule evaluation.

8. **Enterprise Hardening & Security (Resolved in Phase 10):**
   - Role-Based Access Control (RBAC) across `Admin`, `Contributor`, `Operator`, and `Viewer` roles.
   - Enterprise AES-256 Fernet Secrets Vault with masked listings and zero-downtime key rotation.
   - Multi-environment promotion (Dev $\to$ Test $\to$ Prod) with parameter overrides and immutable version rollback.
   - Declarative Git JSON specification export/import with SHA-256 checksums.
   - Concurrency limit saturation guards (HTTP 429) and sliding 15-minute idempotency deduplication.
   - Automated dead-worker orphan recovery upon startup and on-demand via REST API.
   - Tamper-evident centralized audit logging across all administrative and mutation operations.

---

## 2. Final Milestone Focus: Phase 11 (End-to-End Validation Scenarios)

1. **End-to-End Acceptance Scenarios Verification:**
   - Execute the 8 exhaustive end-to-end integration scenarios defined in Section 16 under live multi-database and real-time streaming conditions.
   - Validate end-to-end data fidelity, error recovery, and output verification to achieve 100% full platform validation.

