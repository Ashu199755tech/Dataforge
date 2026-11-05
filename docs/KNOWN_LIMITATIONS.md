# DataFlow Enterprise — Known Limitations & Technical Constraints

**Document Version:** 1.11.0  
**Last Updated:** 2026-11-05  

---

## 1. Resolved In Phases 1 Through 11 (All 11 Implementation Phases Complete)

1. **In-Process Scripting & Process Isolation (Resolved in Phase 4):**
   - Python Script, Custom Activities, and Stored Procedures execute inside isolated sub-processes with real-time stdout streaming, timeout enforcement, and parameter injection.

2. **Distributed Compute Cluster Integration (Resolved in Phase 4):**
   - Clean-room Databricks Jobs REST API 2.1 integration and generic PySpark submission interfaces established.

3. **Hierarchical Control Flow & Sub-DAGs (Resolved in Phase 3):**
   - Hierarchical sub-DAGs, `ForEach` (sequential & parallel worker pools), `ExecutePipeline`, `Switch`, `Filter`, `Fail`, `AppendVariable`, and `Until` fully verified.

4. **Vectorized In-Memory Data Flows (Resolved in Phase 6 & 11):**
   - Dedicated visual Data Flow Designer with vectorized Polars multi-node execution graphs, intermediate node caching, JSON flattening, parsing, and type casting.

5. **Dynamic Expression Language (Resolved in Phase 7):**
   - Clean-room recursive descent tokenizer and parser supporting 35+ ADF-grade functions, system parameters, and string interpolation.

6. **Enterprise Data Quality & Governance (Resolved in Phase 8 & 11):**
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

9. **End-to-End Multi-Engine Validation (Resolved in Phase 11):**
   - All 8 mandatory end-to-end integration scenarios verified against live MySQL 8.0, PostgreSQL 16, filesystems, and APIs:
     - Scenario 1: MySQL $\to$ Copy Data $\to$ PostgreSQL (chunked streaming).
     - Scenario 2: REST API $\to$ JSON Parsing $\to$ Flatten $\to$ PostgreSQL.
     - Scenario 3: Get Metadata $\to$ ForEach $\to$ File Processing $\to$ Archive (.zip).
     - Scenario 4: Lookup $\to$ If Condition $\to$ Execute Pipeline.
     - Scenario 5: Source $\to$ Join $\to$ Aggregate $\to$ Derived Column $\to$ Sink.
     - Scenario 6: Copy Data $\to$ Data Quality $\to$ Reconciliation $\to$ Notification.
     - Scenario 7: Incremental Load $\to$ Schema Validation $\to$ Upsert.
     - Scenario 8: Parent Pipeline $\to$ Child Pipeline $\to$ Return Value (`PipelineReturnValueActivity`).
     - Scenarios 9 & 10: Retry resilience and Handled Failure Branch Recovery.

---

## 2. Production Deployment Notes & Architectural Guarantees

1. **Vendor Independence:**
   - 100% clean-room design without Microsoft proprietary code, trademarked assets, or proprietary cloud SDK dependencies.
   - Operates on standard, open infrastructure: PostgreSQL 16, MySQL 8.0, Polars, PyArrow, and FastAPI.

2. **Automated Test Baseline:**
   - **99 passed, 0 failed across all 18 test suites in ~20 seconds**.
   - Frontend compiles cleanly to production bundle with 0 errors.


